import asyncio
import json

from mcp.shared.memory import create_connected_server_and_client_session

import check_release
import logistics_mcp as v1
import logistics_mcp_versioned as v
from config import VERSION


async def _run(server, fn):
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        return await fn(session)


def _tools(server) -> dict:
    async def go(s):
        return {t.name: t for t in (await s.list_tools()).tools}
    return asyncio.run(_run(server, go))


def test_version_resource_is_the_release():
    async def go(s):
        return (await s.read_resource("version://current")).contents[0].text
    assert asyncio.run(_run(v.mcp, go)) == VERSION == v.MCP_VERSION


def test_existing_tool_schemas_are_byte_identical_to_week6():
    old, new = _tools(v1.mcp), _tools(v.mcp)
    for name in old:
        assert new[name].inputSchema == old[name].inputSchema, name
        assert new[name].description == old[name].description, name


def test_versioned_server_only_adds_never_removes():
    assert set(_tools(v.mcp)) - set(_tools(v1.mcp)) == {"list_low_stock"}
    assert set(_tools(v1.mcp)) <= set(_tools(v.mcp))
    assert set(_tools(v1.mcp)) == {"check_stock", "plan_delivery_route", "get_delivery_eta"}


def test_list_low_stock_over_the_protocol():
    async def go(s):
        return await s.call_tool("list_low_stock", {"clinic_id": "c02"})
    body = json.loads(asyncio.run(_run(v.mcp, go)).content[0].text)
    assert body["clinic_id"] == "C02" and body["mcp_version"] == VERSION
    assert {r["item"] for r in body["low_stock"]} == {"amoxicillin", "malaria_kits"}


def test_list_low_stock_unknown_clinic_is_an_error_as_data():
    body = json.loads(v.list_low_stock("C99"))
    assert "error" in body and "C01" in body["valid_values"]


def test_release_is_aligned_everywhere(monkeypatch):
    monkeypatch.setattr("sys.argv", ["check_release.py"])
    monkeypatch.delenv("GITHUB_REF_TYPE", raising=False)
    assert check_release.main() == 0


def test_release_check_rejects_a_mismatched_tag(monkeypatch):
    monkeypatch.setattr("sys.argv", ["check_release.py", "--tag", "v0.0.1"])
    assert check_release.main() == 1
