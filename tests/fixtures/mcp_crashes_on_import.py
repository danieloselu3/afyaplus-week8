"""A deliberately broken MCP server: dies before the handshake (e.g. a missing data file)."""
raise SystemExit("clinics.json not found")
