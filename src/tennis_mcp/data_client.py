"""Zero-clone data resolution, HTTP caching, and DuckDB Parquet execution."""

from __future__ import annotations

import csv
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import duckdb
import httpx

DEFAULT_BASE_URL = "https://raw.githubusercontent.com/sorukumar/tml-data/main/data"
DEFAULT_CACHE_TTL_HOURS = 168.0  # 7 days; monthly CI updates automatically roll over

_JSON_MEM_CACHE: dict[tuple[str, float], Any] = {}


def get_base_url() -> str:
    return os.environ.get("TENNIS_MCP_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def get_cache_dir() -> Path:
    env_dir = os.environ.get("TENNIS_MCP_CACHE_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return Path.home() / ".cache" / "tennis-mcp"


def get_cache_ttl_seconds() -> float:
    raw = os.environ.get("TENNIS_MCP_CACHE_TTL_HOURS", str(DEFAULT_CACHE_TTL_HOURS))
    try:
        hours = float(raw)
        return max(0.0, hours * 3600.0)
    except ValueError:
        return DEFAULT_CACHE_TTL_HOURS * 3600.0


def _normalize_rel_path(rel_path: str) -> str:
    clean = rel_path.lstrip("/")
    if ".." in Path(clean).parts:
        raise ValueError(f"Invalid relative data path: {rel_path!r}")
    return clean


def _find_local_override(rel_path: str) -> Path | None:
    """Resolve against TML_DATA_DIR if set, checking both root/rel and root/data/rel."""
    local_root = os.environ.get("TML_DATA_DIR")
    if not local_root:
        return None
    root_path = Path(local_root).expanduser().resolve()
    for candidate in (root_path / rel_path, root_path / "data" / rel_path):
        if candidate.is_file():
            return candidate
    return None


def _is_fresh(path: Path, ttl_seconds: float) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if ttl_seconds <= 0:
        return False
    age = time.time() - path.stat().st_mtime
    return age <= ttl_seconds


def resolve_file(rel_path: str) -> Path:
    """
    Resolve a tml-data file locally or download/cache it lazily from GitHub Raw.

    Order:
      1. TML_DATA_DIR override (zero network traffic, ideal on dev hosts).
      2. Fresh cached copy in ~/.cache/tennis-mcp/.
      3. Atomic HTTPS download to cache, falling back to stale cache if offline.
    """
    clean = _normalize_rel_path(rel_path)
    local_override = _find_local_override(clean)
    if local_override is not None:
        return local_override

    cache_path = get_cache_dir() / clean
    ttl_seconds = get_cache_ttl_seconds()
    if _is_fresh(cache_path, ttl_seconds):
        return cache_path

    url = f"{get_base_url()}/{clean}"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=".tmp_", suffix=cache_path.suffix or ".tmp", dir=str(cache_path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        os.close(tmp_fd)
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with tmp_path.open("wb") as out:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        out.write(chunk)
        os.replace(tmp_path, cache_path)
        return cache_path
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        if cache_path.is_file() and cache_path.stat().st_size > 0:
            return cache_path
        raise


def load_json(rel_path: str) -> Any:
    """Load and lightly memoize a JSON dataset by path + mtime."""
    resolved = resolve_file(rel_path)
    mtime = resolved.stat().st_mtime
    key = (str(resolved), mtime)
    if key in _JSON_MEM_CACHE:
        return _JSON_MEM_CACHE[key]
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if len(_JSON_MEM_CACHE) > 32:
        _JSON_MEM_CACHE.clear()
    _JSON_MEM_CACHE[key] = data
    return data


def load_csv(rel_path: str) -> list[dict[str, str]]:
    """Load a CSV dataset into list-of-dicts without needing pandas."""
    resolved = resolve_file(rel_path)
    with resolved.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def clean_value(val: Any) -> Any:
    """Convert DuckDB / float NaNs into strict JSON-serializable scalars."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if hasattr(val, "item") and callable(val.item):
        return clean_value(val.item())
    if isinstance(val, dict):
        return {str(k): clean_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [clean_value(v) for v in val]
    return val


def query_parquet(
    tables: dict[str, str],
    sql: str,
    params: list[Any] | tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    """
    Execute parameterized SQL in an ephemeral in-memory DuckDB instance.

    `tables` maps SQL view names -> relative paths in `tml-data/data/`, registered via
    DuckDB's relational API so file paths never touch SQL string formatting.
    """
    con = duckdb.connect(database=":memory:")
    try:
        for alias, rel_path in tables.items():
            resolved = resolve_file(rel_path)
            con.read_parquet(str(resolved)).create_view(alias)
        cursor = con.execute(sql, list(params))
        columns = [desc[0] for desc in (cursor.description or [])]
        rows = cursor.fetchall()
        return [
            {col: clean_value(val) for col, val in zip(columns, row)}
            for row in rows
        ]
    finally:
        con.close()
