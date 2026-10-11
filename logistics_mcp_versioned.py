# logistics_mcp_versioned.py - the AfyaPlus logistics MCP server, versioned (Week 8).
#
# It REUSES the Week 6 server's functions (logistics_mcp.py, left untouched beside it)
# rather than copying them: check_stock, plan_delivery_route, get_delivery_eta and the
# clinics:// resources are the very same functions, so their schemas cannot drift.
# They are registered on this server's own FastMCP instance, so importing this module
# never changes the Week 6 server. This file adds only:
#   - version://current   the machine-readable pin (the MCP twin of /health)
#   - list_low_stock      one additive tool: existing agents can ignore it, so it is MINOR
# Run: python logistics_mcp_versioned.py   (stdio; the agent and the CI probe spawn it)
import json

from mcp.server.fastmcp import FastMCP

import logistics_mcp as v1
from config import VERSION
from logistics_mcp import REORDER_THRESHOLD, VALID_IDS, _clinic, error, logged

# Lockstep: the MCP server carries the platform release (config/triage.yaml `release`).
# The CHANGELOG says which releases actually changed the MCP contract.
MCP_VERSION = VERSION

mcp = FastMCP("afyaplus-logistics")
for _tool in (v1.check_stock, v1.plan_delivery_route, v1.get_delivery_eta):
    mcp.tool()(_tool)                                   # unchanged since MCP 1.0.0
mcp.resource("clinics://directory", mime_type="application/json")(v1.clinic_directory)
mcp.resource("clinics://{clinic_id}", mime_type="application/json")(v1.clinic_record)


@mcp.resource("version://current", mime_type="text/plain")
def version_current() -> str:
    """Semver of this MCP server. Agents and the CI health probe read this."""
    return MCP_VERSION


@mcp.tool()
@logged
def list_low_stock(clinic_id: str) -> str:
    """List the items at ONE clinic that are below the reorder threshold (10 units).

    Args:
        clinic_id: clinic id, e.g. "C02".

    Returns JSON {"clinic_id", "clinic", "reorder_threshold", "low_stock": [{"item", "units"}],
    "mcp_version"}. An empty low_stock list means nothing needs reordering there.
    Unknown id returns {"error": ..., "valid_values": [...]}.
    Added in 1.2.0; no existing tool schema changed.
    """
    clinic = _clinic(clinic_id)
    if clinic is None:
        return error(f"Unknown clinic id '{clinic_id}'.", valid_values=VALID_IDS)
    low = [{"item": item, "units": units} for item, units in clinic["stock"].items()
           if units < REORDER_THRESHOLD]
    return json.dumps({"clinic_id": clinic["id"], "clinic": clinic["name"],
                       "reorder_threshold": REORDER_THRESHOLD, "low_stock": low,
                       "mcp_version": MCP_VERSION})


if __name__ == "__main__":
    mcp.run()          # stdio transport: stdout is the protocol, logs go to stderr + file
