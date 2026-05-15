"""MCP server — expose fhir-synth as Claude tools."""

from fhir_synth.mcp.server import main, mcp

__all__ = ["main", "mcp"]
