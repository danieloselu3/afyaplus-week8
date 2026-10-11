"""A deliberately broken MCP server for the health-gate test: check_stock was renamed
to stock_check without a major version bump (the breaking change Monday's Lab 2 drafts)."""
import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("afyaplus-logistics-broken")


@mcp.resource("version://current", mime_type="text/plain")
def version_current() -> str:
    return "1.2.0"


@mcp.tool()
def stock_check(item: str) -> str:
    return json.dumps({"item": item, "stock": []})


@mcp.tool()
def plan_delivery_route(start_clinic_id: str) -> str:
    return "{}"


@mcp.tool()
def get_delivery_eta(from_clinic_id: str, to_clinic_id: str) -> str:
    return "{}"


if __name__ == "__main__":
    mcp.run()
