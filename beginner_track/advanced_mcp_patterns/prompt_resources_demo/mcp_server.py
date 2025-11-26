from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.prompts import base
from mcp.server.session import ServerSession

mcp = FastMCP("Research Assistant")


# Define a simple prompt (returns string)
@mcp.prompt(title="Paper Analysis Workflow")
def analysis_workflow(topic: str) -> str:
    """Provides step-by-step workflow for analyzing papers on a topic.
    
    Args:
        topic: Research topic to analyze
        
    Returns:
        Formatted workflow instructions
    """
    return f"""
# Paper Analysis Workflow: {topic}

Follow these steps to analyze papers on "{topic}":

## Step 1: Search (5 min)
- Search arXiv, PubMed, and Semantic Scholar
- Filter for papers from last 2 years
- Aim for 5-10 relevant papers

## Step 2: Initial Review (10 min)
- Read abstracts
- Identify 3-5 most relevant papers
- Note key methodologies mentioned

## Step 3: Deep Analysis (20 min)
For each selected paper:
- Extract research question
- Summarize methodology
- Note key findings and metrics
- Identify datasets used

## Step 4: Synthesis (10 min)
- Compare approaches across papers
- Identify trends and gaps
- Generate summary report

Use the available MCP tools to execute each step.
"""


# Define a prompt with structured messages
@mcp.prompt(title="Code Review Assistant")
def review_code(code: str, language: str = "python") -> list[base.Message]:
    """Generate a code review conversation.
    
    Args:
        code: Code to review
        language: Programming language
        
    Returns:
        List of messages for LLM interaction
    """
    return [
        base.UserMessage(f"Please review this {language} code:"),
        base.UserMessage(code),
        base.AssistantMessage("I'll review the code for:"),
        base.AssistantMessage("1. Correctness\n2. Style\n3. Performance\n4. Security"),
    ]


# Define a resource (static reference data)
@mcp.resource("research://statistics-reference")
def statistics_reference() -> str:
    """Common statistical tests reference for research papers."""
    return """
# Statistical Tests Quick Reference

## Comparing Two Groups
- **t-test**: Compare means of two groups (parametric)
- **Mann-Whitney U**: Compare two groups (non-parametric)
- **Chi-square**: Compare categorical distributions

## Comparing Multiple Groups
- **ANOVA**: Compare means of 3+ groups (parametric)
- **Kruskal-Wallis**: Compare 3+ groups (non-parametric)

## Relationships
- **Pearson correlation**: Linear relationship (parametric)
- **Spearman correlation**: Monotonic relationship (non-parametric)
- **Linear regression**: Predict continuous outcome

## Effect Sizes
- **Cohen's d**: Standardized difference between means
- **R²**: Proportion of variance explained
- **Odds ratio**: Association strength (categorical)

## Significance Levels
- p < 0.05: Statistically significant
- p < 0.01: Highly significant
- p < 0.001: Very highly significant

Always report both p-values and effect sizes!
"""


# Tool that uses a resource
@mcp.tool()
async def analyze_paper_statistics(
    paper_text: str, 
    ctx: Context[ServerSession, None]
) -> str:
    """Analyze statistical methods used in a paper.
    
    Args:
        paper_text: Full text or excerpt from paper
        ctx: Context object
        
    Returns:
        Analysis of statistical methods
    """
    # Read the statistics reference resource
    stats_ref = await ctx.read_resource("research://statistics-reference")
    
    # Use sampling to identify stats tests in the paper
    result = await ctx.session.create_message(
        messages=[
            base.UserMessage(
                f"Given this reference:\n\n{stats_ref}\n\n"
                f"Identify which statistical tests are used in this paper:\n\n{paper_text}"
            )
        ],
        max_tokens=200
    )
    
    if result.content.type == "text":
        return result.content.text
    return "Unable to analyze statistics"


if __name__ == "__main__":
    mcp.run()
