# Part 2: Scientific Knowledge Extraction with MCP

**Duration:** 45-60 minutes  
**Goal:** Extract and structure core scientific knowledge from research papers using MCP servers

**Key Focus:** Extracting scientific concepts, mechanisms, findings, and relationships—not just paper metadata

---

## Prerequisites

- MCP host configured (Claude Desktop, Cursor, or similar)
- Basic understanding of MCP concepts from Part 1
- Internet connection for paper search APIs

---

## Phase 1: Server Installation (10 min)

### Create environment
**using mamba**

```bash
mamba create -n forMCPHackathonFall python=3.13
mamba activate forMCPHackathonFall
```
**or using uv**
```bash
uv venv --python 3.13 forMCPHackathonFall
source forMCPHackathonFall/bin/activate
```

### Install Paper Search MCP

```bash
# Install via pip
pip install paper-search-mcp
```

**Verify Installation by running it**
```bash
python -m paper_search_mcp.server
```

### Install ArangoDB MCP Server

```bash
pip install mcp-arangodb-async
```
**Put our preconfigured .env file in your environment folder**
The file is called `.env.example`. Rename it to `.env`. 

**Start ArangoDB container (required for database operations)**
**Using docker run (on Linux, don't forget sudo)**
```bash
docker run -d --env-file .env --name mcp_arangodb_test -p 8529:8529 arangodb
```
**Wait 10-15 seconds for container to be healthy and check (on Linux, don't forget sudo)**
```bash
docker ps
```
**You can also now log in with root & the root password in .env**
http://localhost:8529

### Configure ArangoDB (add our database etc.)

After the container is healthy, initialize the database with a user account:

**For Linux/macOS (bash):**
```bash
chmod +x beginner_track/arangodb_util/setup-arango.sh
./beginner_track/arangodb_util/setup-arango.sh --seed
```

**For Windows (PowerShell):**
```powershell
.\beginner_track\arangodb_util\setup-arango.ps1 -Seed
```

This script:
- Creates database `mcp_arangodb_test`
- Creates user `mcp_arangodb_user` with password `mcp_arangodb_password`
- Optionally seeds sample data with `-Seed` flag
- Grants read/write permissions

### Verify Setup

```bash
python -m mcp_arangodb_async --health
```
**or with uv**
```bash
uv run -m mcp_arangodb_async --health
```

**Expected output:**
```json
{"ok": true, "db": "mcp_arangodb_test", "user": "mcp_arangodb_user"}
```

**Access Web UI:**
- URL: http://localhost:8529
- Login: root / changeme

---

## Phase 2: Configure MCP Servers (5 min)

### Using Hatch for Configuration

Hatch provides seamless MCP server configuration. After installing both servers and initializing the database:

```bash
# Discover available MCP hosts on your system
hatch mcp discover hosts
```

```bash
# Configure paper-search-mcp for your host (e.g., Claude Desktop)
hatch mcp configure paper-search-mcp \
  --host claude-desktop \
  --command "mamba" \
  --args "run -n forMCPHackathonFall python -m paper_search_mcp.server"
```

```bash
# Configure ArangoDB MCP server (use credentials from setup script)
hatch mcp configure mcp-arangodb-async \
--host claude-desktop \
--command "mamba" \
--args "run -n forMCPHackathonFall python -m mcp_arangodb_async server" \
--env-var ARANGO_URL=http://localhost:8529 \
--env-var ARANGO_DB=mcp_arangodb_test \
--env-var ARANGO_USERNAME=mcp_arangodb_user \
--env-var ARANGO_PASSWORD=mcp_arangodb_password
```

**Manual Configuration Alternative:**

Edit your MCP host configuration file (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "paper-search": {
      "command": "python",
      "args": ["-m", "paper_search_mcp.server"]
    },
    "arangodb": {
      "command": "python",
      "args": ["-m", "mcp_arangodb_async"],
      "env": {
        "ARANGO_URL": "http://localhost:8529",
        "ARANGO_DB": "mcp_arangodb_test",
        "ARANGO_USERNAME": "mcp_arangodb_user",
        "ARANGO_PASSWORD": "mcp_arangodb_password"
      }
    }
  }
}
```

**Restart your MCP host** after configuration.

### Verify MCP Tools Available

Prompt your MCP host:
```
List all available MCP tools from paper-search and arangodb servers
```

You should see tools for paper search (from arXiv, PubMed, Semantic Scholar, etc.) and database operations.

---

## Phase 3: Scientific Knowledge Extraction Workflow (30-45 min)

### Overview: Template-Based Approach

All prompts below use **placeholders** that you can customize:
- `{RESEARCH_TOPIC}`: Your specific research question
- `{KEY_CONCEPTS}`: Main scientific concepts to focus on
- `{MECHANISM}`: Biological/chemical/physical mechanism of interest
- `{TIMEFRAME}`: Temporal aspect (e.g., "first 14 days")
- `{ORGANISM}`: Model organism or system

**Example Instance:** We'll show how these templates work using:
- **Topic:** "How does Wnt/β-catenin signaling regulate blastema formation during the first 14 days post-amputation in axolotl limb regeneration?"

---

### Level 1: Find Relevant Papers (5 min)

**Goal:** Search for papers containing your scientific concepts

**Prompt Template:**
```
Search for recent papers on {RESEARCH_TOPIC} using arXiv, PubMed, and Semantic Scholar.

Focus on papers that discuss:
- {KEY_CONCEPTS}
- {MECHANISM}
- {TIMEFRAME} (if time-dependent)

Find 5-10 papers from the last 5 years. For each paper, I only need:
- Paper ID (for retrieval)
- Title
- Brief abstract excerpt showing relevance

Skip papers that only mention these topics tangentially.
```

**Specific Instance:**
```
Search for recent papers on "Wnt/β-catenin signaling in axolotl limb regeneration" using arXiv, PubMed, and Semantic Scholar.

Focus on papers that discuss:
- Wnt signaling pathway activation
- β-catenin nuclear translocation
- Blastema formation and cell proliferation
- Timeline of events in first 14 days post-amputation

Find 5-10 papers from the last 5 years. For each paper, I only need:
- Paper ID (for retrieval)
- Title
- Brief abstract excerpt showing relevance

Skip papers that only mention these topics tangentially.
```

**What's Happening:**
- MCP searches multiple databases efficiently
- LLM filters for scientific relevance (not just keyword matching)
- Returns minimal metadata needed for next step

---

### Level 2: Extract Core Scientific Knowledge (10 min)

**Goal:** Extract the actual science, not bibliographic data

**Prompt Template:**
```
From the top 3-5 papers found, extract ONLY the core scientific knowledge:

For {RESEARCH_TOPIC}, extract:

1. **Mechanistic Details:**
   - What molecular/cellular processes are involved in {MECHANISM}?
   - What are the key proteins/genes/molecules mentioned?
   - What are the cause-effect relationships?

2. **Temporal Dynamics:** (if relevant)
   - What happens at different time points during {TIMEFRAME}?
   - What is the sequence of events?
   - What are critical time windows?

3. **Experimental Evidence:**
   - What experimental methods were used to demonstrate this?
   - What were the key quantitative findings (with values/statistics)?
   - What controls or comparisons were made?

4. **Biological Context:**
   - What cell types are involved?
   - What tissue/organ/system context?
   - How does {ORGANISM} differ from other systems?

DO NOT extract: author names, publication years, citation counts, journal names, affiliations.

Format as structured knowledge, not as "Paper X says..." but as integrated facts.
```

**Specific Instance:**
```
From the top 3-5 papers found, extract ONLY the core scientific knowledge:

For Wnt/β-catenin signaling regulation of blastema formation in axolotls, extract:

1. **Mechanistic Details:**
   - What molecular/cellular processes are involved in Wnt/β-catenin activation during regeneration?
   - What are the key proteins/genes/molecules (Wnts, Frizzled receptors, β-catenin, TCF/LEF transcription factors)?
   - What are the cause-effect relationships (signal → receptor → β-catenin stabilization → gene expression)?

2. **Temporal Dynamics:**
   - What happens at different time points during the first 14 days post-amputation?
   - What is the sequence of events (wound healing → dedifferentiation → blastema formation → proliferation)?
   - What are critical time windows (when does peak Wnt signaling occur)?

3. **Experimental Evidence:**
   - What experimental methods were used (immunostaining, qPCR, Wnt inhibitors, β-catenin reporters)?
   - What were the key quantitative findings (fold-change in gene expression, cell proliferation rates, blastema size)?
   - What controls or comparisons were made (inhibitor-treated vs. control, different time points)?

4. **Biological Context:**
   - What cell types are involved (dedifferentiated fibroblasts, muscle cells, epithelial cells)?
   - What tissue context (limb stump, wound epithelium, blastema mesenchyme)?
   - How does axolotl regeneration differ from mammals?

DO NOT extract: author names, publication years, citation counts, journal names, affiliations.

Format as structured knowledge, not as "Paper X says..." but as integrated facts.
```

**What's Happening:**
- LLM reads full paper text via MCP
- Extracts scientific facts, not metadata
- Integrates information across papers
- Structures knowledge for database storage

---

### Level 3: Structure Knowledge in Database (10 min)

**Goal:** Store scientific knowledge (not paper metadata) in ArangoDB

**Prompt Template:**
```
Using ArangoDB, create a scientific knowledge base:

1. Create collections for SCIENTIFIC ENTITIES (not papers):
   - "biological_processes" - mechanisms like {MECHANISM}
   - "molecules" - proteins, genes, compounds
   - "temporal_events" - time-dependent processes
   - "experimental_findings" - quantitative results
   - "cell_types" - relevant cell populations

2. For the knowledge extracted about {RESEARCH_TOPIC}, insert documents like:

   **Biological Process:**
   - process_name: descriptive name
   - mechanism: detailed mechanism description
   - components: array of molecules involved
   - context: organism/tissue/condition
   - evidence_strength: high/medium/low

   **Molecule:**
   - molecule_name: official name/symbol
   - molecule_type: protein/gene/compound
   - role: function in the process
   - expression_pattern: where/when expressed
   
   **Temporal Event:**
   - event_name: what happens
   - timepoint: when it occurs in {TIMEFRAME}
   - duration: how long it lasts
   - triggers: what initiates it
   - outcomes: what it causes

   **Experimental Finding:**
   - measurement_type: what was measured
   - value: quantitative result
   - method: experimental technique used
   - context: conditions/system
   - statistical_significance: p-value if available

3. Create indexes on: molecule_name, process_name, timepoint

Show statistics on how many biological entities vs. how many papers.
```

**Specific Instance:**
````
Using ArangoDB, create a scientific knowledge base for axolotl limb regeneration:

1. Create collections for SCIENTIFIC ENTITIES:
   - "biological_processes" - e.g., blastema formation, dedifferentiation
   - "molecules" - e.g., Wnt3a, β-catenin, Axin2, TCF7L2
   - "temporal_events" - e.g., wound healing, early proliferation
   - "experimental_findings" - e.g., β-catenin levels, proliferation rates
   - "cell_types" - e.g., dedifferentiated fibroblasts, blastema cells

2. Insert documents for Wnt/β-catenin regulation of blastema formation:

   **Biological Process Example:**
   ```json
   {
     "process_name": "Wnt_signaling_activation_in_blastema",
     "mechanism": "Wnt ligands bind Frizzled receptors, inhibiting β-catenin degradation complex, allowing β-catenin nuclear translocation and TCF/LEF-mediated transcription",
     "components": ["Wnt3a", "Wnt5a", "β-catenin", "TCF7L2", "LEF1"],
     "context": "axolotl_limb_blastema_days_3_14",
     "evidence_strength": "high"
   }
   ```

   **Temporal Event Example:**
   ```json
   {
     "event_name": "peak_beta_catenin_nuclear_localization",
     "timepoint": "day_7_post_amputation",
     "duration": "3_days",
     "triggers": ["Wnt3a_upregulation", "wound_epithelium_formation"],
     "outcomes": ["increased_cell_proliferation", "blastema_expansion"]
   }
   ```

   **Experimental Finding Example:**
   ```json
   {
     "measurement_type": "blastema_cell_proliferation_rate",
     "value": "65%_BrdU_positive_cells",
     "method": "BrdU_incorporation_assay",
     "context": "day_7_wildtype_blastema",
     "statistical_significance": "p<0.001"
   }
   ```

3. Create indexes on: molecule_name, process_name, timepoint

Show statistics: How many distinct molecules, processes, and events vs. how many source papers.
````

**What's Happening:**
- Database stores SCIENCE, not paper metadata
- Each document represents a biological fact
- Papers are source references, not primary entities
- Enables querying by scientific concept, not by author

**Exercise:** Add a "contradictions" collection for conflicting findings across papers.

---

### Level 4: Build Scientific Knowledge Graph (15 min)

**Goal:** Connect biological entities through mechanistic relationships

**Prompt Template:**
```
Build a SCIENTIFIC knowledge graph in ArangoDB for {RESEARCH_TOPIC}:

1. Create vertex collections (already created in Level 3):
   - biological_processes
   - molecules
   - temporal_events
   - experimental_findings
   - cell_types

2. Create MECHANISTIC edge collections:
   - "regulates" (molecule → process)
     - properties: regulation_type (activates/inhibits), mechanism
   
   - "involves" (process → molecule)
     - properties: role (substrate/enzyme/cofactor/regulator)
   
   - "occurs_in" (process → cell_type)
     - properties: spatial_location, abundance
   
   - "precedes" (event → event)
     - properties: time_gap, dependency_type (required/facilitative)
   
   - "produces" (process → molecule)
     - properties: amount, timepoint
   
   - "supports_finding" (finding → process)
     - properties: evidence_type, strength

3. Populate edges by extracting relationships from {RESEARCH_TOPIC} knowledge:
   - WHO regulates WHAT (molecule-process relationships)
   - WHAT requires WHAT (process dependencies)
   - WHEN leads to WHEN (temporal causality)
   - WHAT produces WHAT (biochemical reactions)

4. Add quantitative edge properties when available:
   - fold_change, IC50, Kd, expression_level, etc.

The graph should answer:
- What regulates {MECHANISM}?
- What happens before/after {KEY_CONCEPTS}?
- What molecules are necessary vs. sufficient?
- How do {TIMEFRAME} events relate?

Show graph statistics: edge counts by type, top 10 most connected molecules.
```

**Specific Instance:**
````
Build a SCIENTIFIC knowledge graph for Wnt/β-catenin regulation of axolotl blastema formation:

1. Using collections created in Level 3

2. Create MECHANISTIC edge collections with relationships like:

   **regulates edges:**
   ```json
   {
     "_from": "molecules/Wnt3a",
     "_to": "biological_processes/blastema_formation",
     "regulation_type": "activates",
     "mechanism": "stabilizes_beta_catenin",
     "timepoint": "days_3_7",
     "fold_change": 2.5
   }
   ```

   **precedes edges:**
   ```json
   {
     "_from": "temporal_events/wound_epithelium_formation",
     "_to": "temporal_events/blastema_cell_proliferation",
     "time_gap": "2_days",
     "dependency_type": "required",
     "evidence": "surgical_removal_blocks_regeneration"
   }
   ```

   **involves edges:**
   ```json
   {
     "_from": "biological_processes/Wnt_signaling_cascade",
     "_to": "molecules/beta_catenin",
     "role": "transcriptional_coactivator",
     "cellular_location": "nucleus",
     "peak_timepoint": "day_7"
   }
   ```

   **supports_finding edges:**
   ```json
   {
     "_from": "experimental_findings/IWR1_treatment_reduces_blastema_size",
     "_to": "biological_processes/Wnt_dependent_proliferation",
     "evidence_type": "pharmacological_inhibition",
     "strength": "high_p_0.001"
   }
   ```

3. Extract relationships answering:
   - What Wnt ligands activate β-catenin signaling?
   - What downstream genes does β-catenin/TCF regulate?
   - What processes require Wnt signaling (vs. just correlate)?
   - How does day 3 signaling lead to day 7 proliferation?

4. Include quantitative properties:
   - Wnt3a expression fold-change: 3.2x at day 5
   - β-catenin target genes: Axin2 (4.5x), Lef1 (2.8x)
   - Proliferation index: 45% → 65% when Wnt active

Show: 
- Total edges by type
- Top 5 molecules by connectivity (hub molecules)
- Critical temporal dependencies
````

**What's Happening:**
- Graph represents BIOLOGY, not bibliography
- Edges are mechanistic relationships, not co-citations
- Enables scientific reasoning: "If I inhibit X, what happens to Y?"
- Temporal edges reveal causal sequences
- Quantitative properties enable modeling

**Key Pattern:** This is a **mechanistic knowledge graph**, not a citation network.

---

### Level 5: Query Scientific Insights (10 min)

**Goal:** Answer biological questions using the knowledge graph

**Prompt Template:**
````
Using ArangoDB graph traversals, answer scientific questions about {RESEARCH_TOPIC}:

1. **Regulatory Network Analysis:**
   - What molecules regulate {MECHANISM}?
   - What processes does {KEY_MOLECULE} influence?
   - Find all paths: molecule → process → outcome

2. **Temporal Causality:**
   - What events must occur before {KEY_EVENT}?
   - What is the longest causal chain during {TIMEFRAME}?
   - Identify rate-limiting steps (bottleneck events)

3. **Mechanistic Dependencies:**
   - What molecules are REQUIRED for {PROCESS}? (inhibition blocks it)
   - What molecules are SUFFICIENT? (addition induces it)
   - Find feedback loops and self-regulation

4. **Evidence Strength:**
   - Which processes have the most experimental support?
   - What findings contradict each other?
   - Where are knowledge gaps (processes with no mechanisms)?

For each query:
- Write the AQL graph traversal query
- Execute it
- Interpret biological significance

Generate insights:
- Rank molecules by regulatory importance (connectivity)
- Identify critical time windows (most events/dependencies)
- Highlight under-studied connections (few supporting findings)
- Suggest experiments to test predictions
````

**Specific Instance:**
````
Using ArangoDB graph traversals, answer questions about Wnt/β-catenin in axolotl regeneration:

1. **Regulatory Network Analysis:**
   - What molecules regulate blastema formation? (traverse regulates edges)
   - What processes does β-catenin influence? (traverse β-catenin → processes)
   - Find paths: Wnt3a → β-catenin → TCF/LEF → target genes → proliferation

2. **Temporal Causality:**
   - What events must occur before blastema cell proliferation starts?
   - What is the longest causal chain from amputation (day 0) to peak proliferation (day 7)?
   - Identify bottlenecks: Is wound epithelium formation rate-limiting?

3. **Mechanistic Dependencies:**
   - What molecules are REQUIRED for blastema formation?
     Query: Find molecules where inhibition → failed regeneration findings
   - What molecules are SUFFICIENT to accelerate regeneration?
     Query: Find molecules where addition → enhanced proliferation findings
   - Find feedback: Does blastema produce factors that regulate Wnt signaling?

4. **Evidence Strength:**
   - Which processes have 3+ supporting experimental findings?
   - What findings conflict? (e.g., different Wnt inhibitor effects)
   - Where are gaps? (processes with no identified mechanism)

Example AQL Queries:

```aql
// Find all molecules that regulate blastema formation
FOR molecule IN molecules
  FOR edge IN regulates
    FILTER edge._from == molecule._id
    FOR process IN biological_processes
      FILTER edge._to == process._id
      FILTER process.process_name =~ "blastema"
      RETURN {
        molecule: molecule.molecule_name,
        regulation: edge.regulation_type,
        process: process.process_name,
        timepoint: edge.timepoint
      }

// Find temporal sequence: what precedes what?
FOR event IN temporal_events
  FILTER event.timepoint == "day_3_post_amputation"
  FOR v, e, p IN 1..3 OUTBOUND event precedes
    RETURN {
      path: p.vertices[*].event_name,
      time_gaps: p.edges[*].time_gap
    }

// Find hub molecules (most connections)
FOR molecule IN molecules
  LET outgoing = LENGTH(FOR v IN 1..1 OUTBOUND molecule regulates, involves, produces RETURN 1)
  SORT outgoing DESC
  LIMIT 5
  RETURN {
    molecule: molecule.molecule_name,
    connections: outgoing,
    roles: molecule.role
  }
```

Generate insights:
- **Rank regulatory importance:** β-catenin (12 connections), Wnt3a (8), TCF7L2 (6)
- **Critical time window:** Days 5-7 (peak signaling + proliferation)
- **Under-studied:** What terminates Wnt signaling after day 10?
- **Suggested experiment:** Test if blocking Wnt at day 8 affects later differentiation
````

**What's Happening:**
- Queries answer "why" and "how," not just "what"
- Graph traversals reveal causal chains
- Identify key regulatory nodes (druggable targets)
- Find knowledge gaps to direct future research
- Generate testable hypotheses

**Exercise:** Query for feedback loops—molecules that regulate their own regulators.

---

## Key Learning Outcomes

✅ **Scientific Focus:** Extract KNOWLEDGE (mechanisms, findings) not METADATA (authors, citations)  
✅ **Template-Based Workflow:** Reusable prompts with placeholders for any research topic  
✅ **Knowledge Graphs:** Model biology as connected entities (molecules, processes, events)  
✅ **Mechanistic Reasoning:** Edges represent regulatory/causal relationships, not co-occurrence  
✅ **Agentic Workflow:** LLM orchestrates multi-step extraction and integration  
✅ **Tool Integration:** MCP servers (paper-search + ArangoDB) work together seamlessly

---

## Adapting Templates to Your Research

**To use these templates for your own topic:**

1. **Define your placeholders:**
   - What is your {RESEARCH_TOPIC}?
   - What are your {KEY_CONCEPTS}?
   - What {MECHANISM} are you studying?
   - Is there a {TIMEFRAME}?
   - What {ORGANISM} or system?

2. **Customize entity types:**
   - Biology: molecules, processes, pathways, cell types
   - Chemistry: compounds, reactions, conditions, products
   - Physics: particles, forces, interactions, states
   - CS: algorithms, architectures, datasets, metrics

3. **Define relationship types:**
   - Biology: regulates, activates, inhibits, binds
   - Chemistry: catalyzes, produces, requires
   - Physics: interacts_with, causes, constrains
   - CS: uses, improves, outperforms

4. **Replace the example:**
   - Substitute "Wnt/β-catenin" with your pathway
   - Substitute "blastema formation" with your process
   - Keep the same workflow structure

---

## Troubleshooting

### Low-Quality Knowledge Extraction
**Problem:** LLM extracts author names instead of mechanisms
**Solution:** 
- Emphasize "DO NOT extract author names, years, citations" in prompts
- Ask explicitly: "What is the MECHANISM? What molecules DO what?"
- Use negative examples: "Not 'Smith et al. showed' but 'β-catenin activates...'"

### Missing Relationships in Graph
**Problem:** Graph has nodes but few edges
**Solution:**
- Prompt for explicit relationships: "What regulates what? What causes what?"
- Look for causal language: "activates," "inhibits," "requires," "produces"
- Ask: "How does X lead to Y? What's the mechanism connecting them?"

### Papers Too General (Not Specific Enough)
**Problem:** Papers discuss topic broadly, not your specific question
**Solution:**
- Make placeholders more specific: Add {TIMEFRAME}, {ORGANISM}, {CONDITION}
- Search with compound queries: "X AND Y AND Z" not just "X"
- Filter during extraction: "Only extract findings about {SPECIFIC_ASPECT}"

### Database Connection Issues
```bash
# Check ArangoDB is running
docker ps | grep arangodb

# Test connection
curl http://localhost:8529/_api/version
```

### Conflicting Information Across Papers
**Problem:** Different papers report different findings
**Solution:**
- Create a "contradictions" collection
- Store both findings with evidence strength
- Prompt: "What differs between these papers? Same method, different result?"
- Use this to identify interesting follow-up questions

---

## Next Steps

**After lunch:** Build your own MCP server using Hatch, applying patterns from this workflow.

**Advanced Topics (if time):**
- **Ontology Integration:** Link extracted entities to standard ontologies (Gene Ontology, ChEBI)
- **Quantitative Modeling:** Export knowledge graph to systems biology tools (SBML, CellDesigner)
- **Hypothesis Generation:** Use graph patterns to suggest untested relationships
- **Literature Monitoring:** Automate updates when new papers are published
- **Multi-Modal Integration:** Combine text extraction with figure analysis

---

## Hatch Commands Reference

Quick reference for server management:

```bash
# List configured servers
hatch mcp list servers

# Sync server configuration to multiple hosts
hatch mcp sync paper-search-mcp --host all

# Remove server configuration
hatch mcp remove server paper-search-mcp --host claude-desktop

# Backup current configuration
hatch mcp backup list
```

Full CLI reference: [Hatch CLI Documentation](https://raw.githubusercontent.com/CrackingShells/Hatch/refs/heads/dev/docs/articles/users/CLIReference.md)
