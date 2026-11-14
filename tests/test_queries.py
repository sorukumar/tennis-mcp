"""Tests for tennis_mcp query logic and zero-clone cache resolution."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tennis_mcp import data_client, queries

LOCAL_TML_DATA = Path("/home/sorukumar/dev/github/tml-data/data")


@pytest.fixture(autouse=True)
def use_local_tml_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    if LOCAL_TML_DATA.is_dir():
        monkeypatch.setenv("TML_DATA_DIR", str(LOCAL_TML_DATA))
    data_client._JSON_MEM_CACHE.clear()


@pytest.mark.skipif(not LOCAL_TML_DATA.is_dir(), reason="Requires local tml-data checkout")
def test_overview_counts() -> None:
    overview = queries.get_dataset_overview()
    assert overview["total_matches"] >= 200000
    assert overview["total_players"] >= 7500
    assert overview["total_h2h_matchups"] >= 113000
    assert overview["mcp_charted_players"] >= 470
    assert overview["mcp_charted_matches"] >= 7600
    assert "19680101" in overview["date_range"]


@pytest.mark.skipif(not LOCAL_TML_DATA.is_dir(), reason="Requires local tml-data checkout")
def test_search_and_player_profile() -> None:
    res = queries.search_players(query="Alcaraz", grand_slam_champions_only=True, limit=5)
    assert res["count"] >= 1
    assert any(p["player_name"] == "Carlos Alcaraz" for p in res["players"])

    profile = queries.get_player_profile("Djokovic")
    assert profile["player_name"] == "Novak Djokovic"
    assert profile["career_metrics"]["gs_titles"] >= 24
    assert profile["charting_metrics"] is not None
    assert profile["charting_metrics"]["mcp_match_count"] > 100
    assert len(profile["recent_matches"]) == 8


@pytest.mark.skipif(not LOCAL_TML_DATA.is_dir(), reason="Requires local tml-data checkout")
def test_head_to_head_perspective_and_matches() -> None:
    forward = queries.get_head_to_head("Carlos Alcaraz", "Jannik Sinner", include_matches=True, match_limit=5)
    reverse = queries.get_head_to_head("Jannik Sinner", "Carlos Alcaraz", include_matches=False)

    assert forward["summary"]["player1"] == "Carlos Alcaraz"
    assert reverse["summary"]["player1"] == "Jannik Sinner"
    assert forward["summary"]["total_matches"] == reverse["summary"]["total_matches"]
    assert forward["summary"]["player1_wins"] == reverse["summary"]["player2_wins"]
    assert forward["summary"]["player2_wins"] == reverse["summary"]["player1_wins"]
    assert len(forward["matches"]) >= 1


@pytest.mark.skipif(not LOCAL_TML_DATA.is_dir(), reason="Requires local tml-data checkout")
def test_search_matches_and_charting_surface_splits() -> None:
    slams = queries.search_matches(
        player="Federer",
        tournament="Wimbledon",
        surface="Grass",
        round_name="F",
        grand_slam_only=True,
        sort_by="duration",
        limit=5,
    )
    assert slams["count"] >= 3
    assert all(m["tourney_date"] >= 19680000 for m in slams["matches"])

    clay_mcp = queries.get_charting_profile(player_name="Rafael Nadal", surface="Clay")
    assert clay_mcp["count"] == 1
    assert clay_mcp["players"][0]["mcp_match_count"] >= 50

    match_mcp = queries.get_match_charting_stats(player1="Novak Djokovic", player2="Roger Federer", limit=3)
    assert match_mcp["count"] >= 1


@pytest.mark.skipif(not LOCAL_TML_DATA.is_dir(), reason="Requires local tml-data checkout")
def test_story_tools_and_comparison() -> None:
    comp = queries.compare_players(["Roger Federer", "Rafael Nadal", "Carlos Alcaraz"], age=22.0)
    assert len(comp["comparisons"]) == 3
    assert all(c["age_snapshot"] is not None for c in comp["comparisons"])

    gsdi = queries.get_gsdi_rankings(player="Nadal", tournament="Roland Garros", limit=3)
    assert gsdi["total_matched"] >= 3
    assert gsdi["rankings"][0]["player"] == "Rafael Nadal"

    nbi = queries.get_nail_biters(tournament="Wimbledon", limit=3)
    assert nbi["total_matched"] >= 10
    assert nbi["matches"][0]["NBI_100"] == 100.0

    yg = queries.get_young_guns_race()
    assert yg["count"] == 6

    bt = queries.get_gs_breakthrough(limit=10)
    assert bt["total_champions"] >= 58

    india = queries.get_indian_tennis_stats()
    assert india["total_indian_players"] >= 50

    geo = queries.get_country_profile(country_code="IND", year=1980)
    assert geo["stats"] is not None


def test_resolve_file_rejects_traversal() -> None:
    with pytest.raises(ValueError):
        data_client.resolve_file("../../etc/passwd")


def test_resolve_file_uses_fresh_cache_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TML_DATA_DIR", raising=False)
    monkeypatch.setenv("TENNIS_MCP_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("TENNIS_MCP_BASE_URL", "http://127.0.0.1:9/unreachable")

    cached = tmp_path / "base" / "metadata.json"
    cached.parent.mkdir(parents=True)
    cached.write_text(json.dumps({"total_matches": 12345}), encoding="utf-8")

    resolved = data_client.resolve_file("base/metadata.json")
    assert resolved == cached
    assert data_client.load_json("base/metadata.json")["total_matches"] == 12345


def test_resolve_file_downloads_from_http_and_falls_back_to_stale_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    remote_root = tmp_path / "remote"
    (remote_root / "base").mkdir(parents=True)
    (remote_root / "base" / "metadata.json").write_text(
        json.dumps({"total_matches": 99999}), encoding="utf-8"
    )

    class _Quiet(SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Quiet, directory=str(remote_root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cache_dir = tmp_path / "cache"
    try:
        monkeypatch.delenv("TML_DATA_DIR", raising=False)
        monkeypatch.setenv("TENNIS_MCP_CACHE_DIR", str(cache_dir))
        monkeypatch.setenv("TENNIS_MCP_CACHE_TTL_HOURS", "1")
        monkeypatch.setenv("TENNIS_MCP_BASE_URL", f"http://127.0.0.1:{server.server_address[1]}")

        assert data_client.load_json("base/metadata.json")["total_matches"] == 99999
        assert (cache_dir / "base" / "metadata.json").is_file()
    finally:
        server.shutdown()
        server.server_close()

    # Force expired cache while HTTP server is stopped -> must fall back cleanly to stale cache
    monkeypatch.setenv("TENNIS_MCP_CACHE_TTL_HOURS", "0")
    data_client._JSON_MEM_CACHE.clear()
    assert data_client.load_json("base/metadata.json")["total_matches"] == 99999
