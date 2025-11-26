from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
import asyncio

mcp = FastMCP("Context Demo")


@mcp.tool()
async def process_items(
    items: list[str], 
    ctx: Context[ServerSession, None]
) -> str:
    """Process multiple items with progress reporting.
    
    Args:
        items: List of items to process
        ctx: Context object
        
    Returns:
        Processing results
    """
    total = len(items)
    await ctx.info(f"Starting processing of {total} items")
    
    results = []
    for idx, item in enumerate(items, 1):
        # Report progress
        await ctx.report_progress(
            progress=idx / total,
            total=1.0,
            message=f"Processing item {idx}/{total}"
        )
        
        # Log debug info
        await ctx.debug(f"Processing: {item}")
        
        # Simulate work
        await asyncio.sleep(0.5)
        
        results.append(f"Processed: {item}")
    
    await ctx.info("Processing complete!")
    return "\n".join(results)

if __name__ == "__main__":
    mcp.run()
