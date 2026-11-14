"""Domain query functions backed by tml-data Parquet warehouse & JSON stories."""

from __future__ import annotations

from typing import Any

from tennis_mcp.data_client import load_csv, load_json, query_parquet

ATTRIBUTION_TML = "sorukumar/tml-data (ATP Open Era via Tennismylife / TML-Database, MIT)"
ATTRIBUTION_MCP = "Jeff Sackmann's Match Charting Project via sorukumar/tml-data (CC BY-NC-SA 4.0)"

ALLOWED_MATCH_SORTS = {
    "recent": "tourney_date DESC, match_num DESC",
    "duration": "COALESCE(minutes, 0) DESC, tourney_date DESC",
    "comeback": "COALESCE(comeback_score, 0) DESC, COALESCE(tiebreaks_count, 0) DESC, tourney_date DESC",
    "tiebreaks": "COALESCE(tiebreaks_count, 0) DESC, COALESCE(minutes, 0) DESC, tourney_date DESC",
}

ALLOWED_CHARTING_SORTS = {
    "mcp_match_count": "mcp_match_count DESC",
    "avg_rally_length": "avg_rally_length DESC",
    "first_won_pct": "first_won_pct DESC",
    "serve_win_pct": "serve_win_pct DESC",
    "return_win_pct": "return_win_pct DESC",
    "bp_save_pct": "bp_save_pct DESC",
    "bp_save_vs_serve_win_delta": "bp_save_vs_serve_win_delta DESC",
    "serve_trans_win_pct": "serve_trans_win_pct DESC",
    "uf_rate": "uf_rate ASC",
}


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _like_pattern(term: str) -> str:
    return f"%{_escape_like(term.strip())}%"


def resolve_player_name(query: str) -> tuple[str | None, list[dict[str, Any]]]:
    """
    Resolve a player name or surname against player_metrics & mcp_player_crosswalk.

    Returns (canonical_name, candidates). `canonical_name` is None when not found
    or genuinely ambiguous.
    """
    clean = " ".join(query.strip().split())
    if not clean:
        return None, []

    exact = query_parquet(
        {"players": "base/player_metrics.parquet"},
        """
        SELECT player_name, country, total_matches, total_wins, peak_ranking, gs_titles
        FROM players
        WHERE LOWER(player_name) = LOWER(?)
        LIMIT 1
        """,
        [clean],
    )
    if exact:
        return exact[0]["player_name"], exact

    # Check MCP crosswalk aliases (e.g., Stanislas Wawrinka <-> Stan Wawrinka)
    cross = query_parquet(
        {"cw": "base/mcp_player_crosswalk.parquet"},
        """
        SELECT tml_player_name
        FROM cw
        WHERE LOWER(mcp_player_name) = LOWER(?)
        LIMIT 1
        """,
        [clean],
    )
    if cross and cross[0].get("tml_player_name"):
        return cross[0]["tml_player_name"], []

    candidates = query_parquet(
        {"players": "base/player_metrics.parquet"},
        """
        SELECT player_name, country, career_start_year, career_end_year,
               total_matches, total_wins, peak_ranking, gs_titles
        FROM players
        WHERE LOWER(player_name) LIKE LOWER(?) ESCAPE '\\'
        ORDER BY gs_titles DESC, total_matches DESC
        LIMIT 8
        """,
        [_like_pattern(clean)],
    )
    if not candidates:
        return None, []
    if len(candidates) == 1:
        return candidates[0]["player_name"], candidates

    # Safe disambiguation for unmistakable surname queries (e.g., "Djokovic", "Alcaraz")
    top = candidates[0]
    second = candidates[1]
    if (
        len(clean) >= 5
        and (top.get("total_matches") or 0) >= 50
        and (top.get("total_matches") or 0) >= max(5 * (second.get("total_matches") or 1), 100)
        and (second.get("total_matches") or 0) < 25
    ):
        return top["player_name"], candidates

    return None, candidates


def _resolve_mcp_name(tml_or_mcp_name: str) -> str | None:
    clean = " ".join(tml_or_mcp_name.strip().split())
    direct = query_parquet(
        {"mcp": "base/mcp_player_metrics.parquet"},
        "SELECT player_name FROM mcp WHERE LOWER(player_name) = LOWER(?) LIMIT 1",
        [clean],
    )
    if direct:
        return direct[0]["player_name"]

    mapped = query_parquet(
        {"cw": "base/mcp_player_crosswalk.parquet"},
        """
        SELECT mcp_player_name
        FROM cw
        WHERE LOWER(tml_player_name) = LOWER(?) OR LOWER(mcp_player_name) = LOWER(?)
        ORDER BY match_count DESC
        LIMIT 1
        """,
        [clean, clean],
    )
    if mapped and mapped[0].get("mcp_player_name"):
        return mapped[0]["mcp_player_name"]

    fuzzy = query_parquet(
        {"mcp": "base/mcp_player_metrics.parquet"},
        """
        SELECT player_name
        FROM mcp
        WHERE LOWER(player_name) LIKE LOWER(?) ESCAPE '\\'
        ORDER BY mcp_match_count DESC
        LIMIT 2
        """,
        [_like_pattern(clean)],
    )
    if len(fuzzy) == 1:
        return fuzzy[0]["player_name"]
    return None


def get_dataset_overview() -> dict[str, Any]:
    """Return live warehouse counts, coverage window, and data attribution."""
    meta = load_json("base/metadata.json")
    mcp_counts = query_parquet(
        {
            "pm": "base/player_metrics.parquet",
            "h2h": "base/head_to_head.parquet",
            "mcp_pm": "base/mcp_player_metrics.parquet",
            "mcp_m": "base/mcp_matches_enriched.parquet",
        },
        """
        SELECT
            (SELECT COUNT(*) FROM pm) AS total_players,
            (SELECT SUM(CASE WHEN has_gs_title THEN 1 ELSE 0 END) FROM pm) AS gs_champions,
            (SELECT COUNT(*) FROM h2h) AS total_h2h_matchups,
            (SELECT COUNT(*) FROM mcp_pm) AS mcp_charted_players,
            (SELECT COUNT(*) FROM mcp_m) AS mcp_charted_matches
        """,
    )[0]
    return {
        "date_range": meta.get("date_range"),
        "updated_at": meta.get("updated_at") or meta.get("fetch_date"),
        "total_matches": meta.get("total_matches"),
        "total_players": mcp_counts["total_players"],
        "grand_slam_champions": mcp_counts["gs_champions"],
        "total_h2h_matchups": mcp_counts["total_h2h_matchups"],
        "mcp_charted_players": mcp_counts["mcp_charted_players"],
        "mcp_charted_matches": mcp_counts["mcp_charted_matches"],
        "visualizations_url": "https://sorukumar.github.io/tennis-analytics/",
        "warehouse_repo": "https://github.com/sorukumar/tml-data",
        "attribution": [ATTRIBUTION_TML, ATTRIBUTION_MCP],
    }


def search_players(
    query: str = "",
    country: str | None = None,
    min_matches: int = 1,
    grand_slam_champions_only: bool = False,
    limit: int = 15,
) -> dict[str, Any]:
    """Search ATP players across all 7,622 Open Era careers."""
    limit = max(1, min(int(limit), 50))
    clauses = ["total_matches >= ?"]
    params: list[Any] = [int(min_matches)]

    if query.strip():
        clauses.append("LOWER(player_name) LIKE LOWER(?) ESCAPE '\\'")
        params.append(_like_pattern(query))
    if country and country.strip():
        clauses.append("UPPER(country) = UPPER(?)")
        params.append(country.strip())
    if grand_slam_champions_only:
        clauses.append("has_gs_title = TRUE")

    where_sql = " AND ".join(clauses)
    params.append(limit)

    rows = query_parquet(
        {"players": "base/player_metrics.parquet"},
        f"""
        SELECT player_name, country, career_start_year, career_end_year,
               career_span_years, total_matches, total_wins, total_losses, win_pct,
               peak_ranking, gs_titles, gs_finals, gs_semifinals, gs_wins,
               hard_win_pct, clay_win_pct, grass_win_pct, top10_wins, top10_win_pct
        FROM players
        WHERE {where_sql}
        ORDER BY gs_titles DESC, total_wins DESC, win_pct DESC
        LIMIT ?
        """,
        params,
    )
    return {
        "count": len(rows),
        "players": rows,
        "source": ATTRIBUTION_TML,
    }


def get_player_profile(player_name: str) -> dict[str, Any]:
    """Fetch complete career metrics, surface splits, big-match stats, and charting stats if available."""
    canonical, candidates = resolve_player_name(player_name)
    if canonical is None:
        return {
            "error": f"Could not uniquely resolve player {player_name!r}.",
            "candidates": candidates,
        }

    career_rows = query_parquet(
        {"players": "base/player_metrics.parquet"},
        "SELECT * FROM players WHERE player_name = ? LIMIT 1",
        [canonical],
    )
    if not career_rows:
        return {"error": f"Player {canonical!r} not found in player_metrics."}
    career = career_rows[0]

    mcp_name = _resolve_mcp_name(canonical)
    charting = None
    if mcp_name:
        mcp_rows = query_parquet(
            {"mcp": "base/mcp_player_metrics.parquet"},
            "SELECT * FROM mcp WHERE player_name = ? LIMIT 1",
            [mcp_name],
        )
        if mcp_rows:
            charting = mcp_rows[0]

    recent_matches = query_parquet(
        {"matches": "base/matches_enriched.parquet"},
        """
        SELECT tourney_date, tourney_name, surface, round, score,
               winner_name, loser_name, winner_rank, loser_rank,
               is_grand_slam, comeback_score, minutes
        FROM matches
        WHERE tourney_date >= 19680000
          AND (winner_name = ? OR loser_name = ?)
        ORDER BY tourney_date DESC, match_num DESC
        LIMIT 8
        """,
        [canonical, canonical],
    )

    return {
        "player_name": canonical,
        "career_metrics": career,
        "charting_metrics": charting,
        "recent_matches": recent_matches,
        "sources": [ATTRIBUTION_TML] + ([ATTRIBUTION_MCP] if charting else []),
    }


def _normalize_h2h_row(row: dict[str, Any], requested_p1: str) -> dict[str, Any]:
    if row["player1"] == requested_p1:
        return row
    return {
        "player1": row["player2"],
        "player2": row["player1"],
        "total_matches": row["total_matches"],
        "player1_wins": row["player2_wins"],
        "player2_wins": row["player1_wins"],
        "hard_total": row["hard_total"],
        "hard_p1_wins": row["hard_p2_wins"],
        "hard_p2_wins": row["hard_p1_wins"],
        "clay_total": row["clay_total"],
        "clay_p1_wins": row["clay_p2_wins"],
        "clay_p2_wins": row["clay_p1_wins"],
        "grass_total": row["grass_total"],
        "grass_p1_wins": row["grass_p2_wins"],
        "grass_p2_wins": row["grass_p1_wins"],
        "carpet_total": row["carpet_total"],
        "carpet_p1_wins": row["carpet_p2_wins"],
        "carpet_p2_wins": row["carpet_p1_wins"],
    }


def get_head_to_head(
    player1: str,
    player2: str,
    include_matches: bool = True,
    match_limit: int = 15,
) -> dict[str, Any]:
    """Query surface-by-surface H2H record plus individual match logs from 200,105 ATP matches."""
    p1, p1_candidates = resolve_player_name(player1)
    if p1 is None:
        return {"error": f"Could not resolve player1 {player1!r}.", "candidates": p1_candidates}
    p2, p2_candidates = resolve_player_name(player2)
    if p2 is None:
        return {"error": f"Could not resolve player2 {player2!r}.", "candidates": p2_candidates}

    rows = query_parquet(
        {"h2h": "base/head_to_head.parquet"},
        """
        SELECT * FROM h2h
        WHERE (player1 = ? AND player2 = ?)
           OR (player1 = ? AND player2 = ?)
        LIMIT 1
        """,
        [p1, p2, p2, p1],
    )
    if not rows:
        return {
            "player1": p1,
            "player2": p2,
            "total_matches": 0,
            "message": f"No recorded ATP matches between {p1} and {p2}.",
            "matches": [],
            "source": ATTRIBUTION_TML,
        }

    summary = _normalize_h2h_row(rows[0], p1)
    matches: list[dict[str, Any]] = []
    if include_matches:
        limit_val = max(1, min(int(match_limit), 50))
        matches = query_parquet(
            {"matches": "base/matches_enriched.parquet"},
            """
            SELECT tourney_date, year, tourney_name, surface, tourney_level,
                   is_grand_slam, round, winner_name, loser_name, score,
                   winner_rank, loser_rank, tiebreaks_count, comeback_score, minutes
            FROM matches
            WHERE tourney_date >= 19680000
              AND ((winner_name = ? AND loser_name = ?)
                OR (winner_name = ? AND loser_name = ?))
            ORDER BY tourney_date DESC, match_num DESC
            LIMIT ?
            """,
            [p1, p2, p2, p1, limit_val],
        )

    return {
        "summary": summary,
        "matches": matches,
        "source": ATTRIBUTION_TML,
    }


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
    """Filter the 200,105-match enriched ATP warehouse with safe parameterized SQL."""
    limit = max(1, min(int(limit), 50))
    order_sql = ALLOWED_MATCH_SORTS.get(sort_by)
    if order_sql is None:
        return {
            "error": f"Invalid sort_by {sort_by!r}. Allowed: {sorted(ALLOWED_MATCH_SORTS)}"
        }

    clauses = ["tourney_date >= 19680000"]
    params: list[Any] = []

    resolved_player = None
    if player and player.strip():
        resolved_player, cand = resolve_player_name(player)
        if resolved_player is None:
            return {"error": f"Could not resolve player {player!r}.", "candidates": cand}
        clauses.append("(winner_name = ? OR loser_name = ?)")
        params.extend([resolved_player, resolved_player])

    if opponent and opponent.strip():
        resolved_opp, cand = resolve_player_name(opponent)
        if resolved_opp is None:
            return {"error": f"Could not resolve opponent {opponent!r}.", "candidates": cand}
        clauses.append("(winner_name = ? OR loser_name = ?)")
        params.extend([resolved_opp, resolved_opp])

    if tournament and tournament.strip():
        clauses.append("LOWER(tourney_name) LIKE LOWER(?) ESCAPE '\\'")
        params.append(_like_pattern(tournament))
    if surface and surface.strip():
        clauses.append("LOWER(surface) = LOWER(?)")
        params.append(surface.strip())
    if round_name and round_name.strip():
        clauses.append("UPPER(round) = UPPER(?)")
        params.append(round_name.strip())
    if year_from is not None:
        clauses.append("year >= ?")
        params.append(int(year_from))
    if year_to is not None:
        clauses.append("year <= ?")
        params.append(int(year_to))
    if grand_slam_only:
        clauses.append("is_grand_slam = TRUE")
    if min_comeback_score is not None:
        clauses.append("COALESCE(comeback_score, 0) >= ?")
        params.append(int(min_comeback_score))

    where_sql = " AND ".join(clauses)
    params.append(limit)

    rows = query_parquet(
        {"matches": "base/matches_enriched.parquet"},
        f"""
        SELECT tourney_date, year, tourney_name, surface, tourney_level,
               is_grand_slam, round, winner_name, loser_name, score,
               winner_rank, loser_rank, winner_sets, loser_sets,
               tiebreaks_count, comeback_score, final_set_tiebreak, minutes
        FROM matches
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT ?
        """,
        params,
    )
    return {
        "count": len(rows),
        "player_resolved": resolved_player,
        "matches": rows,
        "source": ATTRIBUTION_TML,
    }


def get_charting_profile(
    player_name: str | None = None,
    surface: str | None = None,
    sort_by: str = "mcp_match_count",
    min_matches: int = 10,
    limit: int = 15,
) -> dict[str, Any]:
    """
    Query Match Charting Project shot/rally metrics across 475 players & 7,663 matches.

    When `surface` is omitted, reads pre-aggregated `mcp_player_metrics.parquet`.
    When `surface` (Hard/Clay/Grass) is provided, computes splits from `mcp_matches_enriched.parquet`.
    """
    limit = max(1, min(int(limit), 50))
    if sort_by not in ALLOWED_CHARTING_SORTS:
        return {
            "error": f"Invalid sort_by {sort_by!r}. Allowed: {sorted(ALLOWED_CHARTING_SORTS)}"
        }

    if surface and surface.strip():
        clean_surface = surface.strip()
        target_mcp = _resolve_mcp_name(player_name) if player_name and player_name.strip() else None
        if player_name and player_name.strip() and not target_mcp:
            return {"error": f"No MCP charting data found for {player_name!r}."}

        where_player = "WHERE LOWER(player_name) = LOWER(?)" if target_mcp else "HAVING COUNT(*) >= ?"
        sql_params: list[Any] = [clean_surface, clean_surface]
        if target_mcp:
            sql_params.append(target_mcp)
        else:
            sql_params.append(int(min_matches))
        sql_params.append(limit)

        rows = query_parquet(
            {"m": "base/mcp_matches_enriched.parquet"},
            f"""
            WITH player_side AS (
                SELECT player1_name AS player_name, surface, tourney_date,
                       player1_serve_pts AS serve_pts, player1_aces AS aces, player1_dfs AS dfs,
                       player1_first_in AS first_in, player1_first_won AS first_won,
                       player1_second_won AS second_won, player1_bp_faced AS bp_faced,
                       player1_bp_saved AS bp_saved, player1_return_pts AS return_pts,
                       player1_return_won AS return_won, player1_winners AS winners,
                       player1_unforced AS unforced, match_avg_rally
                FROM m WHERE LOWER(surface) = LOWER(?)
                UNION ALL
                SELECT player2_name AS player_name, surface, tourney_date,
                       player2_serve_pts AS serve_pts, player2_aces AS aces, player2_dfs AS dfs,
                       player2_first_in AS first_in, player2_first_won AS first_won,
                       player2_second_won AS second_won, player2_bp_faced AS bp_faced,
                       player2_bp_saved AS bp_saved, player2_return_pts AS return_pts,
                       player2_return_won AS return_won, player2_winners AS winners,
                       player2_unforced AS unforced, match_avg_rally
                FROM m WHERE LOWER(surface) = LOWER(?)
            )
            SELECT
                player_name,
                COUNT(*) AS mcp_match_count,
                SUM(serve_pts) AS serve_pts,
                SUM(aces) AS aces,
                ROUND(100.0 * SUM(first_won + second_won) / NULLIF(SUM(serve_pts), 0), 2) AS serve_win_pct,
                ROUND(100.0 * SUM(first_won) / NULLIF(SUM(first_in), 0), 2) AS first_won_pct,
                ROUND(100.0 * SUM(return_won) / NULLIF(SUM(return_pts), 0), 2) AS return_win_pct,
                ROUND(100.0 * SUM(bp_saved) / NULLIF(SUM(bp_faced), 0), 2) AS bp_save_pct,
                ROUND(AVG(match_avg_rally), 2) AS avg_rally_length,
                SUM(winners) AS winners,
                SUM(unforced) AS unforced_errors
            FROM player_side
            {"WHERE LOWER(player_name) = LOWER(?)" if target_mcp else ""}
            GROUP BY player_name
            {"" if target_mcp else where_player}
            ORDER BY mcp_match_count DESC
            LIMIT ?
            """,
            sql_params,
        )
        return {
            "surface": clean_surface,
            "count": len(rows),
            "players": rows,
            "source": ATTRIBUTION_MCP,
        }

    if player_name and player_name.strip():
        target_mcp = _resolve_mcp_name(player_name)
        if not target_mcp:
            return {"error": f"No MCP charting data found for {player_name!r}."}
        rows = query_parquet(
            {"mcp": "base/mcp_player_metrics.parquet"},
            "SELECT * FROM mcp WHERE player_name = ? LIMIT 1",
            [target_mcp],
        )
        return {
            "player": rows[0] if rows else None,
            "source": ATTRIBUTION_MCP,
        }

    order_sql = ALLOWED_CHARTING_SORTS[sort_by]
    rows = query_parquet(
        {"mcp": "base/mcp_player_metrics.parquet"},
        f"""
        SELECT player_name, mcp_match_count, mcp_year_min, mcp_year_max,
               first_in_pct, first_won_pct, second_won_pct, serve_win_pct,
               return_win_pct, avg_rally_length, uf_rate,
               serve_trans_win_pct, bp_save_pct, bp_save_vs_serve_win_delta
        FROM mcp
        WHERE mcp_match_count >= ?
        ORDER BY {order_sql}
        LIMIT ?
        """,
        [int(min_matches), limit],
    )
    return {
        "sort_by": sort_by,
        "count": len(rows),
        "players": rows,
        "source": ATTRIBUTION_MCP,
    }


def get_match_charting_stats(
    player1: str,
    player2: str | None = None,
    tournament: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Retrieve match-level shot/rally/winner/error breakdowns from the 7,663 MCP matches."""
    limit = max(1, min(int(limit), 30))
    m1 = _resolve_mcp_name(player1) or player1.strip()
    clauses = ["(LOWER(player1_name) LIKE LOWER(?) ESCAPE '\\' OR LOWER(player2_name) LIKE LOWER(?) ESCAPE '\\')"]
    params: list[Any] = [_like_pattern(m1), _like_pattern(m1)]

    if player2 and player2.strip():
        m2 = _resolve_mcp_name(player2) or player2.strip()
        clauses.append("(LOWER(player1_name) LIKE LOWER(?) ESCAPE '\\' OR LOWER(player2_name) LIKE LOWER(?) ESCAPE '\\')")
        params.extend([_like_pattern(m2), _like_pattern(m2)])
    if tournament and tournament.strip():
        clauses.append("LOWER(tournament) LIKE LOWER(?) ESCAPE '\\'")
        params.append(_like_pattern(tournament))

    where_sql = " AND ".join(clauses)
    params.append(limit)

    rows = query_parquet(
        {"m": "base/mcp_matches_enriched.parquet"},
        f"""
        SELECT match_id, tourney_date, tournament, surface, round, best_of,
               player1_name, player2_name, total_pts, match_avg_rally,
               rally_1_3_pct, rally_4_6_pct, rally_7_9_pct, rally_10_pct,
               player1_aces, player1_winners, player1_unforced,
               p1_serve_win_pct, p1_return_win_pct, p1_bp_save_pct, p1_long_rally_win_pct,
               player2_aces, player2_winners, player2_unforced,
               p2_serve_win_pct, p2_return_win_pct, p2_bp_save_pct, p2_long_rally_win_pct,
               tml_winner_name, tml_loser_name, tml_join_confidence
        FROM m
        WHERE {where_sql}
        ORDER BY tourney_date DESC
        LIMIT ?
        """,
        params,
    )
    return {
        "count": len(rows),
        "matches": rows,
        "source": ATTRIBUTION_MCP,
    }


def _trajectory_at_age(trajectory: list[dict[str, Any]], target_age: float | None) -> dict[str, Any]:
    if not trajectory:
        return {}
    if target_age is None:
        return trajectory[-1]
    eligible = [pt for pt in trajectory if pt.get("age", 999) <= target_age]
    return eligible[-1] if eligible else trajectory[0]


def compare_players(players: list[str], age: float | None = None) -> dict[str, Any]:
    """Compare 2 to 6 ATP players across career stats, MCP charting profiles, and age snapshots."""
    if len(players) < 2 or len(players) > 6:
        return {"error": "Provide between 2 and 6 player names to compare."}

    greatness_data = load_json("greatness/race_to_greatness.json").get("players", {})
    young_guns_data = load_json("greatness/young_guns_race.json").get("players", {})

    comparisons: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for raw_name in players:
        canonical, candidates = resolve_player_name(raw_name)
        if canonical is None:
            errors.append({"query": raw_name, "candidates": candidates})
            continue

        career = query_parquet(
            {"pm": "base/player_metrics.parquet"},
            """
            SELECT player_name, country, career_start_year, career_end_year,
                   total_matches, total_wins, win_pct, peak_ranking,
                   gs_titles, gs_finals, gs_win_pct,
                   hard_win_pct, clay_win_pct, grass_win_pct,
                   top5_win_pct, top10_win_pct, first_gs_title_age
            FROM pm WHERE player_name = ? LIMIT 1
            """,
            [canonical],
        )[0]

        mcp_name = _resolve_mcp_name(canonical)
        mcp_stats = None
        if mcp_name:
            res = query_parquet(
                {"mcp": "base/mcp_player_metrics.parquet"},
                """
                SELECT mcp_match_count, first_won_pct, second_won_pct, serve_win_pct,
                       return_win_pct, avg_rally_length, uf_rate,
                       serve_trans_win_pct, bp_save_pct, bp_save_vs_serve_win_delta
                FROM mcp WHERE player_name = ? LIMIT 1
                """,
                [mcp_name],
            )
            if res:
                mcp_stats = res[0]

        age_snapshot = None
        if canonical in greatness_data:
            snap = _trajectory_at_age(greatness_data[canonical].get("trajectory", []), age)
            age_snapshot = {"source": "race_to_greatness", **snap}
        elif canonical in young_guns_data:
            snap = _trajectory_at_age(young_guns_data[canonical].get("trajectory", []), age)
            age_snapshot = {"source": "young_guns_race", **snap}

        comparisons.append({
            "player_name": canonical,
            "career": career,
            "charting": mcp_stats,
            "age_snapshot": age_snapshot,
        })

    return {
        "target_age": age,
        "comparisons": comparisons,
        "unresolved": errors,
        "sources": [ATTRIBUTION_TML, ATTRIBUTION_MCP],
    }


def get_gsdi_rankings(
    player: str | None = None,
    tournament: str | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    """Query Grand Slam Dominance Index (GSDI) rankings across 231 historical runs."""
    limit = max(1, min(int(limit), 50))
    rows = load_json("gsdi/gs_dominance_rankings.json")
    if player and player.strip():
        needle = player.strip().lower()
        rows = [r for r in rows if needle in str(r.get("player", "")).lower()]
    if tournament and tournament.strip():
        needle = tournament.strip().lower()
        rows = [r for r in rows if needle in str(r.get("tournament", "")).lower()]
    return {
        "total_matched": len(rows),
        "rankings": rows[:limit],
        "source": ATTRIBUTION_TML,
    }


def get_nail_biters(
    player: str | None = None,
    tournament: str | None = None,
    tag: str | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    """Query Nail-Biter Index (NBI) rankings across 687 Grand Slam Finals & Semifinals."""
    limit = max(1, min(int(limit), 50))
    rows = load_json("nbi/gs_nailbiters.json")
    if player and player.strip():
        needle = player.strip().lower()
        rows = [r for r in rows if needle in str(r.get("match", "")).lower()]
    if tournament and tournament.strip():
        needle = tournament.strip().lower()
        rows = [r for r in rows if needle in str(r.get("tourney", "")).lower()]
    if tag and tag.strip():
        needle = tag.strip().lower()
        rows = [r for r in rows if needle in str(r.get("drama_tags", "")).lower()]
    return {
        "total_matched": len(rows),
        "matches": rows[:limit],
        "source": ATTRIBUTION_TML,
    }


def get_greatness_race(player: str | None = None, age: float | None = None) -> dict[str, Any]:
    """Compare Big 3, Alcaraz, Sinner, and past legends at a given age or current milestones."""
    players_map = load_json("greatness/race_to_greatness.json").get("players", {})
    if player and player.strip():
        needle = player.strip().lower()
        selected = {k: v for k, v in players_map.items() if needle in k.lower()}
    else:
        selected = players_map

    out = []
    for name, payload in selected.items():
        snap = _trajectory_at_age(payload.get("trajectory", []), age)
        out.append({
            "player": name,
            "snapshot": snap,
            "current_stats": payload.get("current_stats"),
            "milestones": payload.get("milestones"),
        })
    return {
        "target_age": age,
        "count": len(out),
        "players": out,
        "source": ATTRIBUTION_TML,
    }


def get_young_guns_race(player: str | None = None, age: float | None = None) -> dict[str, Any]:
    """Track next-wave ATP prospects (Fonseca, Mensik, Tien, Jodar) vs Alcaraz & Sinner."""
    players_map = load_json("greatness/young_guns_race.json").get("players", {})
    if player and player.strip():
        needle = player.strip().lower()
        selected = {k: v for k, v in players_map.items() if needle in k.lower()}
    else:
        selected = players_map

    out = []
    for name, payload in selected.items():
        snap = _trajectory_at_age(payload.get("trajectory", []), age)
        out.append({
            "player": name,
            "snapshot": snap,
            "current_stats": payload.get("current_stats"),
            "milestones": payload.get("milestones"),
        })
    return {
        "target_age": age,
        "count": len(out),
        "players": out,
        "source": ATTRIBUTION_TML,
    }


def get_gs_breakthrough(player: str | None = None, limit: int = 25) -> dict[str, Any]:
    """Analyze how quickly Open Era Grand Slam champions won their first major title."""
    limit = max(1, min(int(limit), 60))
    rows = load_csv("gs-breakthrough/gs_breakthrough_comparison.csv")
    if player and player.strip():
        needle = player.strip().lower()
        rows = [r for r in rows if needle in r.get("Player_Name", "").lower()]
    return {
        "total_champions": len(rows),
        "champions": rows[:limit],
        "source": ATTRIBUTION_TML,
    }


def get_country_profile(country_code: str | None = None, year: int | None = None) -> dict[str, Any]:
    """Query global Top 100 / Top 10 ATP evolution by country IOC code and/or 5-year milestone."""
    profiles = load_json("globaltop100evolution/tennis_country_profiles.json")
    timeline = load_json("globaltop100evolution/global_timeline_dataset.json")

    if country_code and country_code.strip():
        code = country_code.strip().upper()
        entry = profiles.get(code)
        if not entry:
            return {"error": f"Country code {code!r} not found.", "available_count": len(profiles)}
        if year is not None:
            yr_str = str(int(year))
            return {
                "country": code,
                "year": yr_str,
                "stats": entry.get(yr_str),
                "available_years": sorted(entry.keys()),
                "source": ATTRIBUTION_TML,
            }
        return {"country": code, "timeline": entry, "source": ATTRIBUTION_TML}

    if year is not None:
        yr = int(year)
        yr_str = str(yr)
        matching_timeline = [row for row in timeline if row.get("year") == yr]
        country_ranks = [
            {"country": code, **stats[yr_str]}
            for code, stats in profiles.items()
            if yr_str in stats and (stats[yr_str].get("ever_in_top100", 0) > 0 or stats[yr_str].get("unique_atp_player", 0) > 0)
        ]
        country_ranks.sort(
            key=lambda x: (x.get("ever_in_top100", 0), x.get("unique_atp_player", 0)),
            reverse=True,
        )
        return {
            "year": yr,
            "global_summary": matching_timeline[0] if matching_timeline else None,
            "top_countries": country_ranks[:25],
            "source": ATTRIBUTION_TML,
        }

    return {"global_timeline": timeline, "source": ATTRIBUTION_TML}


def get_indian_tennis_stats(player: str | None = None) -> dict[str, Any]:
    """Query Open Era Indian ATP singles & milestone histories."""
    notable = load_json("indian/notable_players.json")
    all_players = load_json("indian/players_summary.json")

    if player and player.strip():
        needle = player.strip().lower()
        matches = [p for p in all_players if needle in str(p.get("name", "")).lower()]
        return {
            "count": len(matches),
            "players": matches[:15],
            "source": ATTRIBUTION_TML,
        }

    return {
        "total_indian_players": len(all_players),
        "notable_players": notable,
        "source": ATTRIBUTION_TML,
    }
