from hatch_mcp_server import HatchMCP
from mcp_server import mcp

hatch_mcp = HatchMCP("prompt_resources_demo",
                     fast_mcp=mcp,
                     origin_citation="Origin citation for prompt_resources_demo",
                     mcp_citation="MCP citation for prompt_resources_demo")

if __name__ == "__main__":
    hatch_mcp.server.run()
