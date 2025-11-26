
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
from mcp.types import SamplingMessage, TextContent

mcp = FastMCP("sampling_demo", log_level="WARNING")

@mcp.tool()
async def smart_summary(text: str, ctx: Context[ServerSession, None]) -> str:
    """Generate an intelligent summary using LLM sampling.
    
    Args:
        text: Text to summarize
        ctx: Context object (automatically injected by FastMCP)
        
    Returns:
        LLM-generated summary
    """
    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"Summarize this in 2 sentences:\n\n{text}"
                )
            )
        ],
        max_tokens=100
    )
    
    if result.content.type == "text":
        return result.content.text
    return str(result.content)


@mcp.tool()
async def confirm_action(
    action: str, 
    details: str, 
    ctx: Context[ServerSession, None]
) -> str:
    """Ask LLM to confirm a potentially risky action.
    
    Args:
        action: The action to perform
        details: Details about what will happen
        ctx: Context object
        
    Returns:
        Confirmation result
    """
    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"⚠️ Confirm this action:\n\n"
                         f"Action: {action}\n"
                         f"Details: {details}\n\n"
                         f"Reply 'CONFIRM' to proceed or 'CANCEL' to abort."
                )
            )
        ],
        max_tokens=50
    )
    
    if result.content.type == "text":
        response = result.content.text.strip().upper()
        if "CONFIRM" in response:
            return f"✓ Action '{action}' confirmed and executed"
        else:
            return f"✗ Action '{action}' cancelled"
    return "✗ Unable to get confirmation"


@mcp.tool()
async def analyze_sentiment(text: str, ctx: Context[ServerSession, None]) -> str:
    """Analyze sentiment of text using LLM.
    
    Args:
        text: Text to analyze
        ctx: Context object
        
    Returns:
        Sentiment analysis result
    """
    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"Analyze the sentiment (positive/negative/neutral):\n\n{text}"
                )
            )
        ],
        max_tokens=50
    )
    
    if result.content.type == "text":
        return result.content.text
    return "Unable to analyze"


if __name__ == "__main__":
    mcp.run()
