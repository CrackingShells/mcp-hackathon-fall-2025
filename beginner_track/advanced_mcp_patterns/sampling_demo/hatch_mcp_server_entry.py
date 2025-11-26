from hatch_mcp_server import HatchMCP
from mcp_server import mcp

hatch_mcp = HatchMCP("sampling_demo",
                     fast_mcp=mcp,
                     origin_citation="Origin citation for sampling_demo",
                     mcp_citation="MCP citation for sampling_demo")

if __name__ == "__main__":
    hatch_mcp.server.run()
