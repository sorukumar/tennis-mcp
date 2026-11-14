"""End-to-end stdio MCP protocol test for tennis_mcp.server."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

LOCAL_TML_DATA = Path("/home/sorukumar/dev/github/tml-data/data")


async def _run_stdio_roundtrip() -> tuple[list[str], list[str], list[str], dict, dict]:
    env = dict(os.environ)
    env["TML_DATA_DIR"] = str(LOCAL_TML_DATA)

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tennis_mcp.server"],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            prompts = await session.list_prompts()

            tool_res = await session.call_tool(
                "get_head_to_head",
                {"player1": "Novak Djokovic", "player2": "Rafael Nadal", "include_matches": True, "match_limit": 2},
            )
            overview_res = await session.read_resource("tennis://overview")

            tool_payload = json.loads(tool_res.content[0].text)
            overview_payload = json.loads(overview_res.contents[0].text)
            return (
                [t.name for t in tools.tools],
                [str(r.uri) for r in resources.resources],
                [p.name for p in prompts.prompts],
                tool_payload,
                overview_payload,
            )


@pytest.mark.skipif(not LOCAL_TML_DATA.is_dir(), reason="Requires local tml-data checkout")
def test_mcp_stdio_protocol_roundtrip() -> None:
    tool_names, resource_uris, prompt_names, h2h_payload, overview_payload = asyncio.run(
        _run_stdio_roundtrip()
    )
    assert len(tool_names) >= 15
    assert "get_charting_profile" in tool_names
    assert "search_matches" in tool_names
    assert len(resource_uris) >= 7
    assert "tennis://overview" in resource_uris
    assert len(prompt_names) >= 3
    assert "scouting_report" in prompt_names
    assert h2h_payload["summary"]["total_matches"] >= 60
    assert overview_payload["total_matches"] >= 200000
