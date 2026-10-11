"""MCP health gate (Route A): a real client handshake over stdio, not a port check.

    python scripts/check_mcp_health.py                       # probe logistics_mcp_versioned.py
    python scripts/check_mcp_health.py --server some_server.py

Healthy means ALL of:
  1. the server starts and completes the MCP initialize handshake (within TIMEOUT_S)
  2. list_tools includes every tool the logistics agent calls (REQUIRED_TOOLS)
  3. version://current equals the platform release in config/triage.yaml
  4. one real call, check_stock("ors_sachets"), returns stock for every clinic with integer units
Any failure, including a crash or a timeout, is exit 1, so the deploy job never starts.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_TOOLS = {"check_stock", "plan_delivery_route", "get_delivery_eta"}   # what agent.py uses
EXPECTED_CLINICS = 5
TIMEOUT_S = 30


async def probe(server: Path, expected_version: str) -> list[str]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=[str(server)], cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = {t.name for t in (await session.list_tools()).tools}
            version = (await session.read_resource("version://current")).contents[0].text
            payload = None
            if "check_stock" in tools:
                result = await session.call_tool("check_stock", {"item": "ors_sachets"})
                payload = json.loads(result.content[0].text)
    print(f"server={init.serverInfo.name} tools={sorted(tools)} version={version}")

    problems = []
    if missing := REQUIRED_TOOLS - tools:
        problems.append(f"missing required tools {sorted(missing)}")
    if version != expected_version:
        problems.append(f"version://current is {version}, release is {expected_version}")
    stock = (payload or {}).get("stock", [])
    if payload is None:
        problems.append("check_stock could not be called")
    elif "error" in payload or len(stock) != EXPECTED_CLINICS \
            or not all(isinstance(row.get("units"), int) for row in stock):
        problems.append(f"check_stock returned an unusable answer: {str(payload)[:160]}")
    else:
        print(f"check_stock(ors_sachets): {len(stock)} clinics, "
              f"{sum(r['reorder_needed'] for r in stock)} need a reorder")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default=str(ROOT / "logistics_mcp_versioned.py"))
    args = ap.parse_args()
    release = str(yaml.safe_load((ROOT / "config" / "triage.yaml").read_text())["release"])
    try:
        problems = asyncio.run(asyncio.wait_for(probe(Path(args.server), release), TIMEOUT_S))
    except Exception as exc:          # crash on import, bad handshake, timeout: all unhealthy
        cause = exc
        while getattr(cause, "exceptions", None):          # anyio nests errors in groups
            cause = cause.exceptions[0]
        problems = [f"probe failed before a healthy handshake: {type(cause).__name__}: {cause}"]
    if problems:
        print("MCP HEALTH FAILED")
        for p in problems:
            print("  -", p)
        return 1
    print("MCP health OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
