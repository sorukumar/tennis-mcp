# 🎾 tennis-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](pyproject.toml)
[![Data: sorukumar/tml-data](https://img.shields.io/badge/Data-sorukumar%2Ftml--data-orange.svg)](https://github.com/sorukumar/tml-data)
[![Visualizations](https://img.shields.io/badge/Live-Tennis%20Analytics-1e5631.svg)](https://sorukumar.github.io/tennis-analytics/)

**Zero-clone Model Context Protocol (MCP) server for Open Era ATP tennis.**

Query **200,105 ATP matches (1968–2026)**, **7,622 player careers**, **113,744 surface-split head-to-heads**, **7,663 Match Charting Project shot/rally breakdowns**, and curated dominance/drama indices (**GSDI**, **NBI**, **Race to Greatness**, **Young Guns**) directly inside Claude, Cursor, Antigravity, or VS Code — **without cloning the 265 MB data repo**.

---

## ⚡ Quick Start (Zero Clone)

`tennis-mcp` runs via `uvx` (or `pip`) and lazily caches only the Parquet/JSON tables your questions need into `~/.cache/tennis-mcp/`.

### Claude Desktop / Cursor / Antigravity (`mcpServers`)

```json
{
  "mcpServers": {
    "tennis-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/sorukumar/tennis-mcp",
        "tennis-mcp"
      ]
    }
  }
}
```

### Claude Code (CLI)

```bash
claude mcp add tennis-mcp -- uvx --from git+https://github.com/sorukumar/tennis-mcp tennis-mcp
```

### VS Code (`.vscode/mcp.json`)

```json
{
  "servers": {
    "tennis-mcp": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/sorukumar/tennis-mcp",
        "tennis-mcp"
      ]
    }
  }
}
```

### Local Development / Offline `tml-data` Override

If you already cloned `sorukumar/tml-data`, point `TML_DATA_DIR` at it to skip HTTPS downloads completely:

```bash
pip install -e ".[dev]"
TML_DATA_DIR=/path/to/tml-data/data tennis-mcp
```

---

## 🛠 Available MCP Capabilities

### 15 Tools (Powered by DuckDB + Parquet + Story JSONs)

| Category | Tool | What It Queries |
|---|---|---|
| **Warehouse** | `get_dataset_overview` | Live row counts, date window, charting counts, and licenses |
| **Players** | `search_players` | Filter 7,622 ATP careers by name, country IOC code, or Slam champion status |
| **Players** | `get_player_profile` | Career W-L, surface splits, Top 10 win%, recent matches, and MCP charting profile |
| **Rivalries** | `get_head_to_head` | Surface-by-surface H2H breakdown (`113,744` pairs) + individual match logs |
| **Matches** | `search_matches` | Parameterized SQL search over `200,105` enriched ATP matches |
| **Shot / Rally** | `get_charting_profile` | 475 players' serve/return, rally length (1–3 / 4–6 / 7–9 / 10+), UF rate, Serve+1, and surface splits |
| **Shot / Rally** | `get_match_charting_stats` | Per-match winners, unforced errors, rally distributions across `7,663` charted matches |
| **Compare** | `compare_players` | Side-by-side comparison of 2–6 players across career stats, charting, and age snapshots |
| **Indices** | `get_gsdi_rankings` | Grand Slam Dominance Index (231 title runs) |
| **Indices** | `get_nail_biters` | Nail-Biter Index (687 Grand Slam Finals & Semifinals) |
| **Indices** | `get_greatness_race` | Age-for-age title & Slam pace: Big 3, Alcaraz, Sinner, Borg, Sampras, McEnroe, Lendl, Agassi |
| **Indices** | `get_young_guns_race` | Fonseca, Mensik, Tien, Jodar benchmarked against Alcaraz & Sinner |
| **Indices** | `get_gs_breakthrough` | Career age, matches, and years before first Grand Slam title across 59 champions |
| **Geography** | `get_country_profile` | Top 100 / Top 10 ATP evolution across 50 years by IOC code or snapshot year |
| **India** | `get_indian_tennis_stats` | Open Era Indian ATP singles milestones & histories |

### 7 Resources (`tennis://*`)
- `tennis://overview`, `tennis://gsdi/top`, `tennis://nbi/top`, `tennis://greatness/summary`, `tennis://young-guns/summary`, `tennis://global/timeline`, `tennis://indian/notable`

### 3 Prompt Templates
- `scouting_report(player_name)`
- `rivalry_breakdown(player1, player2)`
- `slam_campaign_audit(player_name, tournament)`

---

## 💬 Example Questions You Can Ask Your AI

- *"Compare Jannik Sinner and Carlos Alcaraz on 1st-serve won%, unforced error rate, and Clay charting metrics."*
- *"Show me Novak Djokovic vs Rafael Nadal head-to-head by surface, plus their highest Nail-Biter Index Slam matches."*
- *"Which players won a Grand Slam with the fewest tour matches before their first major?"*
- *"How does Joao Fonseca at age 18–20 track against Carlos Alcaraz in ATP wins and Top 50 wins?"*
- *"List the top 5 Grass-court Grand Slam comebacks since 2000 sorted by comeback score and duration."*

---

## 🏗 Architecture

```
Claude / Cursor / Antigravity / VS Code
            │  (stdio MCP)
            ▼
       tennis-mcp  (Python + FastMCP/MCPServer + DuckDB)
            │
            ├── TML_DATA_DIR set? ──▶ Local tml-data/data/*.parquet + *.json
            │
            └── Otherwise ──────────▶ Lazy cache (~/.cache/tennis-mcp/, 7-day TTL)
                                       fetched via HTTPS from sorukumar/tml-data
```

---

## 📄 License & Data Attribution

- **Code**: MIT License ([LICENSE](LICENSE))
- **ATP Match & Career Warehouse (`sorukumar/tml-data`)**: Built on [Tennismylife / TML-Database](https://github.com/Tennismylife/TML-Database) and Jeff Sackmann's ATP archive (MIT).
- **Match Charting Project Tables (`mcp_*.parquet`)**: Derived from [Jeff Sackmann's Match Charting Project](https://github.com/JeffSackmann/tennis_MatchChartingProject), licensed under **CC BY-NC-SA 4.0** (attribution required; non-commercial share-alike for charting tables).

<!-- mcp-name: io.github.sorukumar/tennis-mcp -->
