# Part 4: Advanced MCP Server Patterns with FastMCP

**Duration:** 45-60 minutes  
**Goal:** Learn essential FastMCP patterns for building production-ready MCP servers

**Prerequisites:** Completed Part 3 (basic MCP server creation via Hatch)

**Official Documentation:** [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

---

## Pattern 1: Server-Side LLM Sampling (15 min)

### What is Sampling?

**Sampling** allows your MCP tool to request LLM assistance during execution. Your tool can ask the LLM to:
- Generate summaries or creative content
- Make intelligent decisions based on data
- Analyze sentiment or classify text
- Validate information before taking action

### Basic Sampling Example

```python
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
from mcp.types import SamplingMessage, TextContent

mcp = FastMCP("Sampling Demo")

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
```

### Key Concepts

1. **Context Parameter**: Add `ctx: Context[ServerSession, None]` to access sampling
2. **create_message()**: Method to request LLM assistance
3. **SamplingMessage**: Structure for messages sent to LLM
4. **max_tokens**: Limit response length

### Exercise: Interactive Paper Selection

<details>
<summary>Challenge (5 min)</summary>

Create a tool that:
1. Takes a list of paper titles as input
2. Uses sampling to ask which paper to analyze first
3. Returns the selected paper title

</details>

<details>
<summary>A solution</summary>

```python
@mcp.tool()
async def select_paper(
    paper_titles: list[str], 
    ctx: Context[ServerSession, None]
) -> str:
    """Ask LLM to select the most relevant paper."""
    papers_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(paper_titles)])
    
    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"Which paper should we analyze first?\n\n{papers_text}\n\n"
                         f"Reply with just the number (1-{len(paper_titles)})."
                )
            )
        ],
        max_tokens=10
    )
    
    if result.content.type == "text":
        try:
            idx = int(result.content.text.strip()) - 1
            if 0 <= idx < len(paper_titles):
                return paper_titles[idx]
        except ValueError:
            pass
    
    return paper_titles[0]  # Default to first
```

</details>

---

## Pattern 2: Prompts and Resources (15 min)

### Prompts: Templates for LLM Interaction

Prompts provide pre-written templates that guide LLMs on how to use your tools effectively.

### Resources: Reference Materials

Resources expose static or dynamic data that tools can reference.

### Implementation

```python
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
```

### Key Concepts

1. **@mcp.prompt()**: Decorator to define prompt templates
2. **@mcp.resource(uri)**: Decorator to expose resources at a URI
3. **base.Message**: Structured messages for prompts
4. **ctx.read_resource()**: Read resources from within tools

### Exercise: Create Domain Prompt

<details>
<summary>Challenge (5 min)</summary>

Create a prompt template for "drug discovery paper analysis" that includes:
- Key pharmacological metrics to extract
- Standard analysis workflow
- Safety considerations

</details>

<details>
<summary>A solution</summary>

```python
@mcp.prompt(title="Drug Discovery Analysis")
def drug_discovery_workflow(compound_name: str = "the compound") -> str:
    """Workflow for analyzing drug discovery papers."""
    return f"""
# Drug Discovery Paper Analysis: {compound_name}

## Pharmacological Data to Extract
- IC50/EC50 values (potency)
- Binding affinity (Kd)
- Selectivity ratios
- ADMET properties

## Analysis Steps
1. Identify target protein/pathway
2. Extract efficacy data
3. Review toxicity results
4. Compare to existing drugs
5. Note clinical trial status

## Safety Considerations
Always document:
- In vitro toxicity
- In vivo toxicity (animal models)
- Known side effects
- Drug-drug interactions

## Reference Databases
- PubChem: Chemical structures
- ChEMBL: Bioactivity data
- DrugBank: Drug information
"""
```

</details>

---

## Pattern 3: Context Capabilities (10 min)

### Logging and Progress Reporting

The Context object provides methods for communication beyond just sampling.

```python
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
```

### Available Context Methods

- `await ctx.info(message)`: Info log
- `await ctx.debug(message)`: Debug log
- `await ctx.warning(message)`: Warning log
- `await ctx.error(message)`: Error log
- `await ctx.report_progress(progress, total, message)`: Progress update
- `await ctx.read_resource(uri)`: Read a resource
- `ctx.session.create_message()`: Sample LLM
- `await ctx.session.send_resource_list_changed()`: Notify resource changes

---

## Pattern 4: Error Handling (10 min)

```python
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
from typing import Optional

mcp = FastMCP("Error Handling Demo")


class ValidationError(Exception):
    """Custom validation error."""
    pass


@mcp.tool()
async def divide(a: float, b: float, ctx: Context[ServerSession, None]) -> dict:
    """Divide two numbers with error handling.
    
    Args:
        a: Numerator
        b: Denominator
        ctx: Context object
        
    Returns:
        Result or error information
    """
    try:
        await ctx.debug(f"Dividing {a} by {b}")
        
        if b == 0:
            await ctx.error("Division by zero attempted")
            return {
                "success": False,
                "error": "Cannot divide by zero",
                "result": None
            }
        
        result = a / b
        await ctx.info(f"Result: {result}")
        
        return {
            "success": True,
            "error": None,
            "result": result
        }
        
    except Exception as e:
        await ctx.error(f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "error": f"Unexpected error: {type(e).__name__}",
            "result": None
        }

if __name__ == "__main__":
    mcp.run()
```

### Best Practices

1. **Return structured data**: Use dicts with `success`, `error`, `result` fields
2. **Use custom exceptions**: Define domain-specific error types
3. **Log at appropriate levels**: debug, info, warning, error
4. **Validate early**: Check inputs before processing
5. **Handle specific exceptions**: Catch specific types before generic Exception

## Quick Reference

### FastMCP Decorators

```python
@mcp.tool()                          # Define a tool
@mcp.prompt(title="Name")            # Define a prompt
@mcp.resource("scheme://path")       # Define a resource
```

### Context Methods

```python
# Sampling
await ctx.session.create_message(messages=[...], max_tokens=100)

# Logging
await ctx.debug("Debug message")
await ctx.info("Info message")
await ctx.warning("Warning message")
await ctx.error("Error message")

# Progress
await ctx.report_progress(progress, total, message)

# Resources
await ctx.read_resource("scheme://path")

# Notifications
await ctx.session.send_resource_list_changed()
```

### Running Your Server

```python
if __name__ == "__main__":
    mcp.run()  # Defaults to stdio transport
```

---

**Questions?** Ask your instructor or check the official documentation!
