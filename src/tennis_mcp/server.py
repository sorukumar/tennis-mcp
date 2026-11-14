"""Fast / zero-clone MCP Server entrypoint for tennis-mcp."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from tennis_mcp import queries

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

mcp = MCPServer(
    name="tennis-mcp",
    title="Tennis Analytics MCP",
    description=(
        "Zero-clone ATP Open Era analytics (200,105 matches since 1968), 7,663 Match Charting "
        "Project point/rally breakdowns, head-to-head histories, GSDI, NBI, and player comparisons."
    ),
    instructions=(
        "Use search_players or get_player_profile for career stats, get_head_to_head for rivalries, "
        "search_matches for filtering the 200k-match archive, get_charting_profile / get_match_charting_stats "
        "for point-by-point Match Charting Project shot/rally profiles, and story tools (GSDI, NBI, "
        "Race to Greatness, Young Guns, GS Breakthrough) for curated rankings."
    ),
    website_url="https://sorukumar.github.io/tennis-analytics/",
)


def _json_str(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


# =============================================================================
# TOOLS — PARQUET WAREHOUSE & CHARTING QUERIES
# =============================================================================


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_dataset_overview() -> dict[str, Any]:
    """Get live row counts, date coverage (1968-2026), charting coverage, and license attribution."""
    return queries.get_dataset_overview()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def search_players(
    query: str = "",
    country: str | None = None,
    min_matches: int = 1,
    grand_slam_champions_only: bool = False,
    limit: int = 15,
) -> dict[str, Any]:
    """Search 7,622 Open Era ATP players by name fragment, 3-letter country code (e.g. ESP, ITA, IND), or Grand Slam status."""
    return queries.search_players(
        query=query,
        country=country,
        min_matches=min_matches,
        grand_slam_champions_only=grand_slam_champions_only,
        limit=limit,
    )


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_player_profile(player_name: str) -> dict[str, Any]:
    """Get a player's full ATP career stats, surface splits, top-10 win rates, Match Charting Project profile (if charted), and recent matches."""
    return queries.get_player_profile(player_name=player_name)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_head_to_head(
    player1: str,
    player2: str,
    include_matches: bool = True,
    match_limit: int = 15,
) -> dict[str, Any]:
    """Get overall and surface-by-surface head-to-head record plus chronological match results between two ATP players."""
    return queries.get_head_to_head(
        player1=player1,
        player2=player2,
        include_matches=include_matches,
        match_limit=match_limit,
    )


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def search_matches(
    player: str | None = None,
    opponent: str | None = None,
    tournament: str | None = None,
    surface: str | None = None,
    round_name: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    grand_slam_only: bool = False,
    min_comeback_score: int | None = None,
    sort_by: str = "recent",
    limit: int = 20,
) -> dict[str, Any]:
    """Search 200,105 ATP matches by player, opponent, tournament, surface (Hard/Clay/Grass/Carpet), round, year range, Grand Slam filter, or comeback score."""
    return queries.search_matches(
        player=player,
        opponent=opponent,
        tournament=tournament,
        surface=surface,
        round_name=round_name,
        year_from=year_from,
        year_to=year_to,
        grand_slam_only=grand_slam_only,
        min_comeback_score=min_comeback_score,
        sort_by=sort_by,
        limit=limit,
    )


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_charting_profile(
    player_name: str | None = None,
    surface: str | None = None,
    sort_by: str = "mcp_match_count",
    min_matches: int = 10,
    limit: int = 15,
) -> dict[str, Any]:
    """Get Jeff Sackmann Match Charting Project shot/rally profiles (1st/2nd serve win%, return%, rally length, UF error rate, Serve+1, BP save delta) across 475 players."""
    return queries.get_charting_profile(
        player_name=player_name,
        surface=surface,
        sort_by=sort_by,
        min_matches=min_matches,
        limit=limit,
    )


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_match_charting_stats(
    player1: str,
    player2: str | None = None,
    tournament: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Inspect point-by-point charted match breakdowns (aces, winners, unforced errors, rally length distribution, TML link) from 7,663 MCP matches."""
    return queries.get_match_charting_stats(
        player1=player1,
        player2=player2,
        tournament=tournament,
        limit=limit,
    )


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def compare_players(players: list[str], age: float | None = None) -> dict[str, Any]:
    """Compare 2 to 6 ATP players side by side across career stats, charting styles, and optional age-for-age milestone trajectories."""
    return queries.compare_players(players=players, age=age)


# =============================================================================
# TOOLS — CURATED STORY INDICES (GSDI, NBI, GREATNESS, YOUNG GUNS, GEOGRAPHY)
# =============================================================================


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_gsdi_rankings(
    player: str | None = None,
    tournament: str | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    """Rank the most mathematically dominant Grand Slam title campaigns using the Grand Slam Dominance Index (GSDI)."""
    return queries.get_gsdi_rankings(player=player, tournament=tournament, limit=limit)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_nail_biters(
    player: str | None = None,
    tournament: str | None = None,
    tag: str | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    """Find the highest-drama Grand Slam Finals & Semifinals using the Nail-Biter Index (NBI)."""
    return queries.get_nail_biters(player=player, tournament=tournament, tag=tag, limit=limit)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_greatness_race(player: str | None = None, age: float | None = None) -> dict[str, Any]:
    """Compare Big 3, Alcaraz, Sinner, Borg, Sampras, McEnroe, Lendl, and Agassi on titles, Slams, and Masters at any age."""
    return queries.get_greatness_race(player=player, age=age)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_young_guns_race(player: str | None = None, age: float | None = None) -> dict[str, Any]:
    """Track ATP next-wave talents (Joao Fonseca, Jakub Mensik, Learner Tien, Rafael Jodar) against Alcaraz and Sinner age benchmarks."""
    return queries.get_young_guns_race(player=player, age=age)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_gs_breakthrough(player: str | None = None, limit: int = 25) -> dict[str, Any]:
    """Analyze how quickly Open Era Grand Slam champions broke through to their first major title."""
    return queries.get_gs_breakthrough(player=player, limit=limit)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_country_profile(country_code: str | None = None, year: int | None = None) -> dict[str, Any]:
    """Explore global Top 100 and Top 10 ATP representation trends (1975-2025) by IOC country code or snapshot year."""
    return queries.get_country_profile(country_code=country_code, year=year)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def get_indian_tennis_stats(player: str | None = None) -> dict[str, Any]:
    """Query India's Open Era ATP singles history and milestone achievements."""
    return queries.get_indian_tennis_stats(player=player)


# =============================================================================
# RESOURCES
# =============================================================================


@mcp.resource("tennis://overview", mime_type="application/json")
def overview_resource() -> str:
    """Dataset summary, update timestamp, row counts, and data licenses."""
    return _json_str(queries.get_dataset_overview())


@mcp.resource("tennis://gsdi/top", mime_type="application/json")
def gsdi_top_resource() -> str:
    """Top 20 Grand Slam Dominance Index runs."""
    return _json_str(queries.get_gsdi_rankings(limit=20))


@mcp.resource("tennis://nbi/top", mime_type="application/json")
def nbi_top_resource() -> str:
    """Top 20 Grand Slam Nail-Biter Index matches."""
    return _json_str(queries.get_nail_biters(limit=20))


@mcp.resource("tennis://greatness/summary", mime_type="application/json")
def greatness_summary_resource() -> str:
    """Latest Career Greatness Race stats across all tracked legends and active stars."""
    return _json_str(queries.get_greatness_race())


@mcp.resource("tennis://young-guns/summary", mime_type="application/json")
def young_guns_resource() -> str:
    """Latest Young Guns scouting leaderboard vs Alcaraz/Sinner benchmarks."""
    return _json_str(queries.get_young_guns_race())


@mcp.resource("tennis://global/timeline", mime_type="application/json")
def global_timeline_resource() -> str:
    """Global ATP geographic diversity index timeline (1975-2025)."""
    return _json_str(queries.get_country_profile())


@mcp.resource("tennis://indian/notable", mime_type="application/json")
def indian_notable_resource() -> str:
    """Notable Indian ATP players across the Open Era."""
    return _json_str(queries.get_indian_tennis_stats())


# =============================================================================
# PROMPTS
# =============================================================================


@mcp.prompt(description="Generate a data-backed ATP scouting & tactical charting brief for a player.")
def scouting_report(player_name: str) -> str:
    return (
        f"Build a structured scouting report for {player_name} using tennis-mcp:\n"
        f"1. Call get_player_profile(player_name={player_name!r}) for career, surface, Top 10 win%, and recent matches.\n"
        f"2. If charted data exists, highlight 1st/2nd serve win%, return win%, average rally length, UF error rate, Serve+1 win%, and BP save delta.\n"
        f"3. Call get_charting_profile(player_name={player_name!r}, surface='Hard') and surface='Clay' to contrast tactical shifts by surface.\n"
        f"Summarize strengths, vulnerabilities, and cite Open Era numbers + Match Charting Project attribution cleanly."
    )


@mcp.prompt(description="Analyze a classic or upcoming ATP rivalry across surfaces, comebacks, and tactical charting matchups.")
def rivalry_breakdown(player1: str, player2: str) -> str:
    return (
        f"Analyze the ATP rivalry between {player1} and {player2} using tennis-mcp:\n"
        f"1. Call get_head_to_head(player1={player1!r}, player2={player2!r}, include_matches=True, match_limit=20).\n"
        f"2. Call compare_players(players=[{player1!r}, {player2!r}]) for career & tactical charting deltas.\n"
        f"3. Call get_match_charting_stats(player1={player1!r}, player2={player2!r}, limit=5) and get_nail_biters(player={player1!r}) for Grand Slam drama context.\n"
        f"Deliver a concise breakdown by surface, deciding-set/tiebreak resilience, and tactical style clash."
    )


@mcp.prompt(description="Audit historical Grand Slam dominance campaigns using GSDI and NBI metrics.")
def slam_campaign_audit(player_name: str, tournament: str = "") -> str:
    return (
        f"Evaluate {player_name}'s Grand Slam peaks using tennis-mcp:\n"
        f"1. Call get_gsdi_rankings(player={player_name!r}, tournament={(tournament or None)!r}, limit=15).\n"
        f"2. Call get_nail_biters(player={player_name!r}, tournament={(tournament or None)!r}, limit=10).\n"
        f"Contrast dominance (sets lost, speed score, opponent quality) against survival/drama matches."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
