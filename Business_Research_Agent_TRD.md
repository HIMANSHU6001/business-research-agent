# Business Research Agent

**Technical Requirements Document**

*Version 2.0 (Consolidated)*

*Supersedes: Context Layer TRD v1 · Workspace Manager TRD v1 · Data Collection Layer TRD v1 · Data Analysis Layer TRD v1 · Analytics MCP Server TRD v1*

---

## Table of Contents

- [1. Executive Summary](#1-executive-summary)
- [2. Scope](#2-scope)
- [3. Global Design Principles](#3-global-design-principles)
- [4. System Architecture Overview](#4-system-architecture-overview)
- [5. End-to-End Research Workflow](#5-end-to-end-research-workflow)
- [6. Context Layer](#6-context-layer)
- [7. Data Collection Layer](#7-data-collection-layer)
- [8. Data Analysis Layer](#8-data-analysis-layer)
- [9. Analytics MCP Server](#9-analytics-mcp-server)
- [10. Cross-Cutting Operational Policies](#10-cross-cutting-operational-policies)
- [11. Glossary of Agents and Roles](#11-glossary-of-agents-and-roles)

---

## 1. Executive Summary

The Business Research Agent is a multi-agent system that turns a natural-language research query into an evidence-backed research report. It scopes the query, selects an analytical framework, dispatches capability agents to collect financial, macroeconomic, and consumer-trend evidence, runs quantitative and qualitative analysis over that evidence, and returns a synthesized final report.

The system is built on one architectural principle above all others: the LLM never operates on raw data. Every agent reasons over semantic descriptions, schemas, and catalogs — never over raw rows, dataframes, or unbounded API payloads. Deterministic infrastructure (interceptors, middleware, a dedicated statistics server) does the actual data handling and computation. This keeps the system reproducible, auditable, and immune to the context-window blowups that come from feeding large datasets directly into a model.

This document consolidates and supersedes five prior TRDs (Context Layer, Workspace Manager, Data Collection Layer, Data Analysis Layer, Analytics MCP Server) into a single, internally consistent specification.

## 2. Scope

### 2.1 In Scope

- Query scoping and analytical framework selection

- Parallel evidence collection across financial, macroeconomic, and trend data sources

- Deterministic artifact creation, validation, and cataloging

- Quantitative analysis via a dedicated, LLM-isolated statistics server

- Qualitative analysis via framework-driven retrieval-augmented reasoning

- Context management: semantic knowledge (Knowledge Manager) and structured data (Workspace Manager)

- Final report synthesis

### 2.2 Out of Scope (deferred to future TRDs)

- Visualization / charting layer

- Report formatting, export, and rendering (PDF, slides, etc.) beyond the Analysis Supervisor's structured output

- Framework package specifications (SWOT, PESTEL, Porter's Five Forces, Thematic, Conceptual — content and evidence checklists per framework)

- Workflow runtime / orchestration graph implementation (e.g., LangGraph node and edge definitions)

- Evaluation harness and golden-dataset testing strategy

- Authentication, multi-tenancy, and access control

## 3. Global Design Principles

- Control plane / data plane separation. LLMs reason over metadata, schemas, and catalogs. Only deterministic infrastructure (interceptors, the Analytics MCP Server) touches raw data.

- Evidence before conclusions. Data collection agents gather facts and never interpret them. Analysis agents interpret evidence and never collect new data (with one narrow, explicit exception — see §8.4.3).

- Deterministic artifact creation. Artifacts are built by middleware, never hand-assembled by an agent.

- Capability-oriented design. Agents represent business capabilities (“Financial Intelligence”), not the vendor API behind them (“Alpha Vantage Agent”).

- Orchestrator / workers, never peer-to-peer. Capability agents never communicate directly. All coordination flows through a supervisor.

- Traceability. Every artifact and every claim in a report must be traceable to a source, with provenance and citations attached.

- Storage-agnostic agents. Agents never talk to a database directly. Context Layer components are the only things that do.

## 4. System Architecture Overview

The system is organized into four layers:

- Context Layer — the Knowledge Manager (semantic memory, pgvector) and Workspace Manager (structured artifacts, DuckDB + Parquet). Both are accessed exclusively through narrow APIs; no agent talks to a database directly.

- Data Collection Layer — a supervisor that dispatches three capability agents in parallel (Financial Intelligence, Macro Economic Intelligence, Trends Intelligence) to gather evidence and produce artifacts.

- Data Analysis Layer — a supervisor that runs Quantitative Analysis (statistics via the Analytics MCP Server) and Qualitative Analysis (framework-driven reasoning) over the collected evidence.

- Analytics MCP Server — a stateless computation engine that executes statistical operations on behalf of the Quantitative Analysis Agent and returns compressed natural-language results, never raw data.

## 5. End-to-End Research Workflow

The system executes a fixed, top-level sequence:

1. Scoping — the user query is converted into a structured research brief.

2. Framework Selection — exactly once per research session, immediately after scoping. The Scoping stage selects the analytical framework (Conceptual, Thematic, SWOT, PESTEL, or Porter's Five Forces) that best fits the research brief. This choice is final for the session and is persisted as part of the research state.

3. Data Collection — the Data Collection Supervisor dispatches the three capability agents in parallel. Each returns a topic report and a set of artifact references.

4. Data Analysis — the Analysis Supervisor runs Quantitative Analysis (if required) and then Qualitative Analysis. The Qualitative Analysis Agent does not re-select a framework; it loads the framework chosen in step 2 and executes it.

5. Final Report — the Analysis Supervisor synthesizes the quantitative and qualitative findings into the final report. There is no separate report-generation stage in this version of the system; the Analysis Supervisor's output is the deliverable returned to the user.

*Design note: framework selection happens exactly once, upfront, so that it can inform what evidence the Data Collection Layer prioritizes. The Qualitative Analysis Agent is a consumer of that decision, not a second decision-maker — this is a deliberate change from earlier drafts, where the wording implied the qualitative agent might independently reselect a framework after collection.*

## 6. Context Layer

The Context Layer manages all information generated during a research session. It is split into two independent services — the Knowledge Manager and the Workspace Manager — so that contextual knowledge used by LLMs stays isolated from structured research data used for computation.

### 6.1 Principles

- Contextual knowledge and structured data are separate concerns.

- Agents never interact directly with databases; the Context Layer is a black box to them.

- Every stored artifact must be traceable to its original source.

- The Context Layer is storage-agnostic from the perspective of agents.

### 6.2 Memory Architecture

#### 6.2.1 Procedural Memory

Defines how an agent behaves: tool usage instructions, output schemas, examples, execution guidelines. Static, stored in the agent's prompt, and not managed by the Context Layer.

#### 6.2.2 Semantic Memory

Knowledge generated during a research session — research reports, human feedback, research milestones. Managed entirely by the Knowledge Manager. Raw reasoning traces and intermediate working memory are never persisted here.

#### 6.2.3 Working Memory

Exists only for the lifetime of a single agent execution: conversation turns, tool calls and outputs, intermediate reasoning, temporary plans, observations, partial results.

Each agent maintains an in-memory checkpointer that periodically compresses conversation history to control context window usage. The compressed state is local to the running agent and discarded once its execution completes. When an agent's execution finishes, the report it produces is persisted as semantic memory; the working memory that produced it is not.

### 6.3 Knowledge Manager

Responsible for storing and retrieving contextual knowledge from a vector database (pgvector).

#### Responsibilities

- Store contextual reports

- Retrieve relevant context

- Manage semantic memory

- Hide retrieval implementation from agents

#### Public APIs

search_context(research_id, agent, query)

Returns contextual information required by an agent: research brief, previous reports, human feedback, and relevant semantic memories. Retrieval strategy is Metadata-Filtered Hybrid Search (dense + sparse) with a cross-encoder reranker, entirely internal to the Knowledge Manager.

store_context(research_id, agent, task, report)

Stores contextual knowledge generated during execution. The report is embedded and stored under the namespace of the producing agent.

#### Access budget

The supervisor agents have unrestricted access to search_context() for orchestration purposes. Capability agents have a limited number of search_context() calls per execution (see §10.2 for the initial quota policy).

#### Storage

Reports are stored under namespaces corresponding to the Research ID (Research ID → Collected Knowledge), forming a knowledge pool that any downstream agent can retrieve from via search_context().

### 6.4 Workspace Manager

The Workspace Manager is the central store for structured research artifacts. It maintains strict decoupling between the Control Plane (LLM context/reasoning) and the Data Plane (high-volume structured/time-series data) via a stateless hub-and-spoke topology.

#### 6.4.1 The Triad State Configuration

Three isolated registries provide schema deduplication, rapid lookups, and context safety:

- **Artifact Registry (Data Plane) — physical storage of normalized data (DuckDB + Parquet). LLMs are strictly forbidden from reading these entities; access is exclusive to the Python execution runtime during Quantitative Agent delegations.**

- **Semantic Catalog (Routing Plane) — active metadata registry with natural-language descriptions of available data for LLM discovery.**

- **Schema Registry (Execution Plane) — strict column-level types, constraints, and array structures, accessed exclusively by the Quantitative Agent to formulate precise tool calls.**

#### 6.4.2 Semantic Catalog Schema

- source_mcp / tool_used — audit and lineage tracking

- db_table_pointer — the physical target for the Python runtime

- schema_ref — pointer into the Schema Registry for column mapping

- row_count — prevents hallucinated mathematical execution on empty datasets

- time_range — temporal boundaries (start, end); null for snapshots

- inputs — scrubbed, semantic parameters used to fetch the data (e.g., {"symbol": "IBM"})

- description — an LLM-generated, 2–3 sentence semantic summary of the data's utility

#### 6.4.3 Ingestion Protocol (ingest_to_db)

Every ingestion event undergoes a mandatory pipeline:

- Payload Interception — raw JSON from the MCP server is intercepted before it reaches the LLM.

- Sanitization & Flattening — nested structures are stringified for relational compatibility, keys normalized to snake_case, strings coerced to numerics where applicable.

- Artifact Generation — the sanitized payload is written to the Data Plane.

- Metadata Extraction — shape (row_count), temporal boundaries (time_range), and scrubbed invocation inputs are computed.

- Semantic Generation — a lightweight LLM utility writes the descriptive summary of the artifact.

*Data quality note: numeric coercion failures must be counted and recorded in the artifact metadata (e.g., coercion_failures: <n>), not silently dropped to null or zero. A value that fails to coerce and is silently treated as 0 will corrupt downstream correlation and t-test results without tripping any existing guard, since the Analytics MCP Server's insufficiency check only looks at row count, not per-column coercion failures.*

#### 6.4.4 Tools Exposed by the Workspace Manager

**get_catalog()** — Access: Quantitative Agent. Target: Semantic Catalog. Returns a lightweight array of available datasets (description, row_count, time_range, artifact_id, schema_ref) with all raw data stripped.

**get_schema(schema_ref)** — Access: Quantitative Agent. Target: Schema Registry. Returns exact column types and constraints for an artifact. Must be called before any Analytics MCP invocation to prevent parameter hallucination (e.g., guessing revenue_net instead of net_revenue).

**get_artifact(filter)** — Access: Analytics MCP Server (Python runtime) ONLY. Target: Artifact Registry (DuckDB + Parquet). Executes physical extraction of normalized data. The Quantitative Agent is completely isolated from this endpoint; if an LLM successfully invoked it directly, the raw time-series payload would overflow its context.

## 7. Data Collection Layer

### 7.1 Purpose

Collects reliable evidence from external sources and transforms it into structured, traceable research artifacts. This is the evidence acquisition phase: it is intentionally separated from statistical analysis, reasoning, and report synthesis so downstream stages operate on verified, reproducible data rather than raw API responses. The objective is to collect facts, not conclusions.

### 7.2 Scope

#### Responsible for

- Retrieving information from trusted external sources

- Producing structured research artifacts

- Attaching provenance and citations

- Generating topic-specific evidence reports

#### Not responsible for

- Statistical analysis

- Business interpretation

- Cross-domain synthesis

- Visualization

- Final report generation

- Workspace persistence (delegated to the Workspace Manager)

- Context management (delegated to the Knowledge Manager)

### 7.3 Architecture

Supervisor → Capability Agent → Domain MCP Server → External Data Source → Artifact Middleware → Workspace Manager

Each capability agent owns a single research capability. Agents never communicate with one another; all orchestration is performed by the Supervisor.

### 7.4 Concurrency Model

The Data Collection Supervisor dispatches all three capability agents in parallel. Each agent runs independently against its own domain MCP server and returns its topic report and artifact references to the Supervisor once complete. The Supervisor waits on all three before proceeding to synthesis of the Data Collection Report. This replaces a sequential one-agent-at-a-time model considered in an earlier draft, and is the primary lever for keeping collection-phase latency roughly constant regardless of how many capability agents exist.

### 7.5 Runtime Contract

#### Input

- Assigned research task

- Agent instructions

- Compressed conversation history

- Runtime budget

#### Execution

- think()

- search_context() (within budget)

- ask_human()

- Domain-specific MCP tool invocations

#### Output

- Topic research report

- References to generated artifacts

- Citations

### 7.6 Data Collection Supervisor

| **Field** | **Specification** |
| --- | --- |
| Responsibility | Understand research brief; break research into sub-topics; dispatch all three capability agents in parallel; synthesize their reports into the Data Collection Report. |
| Privileges | Context store access; ask_human() access; sub-agent report access; workspace catalog.json read access; higher turn budget. |
| Context | Compressed message history; research brief; selected framework (reference only, for evidence prioritization); instructions. |
| Tools | knowledge_retrieval(); catalog_inspection(); invoke_agent() (parallel dispatch); ask_human(); think(); terminate_data_collection(). |
| Output | Final Data Collection Report. |

### 7.7 Capability Agents

Common restrictions across all three capability agents: cannot invoke other agents; cannot access databases directly; cannot create artifacts manually; cannot access DuckDB or pgvector directly; cannot modify workspace metadata; cannot perform statistical analysis.

#### 7.7.1 Financial Intelligence Agent

Purpose: collect company-specific financial evidence. Source: Alpha Vantage MCP.

Deliverables: Financial Research Report, financial artifact references.

| **Tool group** | **Tools** | **Routing** |
| --- | --- | --- |
| fundamental_data | EARNINGS_CALENDAR, COMPANY_OVERVIEW, LISTING_STATUS, INCOME_STATEMENT, CASH_FLOW, EARNINGS, BALANCE_SHEET, IPO_CALENDAR | Intercepted by ingest_to_db. Raw data is ingested into the Workspace Manager; the agent receives a confirmation string (e.g., “24 rows ingested”), never the raw payload. |
| alpha_intelligence | NEWS_SENTIMENT, EARNINGS_CALL_TRANSCRIPT, TOP_GAINERS_LOSERS, INSIDER_TRANSACTIONS, INSTITUTIONAL_HOLDINGS, ANALYTICS_FIXED_WINDOW, ANALYTICS_SLIDING_WINDOW | Not intercepted. Result returned directly to the agent, which may include it verbatim in its topic report. |

#### 7.7.2 Macro Economic Intelligence Agent

Purpose: collect macroeconomic and industry evidence (GDP, inflation, population, industry indicators, trade statistics). Source: Data 360 MCP. Renamed from “Market Intelligence Agent” in earlier drafts for accuracy — this agent collects country-level macroeconomic indicators, not competitive or market-share intelligence.

Deliverables: Macro Economic Intelligence Report, macroeconomic artifact references.

| **Tool(s)** | **Routing** |
| --- | --- |
| data360_search_indicators, data360_get_disaggregation | Do not produce data themselves. They assist the agent in identifying the correct indicator code to pass to data360_get_data. |
| data360_get_data | Intercepted by ingest_to_db. Result is ingested into the Workspace Manager; the agent receives a confirmation string. |
| data360_summarize, data360_rank_countries, data360_compare_countries | Not intercepted. Result returned directly to the agent, which may include it verbatim in its topic report. |

#### 7.7.3 Trends Intelligence Agent

Purpose: collect consumer demand and search trend evidence. Source: Google Trends MCP Server (via SerpAPI).

Deliverables: Trends Report, trend artifact references.

| **Tool(s)** | **Routing** |
| --- | --- |
| interest_by_region, interest_over_time | Both intercepted by ingest_to_db. Results are ingested into the Workspace Manager; the agent receives a confirmation string for each. |

### 7.8 Artifact Generation

Artifacts are never generated by agents. Every successful MCP tool invocation that is routed for interception passes through the Artifact Middleware, which normalizes API responses, builds canonical artifacts, validates schema, attaches metadata/provenance/citations, updates catalog.json, and persists the artifact through the Workspace Manager.

### 7.9 Quality Guarantees

- Traceable to external sources

- Includes citations

- Includes provenance

- Follows canonical schema

- Passes validation before persistence

## 8. Data Analysis Layer

### 8.1 Purpose

Transforms collected research evidence into meaningful insights. This layer does not collect new primary evidence — it operates on structured artifacts produced during data collection, semantic knowledge stored in the Knowledge Manager, and reports generated by previous agents, with one narrow, explicitly scoped exception described in §8.4.3.

#### Responsible for

- Analyzing collected evidence

- Qualitative reasoning

- Quantitative/statistical reasoning

- Synthesizing findings

- Generating the final analysis report

#### Not responsible for

- Primary evidence collection

- Arbitrary API calls

- Writing artifacts into the workspace

- Generating visualizations

### 8.2 Architecture

Analysis Supervisor → {Quantitative Analysis Agent → Analytics MCP Server; Qualitative Analysis Agent → Knowledge Manager} → Reports → Final Analysis Report.

Supervisor orchestrates; capability agents perform focused reasoning; deterministic computation is delegated to tools; large datasets are never injected into LLM context; reports are the sole communication mechanism between agents.

### 8.3 Analysis Supervisor

Orchestrates the analysis workflow and maintains an explicit current_task state: quantitative_analysis → qualitative_analysis → synthesis → completed. It decides which capability agent executes next, whether quantitative analysis is required, whether qualitative analysis is required, and when analysis is complete. The supervisor never performs analysis itself.

| **Field** | **Specification** |
| --- | --- |
| Inputs | Research brief; research progress summary; Data Collection Report; workspace catalog; knowledge context. |
| Context | Compressed conversation history; research brief; research progress summary; Data Collection Report; workspace catalog; system instructions. |
| Privileges | Knowledge Manager access; workspace catalog access; ask_human(); capability agent invocation; higher reasoning budget. |
| Tools | search_context(); read_catalog(); invoke_agent(); ask_human(); think(); complete_analysis_step(). |
| Output | Final Analysis Report (see §8.6) — this is the document returned to the user. There is no separate report-generation stage downstream of the Analysis Supervisor. |

### 8.4 Qualitative Analysis Agent

Purpose: interpret research evidence using an established business or research framework (SWOT, PESTEL, Porter's Five Forces, Thematic Analysis, or Conceptual Analysis). Performs reasoning only; never performs statistical computation.

#### 8.4.1 Workflow

- Receive task

- Load framework instructions (see note below)

- Retrieve evidence iteratively via search_context()

- Execute the framework

- Generate the qualitative report

*Note on framework selection: the analytical framework is chosen once, in the Scoping stage, before data collection begins (§5, step 2). The Qualitative Analysis Agent does not select a framework — it loads the instructions, evidence checklist, and output schema for the framework already recorded in the research state. This is a deliberate correction from an earlier draft, where the agent's first workflow step was worded as “Select Framework,” which read as an independent second decision.*

#### 8.4.2 Framework Package

Each framework provides instructions, a reasoning methodology, an evidence checklist, and an optional output schema. It does not provide fixed retrieval queries — the agent generates retrieval queries dynamically from the evidence checklist, iterating (generate query → search → evaluate result → repeat if necessary) until it has enough evidence to proceed.

#### 8.4.3 Tavily Gap-Fill Search

The Qualitative Analysis Agent has access to web search via Tavily, restricted to a single purpose: filling specific gaps in evidence that search_context() cannot satisfy. This is not a primary evidence-collection mechanism and is subject to the following rules:

- Tavily may only be invoked after search_context() has been tried for the evidence in question and returned insufficient results.

- Each execution of the Qualitative Analysis Agent is capped at a small, fixed number of Tavily calls (start at 2 per execution; tune per §10.2).

- Any fact sourced via Tavily must be attached to the qualitative report with the same citation and provenance treatment the Data Collection Layer applies to its artifacts — it must be distinguishable in the final report as gap-fill evidence, not conflated with evidence sourced from the Knowledge Manager.

#### 8.4.4 Context, Privileges, Tools

| **Field** | **Specification** |
| --- | --- |
| Context | Framework instructions; framework schema/checklist; retrieved evidence; compressed history. |
| Privileges | Knowledge search (via search_context()); bounded Tavily gap-fill search; ask_human(). |
| Tools | search_context(); tavily_search() (bounded, see §8.4.3); ask_human(); think(). |
| Output | Evidence-backed qualitative report, with citations distinguishing Knowledge Manager evidence from Tavily gap-fill evidence. |

Maximum recommended frameworks executed per run: one (the framework selected in Scoping). Multi-framework execution is not part of this version of the system.

### 8.5 Quantitative Analysis Agent

Purpose: perform deterministic quantitative analysis by orchestrating statistical tools provided by the Analytics MCP Server. The LLM never performs statistical computation itself — it selects the appropriate tool and interprets the output.

#### Workflow

- Receive task

- Inspect workspace catalog via get_catalog()

- Inspect schema via get_schema()

- Select the appropriate analysis tool

- Invoke the Analytics MCP Server

- Observe the result; invoke additional tools if required

- Interpret findings and generate the report

| **Field** | **Specification** |
| --- | --- |
| Context | Analysis task; research progress summary; compressed history; available Analytics MCP tools. Never raw datasets. |
| Privileges | Workspace catalog and schema registry access; Analytics MCP Server access; ask_human(). |
| Tools | read_catalog(); get_schema(); analytics_mcp(); ask_human(); think(). |
| Output | Evidence-backed quantitative report. |

### 8.6 Supervisor Communication and Final Report

Capability agents never communicate directly; all communication flows through the Analysis Supervisor: Supervisor → Capability Agent → Report → Supervisor → next Capability Agent. Typical flow: quantitative analysis (if required) → qualitative analysis → synthesis.

Only summaries are passed between capability agents (e.g., a compressed summary of the quantitative report is available to the qualitative agent); the full conversation of one capability agent is never shared with another.

The Final Analysis Report, produced by the Analysis Supervisor, is the report returned to the user — there is no downstream formatting or report-generation stage in this version of the system. Its required structure:

- Executive summary (framework-agnostic, 3–5 sentences)

- Qualitative findings, organized by the selected framework's structure (e.g., Strengths / Weaknesses / Opportunities / Threats for SWOT)

- Quantitative findings, with each statistical result stated in plain language alongside its key figures (coefficients, p-values, confidence intervals)

- Synthesis — how the quantitative and qualitative findings support or complicate one another

- Citations — a consolidated reference list, with Tavily gap-fill sources visually distinguished from Knowledge Manager / artifact-sourced evidence

## 9. Analytics MCP Server

### 9.1 Functional Scope

The Analytics MCP Server is the stateless, isolated computation engine for the Data Analysis Layer — a rigid mathematical proxy between the Quantitative Analysis Agent (control plane) and the Workspace Manager (data plane). It abstracts Pandas, NumPy, and SciPy from the LLM entirely. The LLM is strictly prohibited from writing code or SQL; it interacts only by passing string arguments (table pointers, column names) to predefined statistical endpoints.

### 9.2 Core Architecture & Safety Gateways

| **Step** | **Entity** | **Action** |
| --- | --- | --- |
| 1 | Analysis Agent | Invokes tool with table & column strings |
| 2 | Schema Guardrail | Validates request against schema_registry.json |
| 3 | DuckDB Engine | Fetches target data partitions from Parquet |
| 4 | Statistical Processor | Executes SciPy / Pandas logic |
| 5 | Analysis Agent | Receives a compressed text summary |

#### 9.2.1 Schema Guardrail (Anti-Hallucination Pipeline)

Every incoming tool request is validated before it reaches the data pipeline: the server extracts the db_table_pointer and requested columns, cross-references them against schema_registry.json, and hard-fails on any mismatch. The error returned is descriptive and includes a difflib-based nearest-match suggestion (e.g., “Error: Column 'net_margin' not found in table 'tbl_appl_financials'. Did you mean 'net_income_margin'?”), letting the agent self-correct via its own think() loop without a second LLM call to interpret the failure.

#### 9.2.2 Low-Token Payload Compression

The server is explicitly banned from returning raw dataframes or multi-row JSON arrays. All heavy structural transformation happens server-side in memory; the return value is always a compressed, natural-language statistical text block containing key metrics, coefficients, confidence intervals, and p-values.

### 9.3 Tool Specifications

#### 9.3.1 calculate_correlation

Computes the statistical relationship between two numeric series, optionally across two different tables joined on a key.

Parameters: table_x, col_x, table_y, col_y, join_key.

Backend logic: loads Parquet data via DuckDB, inner-joins on join_key, drops NaNs, and runs scipy.stats.pearsonr() and scipy.stats.spearmanr().

*Statistical caveat (added in this revision): most inputs to this system are time series (stock prices, macro indicators, search interest, revenue). Two series that are both simply trending upward will show a strong Pearson/Spearman correlation with no real causal or structural relationship between them (spurious correlation via shared trend). Before reporting a correlation as meaningful, the server should difference or detrend both series, or at minimum flag in its output when both inputs exhibit a strong trend component, so the agent can appropriately discount a high correlation that may simply reflect “both went up over time.”*

#### 9.3.2 execute_t_test

Determines whether there is a statistically significant difference between the means of two groups or time windows.

Parameters: table, target_col, split_col, group_a_condition, group_b_condition.

Backend logic: splits target_col into two vectors by the given conditions and runs scipy.stats.ttest_ind(equal_var=False) (Welch's t-test, which does not assume equal variance between groups).

*Statistical caveat (added in this revision): when the split is a before/after date cut on time-series data, adjacent observations are not independent, which is an assumption of the t-test. Reported p-values in this case will read more confident than they should; this limitation should be surfaced in the tool's output whenever split_col is a date column.*

#### 9.3.3 calculate_trendline

Parameters: table, target_col, date_col, rolling_window.

Backend logic: sorts by date_col, computes a moving average via Pandas rolling(window).mean(), and fits an OLS linear model (statsmodels.api.OLS) over the temporal index to derive slope and R².

#### 9.3.4 get_descriptive_stats

Parameters: table, target_col.

Backend logic: Pandas .describe() combined with skewness and kurtosis via scipy.stats.

### 9.4 Error State Protocols

| **Error Type** | **Trigger** | **Response** |
| --- | --- | --- |
| SchemaValidationError | Column or table name absent from schema_registry.json. | Aborts execution. Returns HTTP 422 with a descriptive message and a difflib-based nearest-match suggestion. |
| DataInsufficiencyError | Fewer than 3 valid data points remain after joining/filtering. | Aborts computation. Returns valid record count and the minimum required (3). |
| MathematicalDivergenceError | Zero variance in a vector (would cause a divide-by-zero in correlation or t-test). | Returns a descriptive error; no computation is attempted. |

## 10. Cross-Cutting Operational Policies

### 10.1 Concurrency Model

Data collection capability agents run in parallel (§7.4). Quantitative and Qualitative analysis run sequentially, in that order, because the qualitative agent's evidence checklist may reference quantitative findings during synthesis.

### 10.2 Budget & Quota Policy

The system is in an early phase; exact budgets are expected to change as real usage patterns emerge. Start at the minimum viable quota for each budgeted resource and raise it only when observed evidence quality is limited by the cap, not preemptively:

- search_context() calls per capability agent execution: start at 3.

- Tavily gap-fill calls per Qualitative Analysis Agent execution: start at 2.

- Supervisor turn budget: kept deliberately higher than capability agent budgets, since supervisors orchestrate multiple invocations.

*These figures are starting points to be tuned during development, not fixed requirements.*

### 10.3 API Failure Handling

Failure handling for the three external data sources (Alpha Vantage, Data 360, SerpAPI) will be defined against real failure modes encountered during development rather than speculatively up front. At minimum, every domain MCP call should surface a distinguishable error to its capability agent (rather than an ambiguous empty result) so the agent can decide whether to retry, try an alternative tool, or report the gap in its topic report.

### 10.4 ask_human() Policy

ask_human() is available to every supervisor and every capability/analysis agent. Recommended default, to be revisited once usage data exists: reserve it for genuine scope ambiguity or missing required input, and route capability-agent escalations through their supervisor rather than surfacing to the user directly, to avoid the pipeline stalling on multiple simultaneous human touchpoints.

### 10.5 Schema Versioning

Not yet specified. If an upstream provider (e.g., Alpha Vantage) changes a field, schema_ref should version rather than silently pointing an existing catalog entry at a changed shape. Placeholder for a future revision of this document.

### 10.6 Evaluation & Testing Strategy

Not yet specified. Recommended before production use: a golden-set of research briefs with expected framework selections, expected evidence coverage, and expected statistical tool selections, to catch regressions in agent decision quality independent of infrastructure correctness.

## 11. Glossary of Agents and Roles

| **Component** | **Role** |
| --- | --- |
| Scoping | Converts the user query into a research brief and selects the analytical framework. |
| Data Collection Supervisor | Dispatches Financial, Macro Economic, and Trends Intelligence agents in parallel; synthesizes the Data Collection Report. |
| Financial Intelligence Agent | Collects company financial evidence via Alpha Vantage MCP. |
| Macro Economic Intelligence Agent | Collects country-level macroeconomic evidence via Data 360 MCP. |
| Trends Intelligence Agent | Collects search-trend evidence via Google Trends MCP (SerpAPI). |
| Analysis Supervisor | Orchestrates Quantitative and Qualitative analysis; produces the Final Analysis Report returned to the user. |
| Quantitative Analysis Agent | Orchestrates statistical tools on the Analytics MCP Server; never computes statistics itself. |
| Qualitative Analysis Agent | Executes the framework selected in Scoping over retrieved evidence; may use bounded Tavily search to fill evidence gaps. |
| Knowledge Manager | Semantic memory store (pgvector); serves search_context() / store_context(). |
| Workspace Manager | Structured artifact store (DuckDB + Parquet); serves get_catalog(), get_schema(), get_artifact(). |
| Analytics MCP Server | Stateless statistics engine; the only component permitted to call get_artifact(). |