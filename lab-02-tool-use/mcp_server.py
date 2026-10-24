"""Lab 2 Stretch - serve the invoice tools over the Model Context Protocol (MCP).

Any MCP-capable application (an agent framework, an IDE, a desktop assistant) can
start this file and use the tools, without importing our Python code:

    uv run python lab-02-tool-use/mcp_server.py      # speaks MCP on stdin/stdout

You normally do not run it by hand; an MCP client starts it as a child process.
See part 7 of the notebook.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from agentlab.invoices import check_invoice_total, compare_with_po, read_invoice, record_result

server = FastMCP("invoices", log_level="WARNING")  # quiet: no line per request

# Re-use the LangChain tools: the MCP tool gets the same name and description the model saw in the lab.
for lc_tool in (read_invoice, check_invoice_total, compare_with_po, record_result):
    server.add_tool(lc_tool.func, name=lc_tool.name, description=lc_tool.description)

if __name__ == "__main__":
    server.run()  # stdio transport
