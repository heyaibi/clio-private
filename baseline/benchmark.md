# Benchmark Strategy & Competitive Evaluation for Clio (by Agent Memoir)

## 1. Executive Summary & Goal

The goal of this benchmarking initiative is to establish a rigorous, reproducible, and standardized evaluation harness for `clio` against established memory systems (**Hindsight**, **Mem0**, **Supermemory**, **Honcho**, and **Mnemosyne**).

This benchmark is not merely a marketing score; it is the **engineering feedback loop** used to tune hyperparameters, validate architectural primitives, and continuously optimize:
1. **Retrieval Quality & Accuracy:** Factual precision, temporal coherence, multi-hop reasoning, and conflict resolution evaluated via calibrated LLM-as-a-judge and token F1.
2. **Token Efficiency & Operating Cost:** Volume of context injected into the agent prompt (tokens retrieved per query vs. brute-force context stuffing) and write-path ingestion token cost.
3. **Latency Profiles:** Decoupled write-path time-to-queryable ($NFR\text{-}2$) and retrieval latency ($p50$, $p95$, $p99$ response times in milliseconds).

```
                      ┌───────────────────────────────────────────────┐
                      │             The Pareto Frontier               │
                      ├───────────────────────────────────────────────┤
                      │  1. Accuracy (LLM-Judge, F1, Recall@k)        │
                      │  2. Token Efficiency (Context tokens/query)   │
                      │  3. Latency (Write-to-queryable & Read p95)   │
                      └───────────────────────────────────────────────┘
```

The benchmark suite integrates five canonical industry benchmarks:
- **LoCoMo:** Long-term conversational memory across multi-session dialogues (temporal, causal, recall).
- **LongMemEval:** Long-horizon evaluation across Accurate Retrieval, Test-Time Learning, Long-Range Understanding, and Conflict Resolution.
- **BEAM (Agent Memory Benchmark):** Massive-scale memory evaluation (128K, 500K, 1M, and 10M tokens) across 10 distinct memory abilities.
- **MemoryAgentBench:** Incremental multi-turn interaction testing with an "inject once, query multiple times" architecture.
- **AMA-Bench:** Long-horizon memory on complex, multi-step agent execution trajectories and tool interactions.

---

## 2. Competitive Landscape: Established Players & Tactics

Understanding how established players design their systems and structure their benchmarks reveals the tactical landscape:

### 2.1 Hindsight (Vectorize / arXiv:2512.12818)
- **Architecture:** Four distinct memory networks: *World Network* (objective facts), *Experience Network* (episodic chronological logs), *Observation Network* (ongoing perceptions), and *Opinion Network* (synthesized beliefs/preferences).
- **Operations:** Three explicit verbs: `Retain` (ingest), `Recall` (hybrid retrieval), and `Reflect` (belief consolidation and contradiction handling).
- **Storage:** PostgreSQL + `pgvector`.
- **Benchmarking Tactic:** Vectorize created the **Agent Memory Benchmark (AMB)** and evaluates on **LongMemEval** and **LoCoMo**. Hindsight achieves high scores by separating immutable facts from changing beliefs, ensuring that obsolete facts are not retrieved for current-state queries.
- **Key Vulnerability:** Heavy reliance on continuous LLM-driven reflection and PostgreSQL-only infrastructure, limiting zero-dependency edge and local agent deployments.

### 2.2 Mem0 (Embedchain / mem0.ai)
- **Architecture:** Dynamic multi-layer memory (User, Session, Agent scopes) with an optional knowledge graph layer (Mem0 Graph).
- **Operations:** Write-time LLM extraction calling structured tools: `add`, `update`, and `delete`.
- **Benchmarking Tactic:** Mem0 maintains an open-source evaluation suite (`memory-benchmarks`) focusing on **LoCoMo**, **LongMemEval**, and **BEAM**. Mem0 emphasizes token efficiency (reporting an average of <7,000 prompt tokens per call compared to 25,000+ for full-context stuffing) and retrieval $p95$ latency.
- **Key Vulnerability:** Write-time extraction latency and cost are high because every message requires synchronous or near-synchronous LLM passes to extract facts and deduce graph edges.

### 2.3 Supermemory (supermemory.ai)
- **Architecture:** Personal memory engine combining vector search with a lightweight knowledge graph.
- **Operations:** Chrome extension / agent ingestion, bookmarking, and markdown/document extraction.
- **Benchmarking Tactic:** Evaluates on **BEAM** (up to 10M tokens) and created **MemoryBench** to emphasize long-range document recall, multi-session user preference continuity, and tool recall.
- **Key Vulnerability:** Optimized primarily for user-facing personal notes/web knowledge rather than stateful agentic execution trajectories or bi-temporal contradiction resolution.

### 2.4 Honcho (Plastic Labs)
- **Architecture:** Dialectic memory and cognitive user modeling ("Theory of Mind"). Instead of storing static chat logs, Honcho constructs a dynamic cognitive model of the user's beliefs, intentions, and reasoning style.
- **Operations:** Powered by the specialized **Neuromancer XR** model series for formal logical reasoning over user representations.
- **Benchmarking Tactic:** Plastic Labs maintains `plastic-labs/honcho-benchmarks`, testing on **LongMemEval**, **LoCoMo**, and **BEAM**. Honcho abandoned token-overlap F1 in favor of calibrated LLM-as-a-judge mean accuracy, demonstrating Pareto dominance in balancing accuracy against token cost.
- **Key Vulnerability:** Complex user-modeling pipelines can introduce cognitive hallucination on objective factual retrieval where simple exact span grounding is required.

### 2.5 Mnemosyne
- **Architecture:** Local-first, unsupervised, zero-dependency graph-structured memory running entirely on **SQLite**.
- **Operations:** Working memory, episodic triples, canonical facts, deterministic temporal decay, and co-occurrence consolidation without mandatory cloud LLM extraction.
- **Benchmarking Tactic:** Evaluated against **LoCoMo** and **BEAM** to prove that local-first, zero-cloud-cost memory can beat naive vector RAG on temporal reasoning and single-hop recall with sub-millisecond query latency.
- **Key Vulnerability:** Unsupervised heuristics without live LLM extraction can miss subtle semantic associations and complex long-range causal chains.

### 2.6 Competitive Matrix

| Feature / Metric | Hindsight | Mem0 | Supermemory | Honcho | Mnemosyne | **Clio** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Persistence** | PostgreSQL + pgvector | Managed / Vector DBs | Vector + Graph DB | Managed Cloud | SQLite | **Dual: Postgres + SQLite** |
| **Temporal Model** | Separate Exp/World nets | Timestamp metadata | Timestamp metadata | Dialectic state | Temporal decay | **Full Bi-temporal (§4.6)** |
| **Write-Path Admission** | Unfiltered retain | Heuristic / LLM filter | Extraction filter | Cognitive filter | Unsupervised gating | **5-Factor Admission (§4.2)** |
| **Hierarchical Index** | Entity Summaries | Graph entities | Document chunks | Cognitive graph | Graph nodes | **MemTree (§4.3) + EMA** |
| **Contradiction Handling** | Reflection pass | LLM update/delete | Graph overwrite | Theory-of-mind update | Score invalidation | **Bi-temporal Invalidation (PR-6)** |
| **Companion Objects** | Opinions/Beliefs | User profile | Personal tags | User persona | Persona list | **Persona (§4.7) + Beliefs (§4.10)** |
| **Deployment Footprint** | Cloud / Self-host | Cloud API / Python | Cloud API / SaaS | Cloud API / SDK | Edge / Local SQLite | **Local Embedded & Cloud-Scale** |

---

## 3. Target Benchmark Suites: Specifications & Metrics

### 3.1 LoCoMo (Snap Research, arXiv:2402.17753)
- **Focus:** Very long-term multi-session conversational memory.
- **Dataset Scale:** Conversations averaging 300 turns and ~9,000 tokens across up to 35 distinct sessions.
- **Question Types:**
  - *Single-hop recall:* Direct fact lookup from a past session.
  - *Multi-hop reasoning:* Combining two or more facts stated across disparate sessions.
  - *Temporal reasoning:* Determining order of events, duration, or whether a past state has changed.
  - *Causal reasoning & summarization:* Identifying reasons for agent/user state changes.
- **Primary Metrics:**
  - Token-level overlap F1.
  - LLM-as-a-judge score (0.0 to 1.0 or 1 to 5) evaluating factual correctness, completeness, and hallucination absence.

### 3.2 LongMemEval (ReMe / AgentScope, arXiv:2410.10813)
- **Focus:** Long-horizon agent interaction and memory maintenance.
- **Four Core Competencies:**
  1. *Accurate Retrieval (AR):* Pinpoint retrieval of specific historical facts without distractor interference.
  2. *Test-Time Learning (TTL):* Learning user instructions, error lessons, and preferences in early turns and correctly applying them in later turns.
  3. *Long-Range Understanding (LRU):* Synthesizing narrative arcs and multi-session developments across extensive interaction sequences.
  4. *Conflict Resolution (CR):* Recognizing when an old fact has been updated or invalidated by a new fact, answering with the latest ground truth while acknowledging the historical transition when queried.
- **Primary Metrics:**
  - GPT-4o / LLM-as-a-Judge Accuracy.
  - Recall@k and Precision@k for retrieved memory units.
  - Faithfulness (percentage of generated assertions grounded in retrieved memory).

### 3.3 BEAM (Agent Memory Benchmark / Vectorize / arXiv:2502.xxxxx)
- **Focus:** Task-driven agent memory evaluated at massive scale.
- **Dataset Scale:** 100 narrative-coherent conversations spanning 4 token tiers: **128K, 500K, 1M, and 10M tokens**, probed with 2,000 human-validated questions.
- **10 Core Memory Abilities:**
  - Temporal reasoning and chronological ordering.
  - Knowledge updates and contradiction resolution.
  - Information extraction under heavy distraction.
  - Multi-session preference following and personality adaptation.
  - Cross-session multi-hop inference.
  - Tool-use and environment state recall.
- **Primary Metrics:**
  - *Judge Accuracy:* Gold-standard rubric matching via LLM-as-a-judge.
  - *Context Efficiency:* Total prompt tokens consumed per question (penalizing context stuffing).
  - *Latency:* End-to-end response time ($p50$ and $p95$).

### 3.4 MemoryAgentBench (HUST / ICLR 2026, arXiv:2507.05257)
- **Focus:** Dynamic memory evaluation via incremental multi-turn interactions.
- **Evaluation Paradigm:** **"Inject once, query multiple times"**—simulates an ongoing deployment where conversations and actions stream continuously, followed by multiple intermittent evaluation probes.
- **Core Datasets:** Reformulated dialog benchmarks + newly constructed **EventQA** and **FactConsolidation** datasets.
- **Primary Metrics:**
  - Exact match / token F1.
  - LLM-as-a-judge accuracy.
  - Cumulative ingestion overhead (time and compute required to maintain memory over hundreds of incremental turns).

### 3.5 AMA-Bench (ICML 2026, arXiv:2602.22769)
- **Focus:** Memory across long-horizon agent execution trajectories (coding agent sessions, terminal commands, web navigation, multi-agent collaborations).
- **Two-Stage Unified Interface:**
  - Stage 1 (Construction): `memory_construction(traj_text, task)` $\rightarrow$ Memory structure.
  - Stage 2 (Retrieval): `memory_retrieve(memory, question)` $\rightarrow$ Context string.
- **Task Types:** Open-ended trajectory QA and Multiple Choice Questions (MCQ) evaluating agent decision rationale, tool output recall, failure diagnosis, and recovery actions.
- **Agent Baselines:** Directly compares memory modules against full-context LLMs and tool-using coding agents (e.g., Claude Code, Codex).
- **Primary Metrics:** Open-ended answer accuracy, judge agreement score, and context compression ratio.

### 3.6 Dataset Snapshot Pins and Licensing (locked for the two first suites)

These pins are locked; Phase 100480 must not re-decide them without a recorded reason. Datasets are downloaded at benchmark time and never committed to this repository. The §5.4 anti-overfitting partition (60% train / 20% canary / 20% blind test, split at the conversation-session level) applies to both suites; the partition is implemented in Phase 100480, and the pins below are the raw snapshots it will split.

#### LoCoMo-style suite (Snap Research)

| Field | Value |
|---|---|
| Identity | LoCoMo — *Evaluating Very Long-Term Conversational Memory of LLM Agents*, Maharana et al., ACL 2024 ([arXiv:2402.17753](https://arxiv.org/abs/2402.17753)) |
| Source | https://github.com/snap-research/locomo |
| Snapshot pin | Repo commit `3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376` (2024-08-13); data file `data/locomo10.json`, git blob `d95b872480b413d935821fdc3c84f8a8f5f29e73` |
| Pin verification | `git hash-object` on the fetched file at the pinned commit returned the exact blob hash above |
| Size | 10 conversations, 1,986 annotated QA items; `data/locomo10.json` = 2,805,274 bytes |
| Download method | `https://raw.githubusercontent.com/snap-research/locomo/3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376/data/locomo10.json` |
| License | CC BY-NC 4.0 (`LICENSE.txt` in the pinned commit: *Attribution-NonCommercial 4.0 International*) |
| Use/distribution notes | Attribution required; **no redistribution** — the repo must fetch the file from the official source and must not vendor `locomo10.json`. Non-commercial-only terms are compatible with internal evaluation use. Multimodal fields are URL/caption metadata only (images are not released upstream) and are out of scope for the text-memory runner. |
| QA category notes | Categories: 1 single-hop (282 items), 2 temporal (321), 3 multi-hop (96), 4 open-domain (841), 5 adversarial (446, uses the separate `adversarial_answer` field). Category-5 abstention handling is a documented Phase 100480 task; the sample calibration covered categories 1–4. |

#### LongMemEval-style suite (Wu et al.)

| Field | Value |
|---|---|
| Identity | LongMemEval — *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory*, Wu et al. ([arXiv:2410.10813](https://arxiv.org/abs/2410.10813)) |
| Source | https://github.com/xiaowu0162/LongMemEval |
| Snapshot pin | Repo commit `9e0b455f4ef0e2ab8f2e582289761153549043fc`; data release `huggingface.co/datasets/xiaowu0162/longmemeval-cleaned` |
| Pin hashes | `longmemeval_oracle.json` sha256 `821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c` (15,388,478 bytes); `longmemeval_s_cleaned.json` sha256 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442` (277,383,467 bytes); `longmemeval_m_cleaned.json` sha256 `9d79e5524794a2e6900a3aa9cb7d9152c5a3e8319c9a87c25494ba1eacee495f` (2,737,100,077 bytes) |
| Pin verification | The oracle split was fetched and its sha256 matches the HuggingFace LFS oid byte-for-byte. The S and M splits were resolved through the HF API (size + sha256 recorded above); full-file download is deferred to Phase 100480. |
| Download method | `https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/<file>` (per the upstream README) |
| License | MIT (repo `LICENSE`, Copyright (c) 2024 Di Wu; upstream paper states the data release uses MIT). Redistribution permitted with attribution; the repo still fetches rather than vendors the data. |
| Scale notes | 500 curated questions (temporal-reasoning 133, multi-session 133, knowledge-update 78, single-session-user 70, single-session-assistant 56, single-session-preference 30 in the oracle split counts — six question types). S ≈ 115k tokens of history per question; M ≈ 500 sessions (~1.5M tokens) per question. The oracle split (evidence sessions only) is the Phase 100480 adapter target; S is the stretch target; M is out of the first-build scope (host budget, see §10). |

---

## 4. Clio Architectural Mapping

`clio` is purpose-built with architectural features that directly map to the core weaknesses of traditional RAG and match the requirements of these benchmarks:

```
┌──────────────────────────────┬──────────────────────────────┬─────────────────────────────┐
│ Benchmark Challenge          │ Clio Mechanism       │ Target Crate                │
├──────────────────────────────┼──────────────────────────────┼─────────────────────────────┤
│ Temporal Reasoning           │ Bi-temporal model (§4.6)     │ clio-store, clio-history        │
│ Conflict Resolution (CR)     │ Invalidation & supersession  │ clio-store, clio-belief         │
│ Accurate Retrieval (AR)      │ 5-factor admission scoring   │ clio-admission                │
│ Long-Range Understanding     │ MemTree hierarchical index   │ clio-write, clio-history        │
│ Preference Following         │ Persona companion object     │ clio-persona                  │
│ Multi-hop Inference          │ Co-activation graph edges    │ clio-retrieve, clio-store       │
│ Zero-Memory Efficiency       │ Intent Gate classifier       │ clio-retrieve                 │
│ Exact Value Fidelity         │ FR-4 span grounding (≥99%)   │ clio-write, scripts/span_verify│
└──────────────────────────────┴──────────────────────────────┴─────────────────────────────┘
```

### 4.1 Bi-Temporal Model vs. Temporal Reasoning & Conflict Resolution
- Traditional vector RAG fails on temporal queries (e.g., *"Where does Alice live now?"* vs *"Where did Alice live in May?"*) because embedding similarity matches both addresses equally.
- `clio` tracks two distinct time intervals for every memory item:
  - `valid_time`: The interval $[t_{valid\_start}, t_{valid\_end})$ during which the fact was true in the real world.
  - `transaction_time`: The interval $[t_{tx\_start}, t_{tx\_end})$ during which the record was stored and active in the system.
- When a fact changes, `clio` closes `valid_time` and `transaction_time` on the superseded record (PR-6). Current queries filter for open transaction/valid intervals, while historical temporal queries query as-of past timestamps, resolving conflicts deterministically.

### 4.2 Five-Factor Admission vs. Memory Bloat
- Benchmarks with long horizons (BEAM 1M+, LoCoMo 35 sessions) suffer from memory bloat when every trivial sentence is retained.
- `clio-admission` enforces a category gate and a five-factor linear admission scoring formula:
  $$\text{Score} = w_1 \cdot \text{Utility} + w_2 \cdot \text{Confidence} + w_3 \cdot \text{Novelty} + w_4 \cdot \text{Recency} + w_5 \cdot \text{TypePrior}$$
- Items scoring below threshold $\theta$ are rejected before touching the index, ensuring that the memory bank maintains high signal-to-noise ratio.

### 4.3 MemTree & EMA vs. Long-Range Understanding (LRU)
- Answering narrative summary questions across 300 turns cannot rely on leaf item retrieval alone.
- `clio-write` maintains **MemTree**, an incremental, hierarchical temporal index with asynchronous dirty-path refresh. Leaf nodes represent episodic chunks; higher levels represent multi-session summaries.
- Combined with continuous Exponential Moving Average (EMA) updates for user preferences, `clio` synthesizes long horizons without re-reading the entire trajectory.

### 4.4 Hybrid Retrieval & Co-Activation Graph vs. Multi-Hop Reasoning
- `clio-retrieve` combines dense vector search (via TEI / embeddings), lexical BM25 search, and graph traversal over `assoc_edges`.
- Co-activation edges track items that are frequently retrieved together, applying saturating growth, lazy decay, pruning, and hub distillation. When a multi-hop query retrieves entity A, traversal along co-activation edges surfaces entity B even if B lacks direct lexical overlap with the query.

### 4.5 Persona Companion & Belief Objects vs. Test-Time Learning (TTL)
- User preferences are stored in the `clio-persona` companion object (`stable` entries with bi-temporal invalidation and `preference` entries with EMA updates).
- Persona entries are injected into the prompt under a dedicated token budget and are **not** gated by the Intent Gate, guaranteeing immediate adaptation to user instructions across turns.
- Evolving propositions are tracked via `clio-belief` objects with append-only `confidence_history`.

---

## 5. Standardized Evaluation Harness (`am-bench`)

To execute the benchmark reliably, we define a unified evaluation harness architecture.

### 5.1 Architecture of the Harness

```
                                  ┌────────────────────────┐
                                  │   Benchmark Datasets   │
                                  │ LoCoMo / LongMemEval / │
                                  │ BEAM / MABench / AMA   │
                                  └───────────┬────────────┘
                                              │ Stream turns
                                              ▼
                                 ┌──────────────────────────┐
                                 │   am-bench Coordinator   │
                                 └────────────┬─────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         ┌─────────────────────────┐                     ┌─────────────────────────┐
         │   System Adapter: AM    │                     │ System Adapters: Rivals │
         │ (clio-mcp / clio-lib facade)│                     │ (Mem0/Hindsight/Honcho/ │
         └────────────┬────────────┘                     │        Mnemosyne)       │
                      │ Ingest / Query                   └────────────┬────────────┘
                      ▼                                               │ Ingest / Query
         ┌─────────────────────────┐                                  ▼
         │ Ingest / Query Latency  │                     ┌─────────────────────────┐
         │ Token Budget Tracker    │                     │ Ingest / Query Latency  │
         └────────────┬────────────┘                     │ Token Budget Tracker    │
                      │                                  └────────────┬────────────┘
                      ▼                                               ▼
         ┌─────────────────────────┐                     ┌─────────────────────────┐
         │  Answer Generator (LLM) │                     │  Answer Generator (LLM) │
         └────────────┬────────────┘                     └────────────┬────────────┘
                      │ Generated answers                             │ Generated answers
                      └───────────────────────┬───────────────────────┘
                                              ▼
                                ┌──────────────────────────┐
                                │   LLM-as-a-Judge Suite   │
                                │ (GPT-4o / Claude / O3)   │
                                └─────────────┬────────────┘
                                              ▼
                                ┌──────────────────────────┐
                                │ Standardized Score Report│
                                │  (Accuracy, Cost, p95)   │
                                └──────────────────────────┘
```

### 5.2 Unified System Adapter Interface
Every benchmarked system (including `clio` and rivals) must implement the same interface:

```python
class MemoryBenchmarkAdapter(ABC):
    @abstractmethod
    def reset(self, session_id: str) -> None:
        """Clear state and prepare fresh memory bank for a test case."""
        pass

    @abstractmethod
    def ingest(self, session_id: str, turn: DialogueTurn) -> IngestResult:
        """
        Ingest a conversation turn or trajectory chunk.
        Returns execution latency (ms), tokens processed, and write success.
        """
        pass

    @abstractmethod
    def retrieve(self, session_id: str, query: str, token_budget: int) -> RetrievalResult:
        """
        Retrieve context string given a question and a hard token budget.
        Returns retrieved context, latency (ms), and actual tokens retrieved.
        """
        pass

    @abstractmethod
    def answer(self, session_id: str, query: str, generator_llm: str) -> str:
        """Optional end-to-end answering using retrieved context."""
        pass
```

### 5.3 Unified LLM-as-a-Judge Protocol
To avoid scoring drift across experiments:
1. **Model:** Pinned judge model (`gpt-4o-2024-08-06` or `gemini-2.5-flash`) run at `temperature = 0.0`.
2. **Structured Output:** Pydantic schema enforcing structured ratings:
   - `accuracy_score` (0.0 to 1.0): Did the response answer the question correctly based on the gold standard?
   - `temporal_correctness` (bool): Did the answer respect valid timestamps and supersessions?
   - `hallucination_penalty` (0.0 to 1.0): Were extra ungrounded facts invented?
   - `explanation` (str): Concise chain-of-thought justification.
3. **Double Blind Grading:** The judge receives the question, gold answer, and candidate answer with system names masked.

### 5.3.1 Judge Decision (locked, spike-calibrated)

**Selected: calibrated LLM-as-a-judge**, two-tier, replacing token F1 as the primary metric. Token F1 remains as a deterministic cross-check and fallback, not the primary score.

| Tier | Judge | Role | Measured properties (spike calibration) |
|---|---|---|---|
| Tier 1 — inner optimization loop | **Local `Qwen2.5-1.5B-Instruct` (Q4_K_M)** via llama.cpp, `temperature = 0.0`, structured JSON output per §5.3 | Fast, free scoring inside tuning trials | Discrimination agreement 60/60 calls (30/30 correct-answer probes ≥ 0.7, 30/30 wrong-answer probes < 0.7; LoCoMo 18/18 items, LongMemEval-oracle 12/12); consistency 0/60 verdict mismatches across two identical passes; latency mean 8.5 s / p95 11.0 s per call on the 4-core spike host; cost $0.00 |
| Tier 2 — canary gate & official leaderboard | **`gpt-4o-2024-08-06`** at `temperature = 0.0` (§5.3 protocol unchanged) | Release scoring and scorecards | Not runnable in the spike environment (no hosted judge credentials); cost estimated at ~$2.50/1M input + ~$10/1M output → ~$15 or less per full official sweep of ~2,500 probes (see §10 assumptions) |

Calibration sample design (seed 100460, scripts run ad hoc, not committed): 30 items — LoCoMo categories 1/2/3/4 (18 items across the pinned conversations) and LongMemEval-oracle across five of its six question types (12 items; `single-session-preference` not sampled — see the calibration limitations below). Each item was judged twice: candidate = gold answer verbatim (expected correct) and candidate = the gold answer of a different question from the same conversation / question type (expected wrong). Judges produced the §5.3 schema (`accuracy_score`, `temporal_correctness`, `hallucination_penalty`, `explanation`) under a JSON schema constraint. A swap-position spot check (4 comparative pairs × both orders, §5.8) picked the better response in 7/8 cases, confirming that swap-position scoring must stay in Phase 100480 rather than being dropped for the small local judge.

**Why not token F1 as primary:** on the same sample F1 discriminates verbatim pairs (mean 1.00 vs 0.04), but it requires the candidate to share surface wording; it systematically penalizes valid paraphrases and abstention phrasings, which are core to temporal-reasoning and conflict-resolution probes. The LLM judge handles semantic equivalence; its measured weakness (positional instability at 1.5B scale) is mitigated by §5.8's two-pass geometric-mean protocol.

**Known calibration limitations (carried into Phase 100480):**
- The sample used verbatim gold vs wrong-answer pairs; it does not yet measure the paraphrase case where the judge outperforms F1. Phase 100480 adds paraphrased and stale-fact candidate arms to the calibration set before official scoring.
- LongMemEval's `single-session-preference` type was not in the sample: the 12 LongMemEval items covered five of the six question types (temporal-reasoning, multi-session, knowledge-update, single-session-user, single-session-assistant). Phase 100480 adds `single-session-preference` items alongside the LoCoMo category-5 abstention arm.
- LoCoMo category 5 (adversarial, separate `adversarial_answer` field) was not in the sample; abstention scoring is part of the Phase 100480 judge integration.
- Tier-2 hosted judging is untested end to end pending credentials via the standard secret mechanism; if provisioning fails, Tier 2 falls back to the local judge and official scores are flagged as provisional.

---

### 5.4 Data Partitioning & Anti-Overfitting Protocol (Addresses Issue 01)

To prevent hyperparameter optimization from memorizing benchmark probe questions, all five benchmark datasets are strictly divided into three session-isolated partitions:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Total Benchmark Dataset Split (100%)                            │
├──────────────────────────────────┬──────────────────────────┬──────────────────────────┤
│         60% Train Split          │     20% Canary / Dev     │      20% Blind Test      │
│  (Used by Optuna search trials)  │  (Used by Canary Gate)   │ (Held out for releases)  │
└──────────────────────────────────┴──────────────────────────┴──────────────────────────┘
```

1. **Session-Level Grouping:** Splitting is performed at the conversation session level (not individual turn level). All turns and probes originating from a single user session remain within the same split to eliminate temporal and conversational context leakage.
2. **Blind Test Isolation:** The 20% Blind Test partition is cryptographically checksummed and physically isolated. It is never accessed by the Optuna search loop or canary evaluators, and is only evaluated once per release milestone to calculate final official scores.
3. **Cross-Validation Rotation:** For smaller datasets (such as LoCoMo), a 5-fold cross-validation scheme is supported, where each fold serves as the holdout dev set in turn.

---

### 5.5 Tiered Ingestion Architecture & Cost Throttling (Addresses Issue 02)

Massive-scale benchmarks like BEAM (up to 10M tokens) and AMA-Bench (hundreds of execution turns) risk prohibitive API fees and multi-day execution times if turn-by-turn frontier LLM extraction is run synchronously. The harness implements a three-tier ingestion pipeline:

```
   Raw Trajectory / Dialogue Stream
                  │
                  ▼
   ┌──────────────────────────────┐
   │ Ingestion Volume Classifier  │
   └──────────────┬───────────────┘
                  │
     ┌────────────┴────────────┐
     ▼ (>128K bulk background) ▼ (Recent turns / High priority)
┌─────────────────────────┐  ┌─────────────────────────┐
│ Tier 1: Fast Local SLM  │  │ Tier 2: Frontier LLM    │
│ (NuExtract-tiny/Qwen 3B)│  │ (GPT-4o-mini / Gemini)  │
│ or Heuristic Chunking   │  │ Online Structured Extr. │
└────────────┬────────────┘  └────────────┬────────────┘
             │                            │
             └────────────┬───────────────┘
                          ▼
            ┌───────────────────────────┐
            │ Hard Spending Budget Cap  │ (Max $15/trial, $50/CI run)
            └─────────────┬─────────────┘
                          ▼
            ┌───────────────────────────┐
            │ Asynchronous Batch Insert │
            └───────────────────────────┘
```

1. **Local SLM Bulk Ingestion:** For historical background turns beyond the recent 128K window, ingestion offloads extraction to local small language models (e.g., `NuExtract-tiny` via the local Compose endpoint or `Qwen-2.5-3B-Instruct`), achieving 200+ tokens/sec with zero cloud API expense.
2. **Frontier Extraction for Leaves:** Recent conversational turns, critical error logs, and direct user instructions utilize frontier LLM extraction to ensure high structured fidelity.
3. **Hard API Cost Caps:** The runner enforces hard expenditure limits ($15 maximum per Optuna trial; $50 per CI test suite). If a trial breaches its financial ceiling, it terminates early and receives a proportional loss penalty.
4. **Worker Pool Concurrency:** Ingestion workers are rate-limited via token bucket throttles to avoid hitting commercial API quota ceilings (e.g., Mem0 or OpenAI rate limits).

---

### 5.6 Standardized Latency Measurement Protocol (Addresses Issue 03)

Comparing in-process embedded databases (such as Clio on SQLite and Mnemosyne) with remote cloud APIs (Mem0, Honcho, Hindsight) can produce misleading comparisons if network transport latency is not isolated.

The harness records and reports two orthogonal latency metrics for every operation:

```
Total Round-Trip Time (End-to-End Client Latency)
├── Network Request Egress (WAN)
├── Cloud TLS Handshake
├── Engine Execution Latency (Server-side storage, graph traversal, & ranking)  <-- FAIR ALGORITHMIC COMPARISON
├── Network Response Ingress (WAN)
└── Client-side JSON Deserialization
```

1. **`engine_execution_latency_ms` (Algorithmic Speed):** Measures pure compute time spent in storage queries, dense vector dot-products, BM25 indexing, graph traversal, and fusion ranking. For cloud providers, this is parsed from server response headers (`X-Process-Time` / `server-timing`); for local engines, it is timed via high-resolution monotonic clocks (`std::time::Instant`).
2. **`end_to_end_client_latency_ms` (Operational Latency):** Measures total elapsed time from client call invocation to parsed result return. This metric assesses real-world developer experience and deployment viability.
3. **Reporting Requirement:** All published comparison charts MUST explicitly label whether latencies represent Engine Execution or End-to-End Client latency.

---

### 5.7 Standardized Reference Tokenizer (Addresses Issue 04)

To eliminate tokenizer variance (which can reach 15–25% between OpenAI, Anthropic, and Llama tokenizers), all adapters in `am-bench` use a standardized canonical reference tokenizer:

1. **Canonical Encoding:** The harness pins `tiktoken` with the **`cl100k_base`** encoding as the universal standard for all token calculations.
2. **Budget Enforcement:** When a benchmark probe specifies `token_budget = 4096`, all adapters truncate or compose their prompt context using this exact tokenizer.
3. **Metric Normalization:** All reported token efficiency metrics ($\overline{\text{TokensInjected}}$) are computed by passing the final retrieved context string through the canonical tokenizer, guaranteeing an objective apples-to-apples comparison regardless of the underlying LLM used by the memory provider.

---

### 5.8 Tiered Judging Architecture & Positional Bias Mitigation (Addresses Issue 05)

To prevent the LLM judge from becoming a cost and latency bottleneck during large-scale optimization:

1. **Two-Tier Judging Strategy:**
   - **Tier 1 (Inner Optimization Loop):** Optuna hyperparameter trials evaluate responses using a fast, high-throughput, cost-effective judge (`gemini-2.5-flash` or local `qwen-2.5-14b-instruct`). This reduces trial evaluation cost by over 90% while preserving relative ranking signal.
   - **Tier 2 (Canary Gate & Official Leaderboard):** Full verification before profile promotion and final scorecard generation runs strictly on the gold-standard judge (`gpt-4o-2024-08-06` at `temperature = 0.0`).
2. **Positional Bias Elimination (Swap-Position Scoring):** For comparative A/B evaluations (comparing candidate memory against baseline), the judge evaluates both orders:
   - Pass 1: Prompt presents Candidate as Response A and Baseline as Response B.
   - Pass 2: Prompt presents Baseline as Response A and Candidate as Response B.
   - Final score is the geometric mean of both passes, canceling positional preference bias.

---

### 5.9 Synthetic Dialogue Generation & Dynamic Expansion (Unlimited Resource Roadmap)

To prevent benchmark saturation over multi-month development cycles, the harness incorporates an automated synthetic dialogue generator:
1. **Dynamic Scenario Synthesis:** Uses generative agent seeds to synthesize new multi-session dialogue trees with known ground-truth temporal shifts, preference updates, and entity relationships.
2. **Automatic Probe Generation:** Automatically compiles single-hop, multi-hop, and conflict resolution questions paired with formal proof traces.
3. **Continuous Test Refresh:** Refreshes 10% of the Blind Test split monthly with verified synthetic scenarios, ensuring that models cannot overfit to static public benchmarks.

---

### 5.10 Distilled Local SLM Evaluator (Unlimited Resource Roadmap)

To achieve complete data privacy and zero cloud API dependency during evaluation:
1. **Distillation Pipeline:** Fine-tunes a specialized 7B/14B parameter local language model (e.g., based on Qwen 2.5 or Llama 3) specifically on 50,000 double-blind grading judgements produced by GPT-4o and human annotators.
2. **Deterministic Grading Engine:** The resulting model runs locally via vLLM, producing identical JSON scoring schemas at sub-50ms latency per evaluation, eliminating cloud evaluation costs entirely.

---

## 6. Implementation Roadmap: 12-Step Execution Plan & Effort Estimation

### 6.1 Effort Estimation Summary

The complete benchmark implementation requires an estimated **145 engineer hours** (range: **120–160 hours**, representing ~3.5 full-time engineering weeks).

| Step | Title | Target Benchmark / System | Estimated Hours | Dependencies |
| :--- | :--- | :--- | :---: | :--- |
| **Step 1** | Harness Scaffolding & Core Interface Contracts | All | 8 h | None |
| **Step 2** | Double-Blind LLM-as-a-Judge Evaluation Engine | All | 10 h | Step 1 |
| **Step 3** | Native `ClioAdapter` (MCP + CLI) | Clio | 12 h | Step 1 |
| **Step 4** | LoCoMo Dataset Pipeline & Baseline Runner | LoCoMo | 10 h | Steps 2, 3 |
| **Step 5** | Rival Adapters 1: Mnemosyne & Mem0 Integration | Mnemosyne, Mem0 | 12 h | Steps 1, 4 |
| **Step 6** | LongMemEval Integration & Competency Probes | LongMemEval | 14 h | Steps 4, 5 |
| **Step 7** | MemoryAgentBench Streaming Pipeline | MemoryAgentBench | 10 h | Step 6 |
| **Step 8** | BEAM Massive-Scale Harness (128K–1M Tokens) | BEAM | 14 h | Step 7 |
| **Step 9** | Performance Profiling: Intent Gate & Latency Telemetry | Clio | 10 h | Step 8 |
| **Step 10** | AMA-Bench Trajectory Ingestion & Tool-Use QA | AMA-Bench | 15 h | Steps 8, 9 |
| **Step 11** | Rival Adapters 2: Hindsight & Honcho Integration | Hindsight, Honcho | 14 h | Steps 5, 10 |
| **Step 12** | Continuous CI Benchmarking & Tuning Flywheel | Full Suite | 16 h | Steps 1–11 |
| **Total** | **End-to-End Implementation** | **All 5 Benchmarks & 5 Rivals** | **145 h** | — |

---

### 6.2 Detailed 12-Step Breakdown

#### Step 1: Harness Scaffolding & Core Interface Contracts (8 hours)
- **Objective:** Establish the workspace structure, shared data classes, and the base `MemoryBenchmarkAdapter` abstraction.
- **Tasks:**
  1. Create the `benchmarks/` workspace root with subdirectories: `benchmarks/{adapters,datasets,runners,judges,metrics,reports}`.
  2. Implement core Python contracts: `DialogueTurn`, `TrajectoryStep`, `IngestResult`, `RetrievalResult`, and `EvalReport`.
  3. Define abstract lifecycle hooks: `reset(session_id)`, `ingest(session_id, turn)`, `retrieve(session_id, query, budget)`, and `healthcheck()`.
- **Deliverables:** `benchmarks/core/types.py` and `benchmarks/core/adapter.py`.

#### Step 2: Double-Blind LLM-as-a-Judge Evaluation Engine (10 hours)
- **Objective:** Build a deterministic, reproducible scoring engine with double-blind masking.
- **Tasks:**
  1. Implement judge client with model pinning (`gpt-4o-2024-08-06` and `gemini-2.5-flash`) run strictly at `temperature=0.0`.
  2. Define Pydantic output schemas for scoring: `accuracy_score` (0.0–1.0), `temporal_correctness` (bool), `hallucination_penalty` (0.0–1.0), and `explanation` (chain-of-thought justification).
  3. Implement blind anonymization masking provider identities from judge prompts to ensure unbiased grading.
  4. Write unit tests comparing judge scores against human-annotated sample answers to confirm rubric alignment.
- **Deliverables:** `benchmarks/judges/llm_judge.py` and unit test fixtures.

#### Step 3: Native `ClioAdapter` (12 hours)
- **Objective:** Connect the evaluation harness directly to `clio`'s dual persistence backends.
- **Tasks:**
  1. Implement stdio MCP transport client calling `clio-mcp` tools (`memory_store`, `memory_retrieve`, `session_reset`).
  2. Add high-speed direct CLI / Rust FFI binding via `clio-lib` for fast batch evaluation runs without HTTP overhead.
  3. Support dual configuration profiles: SQLite local backend (`sqlite-vec`) and PostgreSQL backend (`pgvector`).
  4. Capture execution telemetry: ingestion duration, retrieval duration ($p50/p95$), and total tokens returned.
- **Deliverables:** `benchmarks/adapters/clio_adapter.py`.

#### Step 4: LoCoMo Dataset Pipeline & Baseline Runner (10 hours)
- **Objective:** Ingest the Snap Research LoCoMo dataset and execute initial single-hop and multi-hop QA probes.
- **Tasks:**
  1. Implement dataset downloader and parser for LoCoMo conversation sessions (up to 35 sessions, 300 turns per test).
  2. Build execution runner streaming dialogues session-by-session into the active adapter.
  3. Execute evaluation probes across single-hop, multi-hop, and temporal reasoning question categories.
  4. Generate standardized evaluation scorecards reporting token F1 and LLM judge score.
- **Deliverables:** `benchmarks/datasets/locomo.py` and `benchmarks/runners/run_locomo.py`.

#### Step 5: Rival Adapters 1: Mnemosyne & Mem0 Integration (12 hours)
- **Objective:** Integrate local SQLite rival (Mnemosyne) and dynamic memory rival (Mem0) into the harness.
- **Tasks:**
  1. Implement `MnemosyneAdapter` wrapping native SQLite graph tables (`working_memory`, `episodic_triples`, `canonical_facts`).
  2. Implement `Mem0Adapter` wrapping the `mem0ai` Python package (`add`, `search`, `get_all`, `reset`).
  3. Standardize token budgeting across adapters to ensure fair retrieval prompt sizing.
  4. Run initial head-to-head LoCoMo pilot run across `clio`, `mnemosyne`, and `mem0`.
- **Deliverables:** `benchmarks/adapters/mnemosyne_adapter.py` and `benchmarks/adapters/mem0_adapter.py`.

#### Step 6: LongMemEval Integration & Competency Probes (14 hours)
- **Objective:** Benchmark the four core competencies: Accurate Retrieval (AR), Test-Time Learning (TTL), Long-Range Understanding (LRU), and Conflict Resolution (CR).
- **Tasks:**
  1. Integrate LongMemEval dataset splits (LongMemEval-S, EventQA, FactConsolidation).
  2. Implement Conflict Resolution probe runner: explicitly check whether updated facts supersede older ones without leaking stale records.
  3. Implement Test-Time Learning probe runner: measure prompt adherence to dynamic user instructions introduced in early turns.
  4. Instrument bi-temporal invalidation metrics: track false-positive retrieval rate for closed transaction-time intervals.
- **Deliverables:** `benchmarks/datasets/longmemeval.py` and `benchmarks/runners/run_longmemeval.py`.

#### Step 7: MemoryAgentBench Streaming Pipeline (10 hours)
- **Objective:** Implement the "inject once, query multiple times" streaming interaction benchmark.
- **Tasks:**
  1. Implement streaming turn ingestion simulating continuous agent deployment over extended multi-turn interactions.
  2. Batch query probes against persistent memory states without inter-query resets.
  3. Track cumulative memory bloat: record index size, database row counts, and retrieval latency degradation across turn counts (10 to 500 turns).
  4. Compute memory efficiency curves (accuracy retention vs. interaction horizon).
- **Deliverables:** `benchmarks/datasets/mabench.py` and `benchmarks/runners/run_mabench.py`.

#### Step 8: BEAM Massive-Scale Harness (128K–1M Tokens) (14 hours)
- **Objective:** Stress-test memory scalability across massive context tiers (128K, 500K, and 1M tokens).
- **Tasks:**
  1. Ingest BEAM narrative-coherent conversational datasets across scale buckets.
  2. Implement probe runner covering BEAM's 10 memory categories (temporal ordering, contradiction resolution, multi-session inference).
  3. Track context compression ratio: compare retrieved token counts against full-context stuffing.
  4. Profile database index stability under heavy batch ingestion workloads.
- **Deliverables:** `benchmarks/datasets/beam.py` and `benchmarks/runners/run_beam.py`.

#### Step 9: Performance Profiling: Intent Gate & Latency Telemetry (10 hours)
- **Objective:** Measure retrieval bypass precision and verify time-to-queryable requirements.
- **Tasks:**
  1. Instrument Intent Gate false-negative vs. false-positive tracking on unneeded memory queries.
  2. Verify zero-token context injection and sub-10ms bypass latency when memory retrieval is skipped.
  3. Validate $NFR\text{-}2$ write-path latency: measure time-to-queryable for leaf nodes independent of background MemTree dirty-path maintenance jobs.
  4. Generate latency percentile distributions ($p50$, $p90$, $p95$, $p99$) for both SQLite and PostgreSQL backends.
- **Deliverables:** `benchmarks/metrics/latency_profiler.py` and `benchmarks/metrics/intent_gate_eval.py`.

#### Step 10: AMA-Bench Trajectory Ingestion & Tool-Use QA (15 hours)
- **Objective:** Benchmark memory retention across long-horizon agent execution traces and tool interactions.
- **Tasks:**
  1. Implement AMA-Bench two-stage interface: `memory_construction(traj_text, task)` and `memory_retrieve(memory, question)`.
  2. Parse execution traces (shell commands, tool parameters, error logs, return values) into `clio-history` (`FailureRecord`, task history).
  3. Execute open-ended trajectory QA and multiple-choice questions evaluating agent decisions and diagnostic reasoning.
  4. Compare retrieval accuracy against raw trajectory context window baselines.
- **Deliverables:** `benchmarks/datasets/amabench.py` and `benchmarks/runners/run_amabench.py`.

#### Step 11: Rival Adapters 2: Hindsight & Honcho Integration (14 hours)
- **Objective:** Integrate cloud-scale rival adapters (Hindsight and Honcho) and run full head-to-head comparisons.
- **Tasks:**
  1. Implement `HindsightAdapter` wrapping `hindsight-all` / PostgreSQL pgvector endpoints (`Retain`, `Recall`, `Reflect`).
  2. Implement `HonchoAdapter` connecting to Plastic Labs dialectic user modeling APIs.
  3. Execute identical cross-benchmark test suites across all five rivals (Hindsight, Mem0, Supermemory, Honcho, Mnemosyne) and Clio.
  4. Generate comparative Pareto frontier charts (Accuracy vs. Token Cost vs. Retrieval Latency).
- **Deliverables:** `benchmarks/adapters/hindsight_adapter.py`, `benchmarks/adapters/honcho_adapter.py`, and competitive scorecards.

#### Step 12: Continuous CI Benchmarking & Tuning Flywheel (16 hours)
- **Objective:** Automate regression benchmarking in CI and build hyperparameter tuning automation.
- **Tasks:**
  1. Create a lightweight "smoke benchmark" subset (15-minute runtime) runnable on GitHub Actions CI to catch quality regressions.
  2. Build a Bayesian / grid-search hyperparameter optimizer targeting:
     - Five admission weights ($w_1 \dots w_5$) and cutoff $\theta$ in `clio-admission`.
     - Hybrid fusion weights ($\alpha_{dense}$, $\alpha_{lexical}$, $\alpha_{graph}$) in `clio-retrieve`.
     - Co-activation decay rate $\lambda$ and hub distillation threshold in `assoc_edges`.
  3. Establish automated performance report generation outputting Markdown and JSON artifacts.
- **Deliverables:** `.github/workflows/benchmarks.yml` and `benchmarks/tuning/optimizer.py`.

---

## 7. The Continuous Improvement Engine & Feedback System

The evaluation suite is designed not as a passive reporting tool, but as an **autonomous, closed-loop continuous improvement system**. When benchmark runs execute, failure signatures are extracted into structured diagnostic telemetry, fed into an automated hyperparameter optimizer, verified against a strict non-regression canary gate, and promoted into production configuration profiles without service restarts.

```
                          ┌─────────────────────────────────────────────────────────┐
                          │                am-eval-loop Controller                  │
                          └────────────────────────────┬────────────────────────────┘
                                                       │
                     ┌─────────────────────────────────┴─────────────────────────────────┐
                     ▼                                                                   ▼
       ┌───────────────────────────┐                                       ┌───────────────────────────┐
       │   1. EVALUATE & PROBE     │                                       │   5. PROMOTE & HOT-RELOAD │
       │ Run benchmarks against AM │                                       │ Commit TOML profile & run │
       │ (LoCoMo, LongMem, BEAM)   │                                       │ clio-config config_profile  │
       └─────────────┬─────────────┘                                       └─────────────▲─────────────┘
                     │                                                                   │ Passes canary
                     ▼                                                                   │
       ┌───────────────────────────┐                                       ┌─────────────┴─────────────┐
       │   2. DIAGNOSE & PARSE     │                                       │   4. CANARY REGRESSION    │
       │ Extract EvalTelemetry JSON│                                       │ Shadow eval on held-out   │
       │ & tag failure classes     │                                       │ split: Acc >= 0, p95 <= 5%│
       └─────────────┬─────────────┘                                       └─────────────▲─────────────┘
                     │                                                                   │
                     ▼                                                                   │ Candidate config
       ┌───────────────────────────┐                                                     │
       │   3. SAMPLE HYPERPARAMS   │─────────────────────────────────────────────────────┘
       │ Optuna Bayesian TPE loop  │
       │ optimize objective J(Φ)   │
       └───────────────────────────┘
```

---

### 7.1 Closed-Loop Controller State Machine

The loop runner (`benchmarks/tuning/controller.py`) executes as a deterministic state machine:

```
[IDLE] ──(trigger: cron / git push / drift)──► [RUNNING_BENCHMARK]
                                                       │
                                                       ▼
[SAMPLING_CANDIDATE] ◄──(aggregate telemetry)─── [PARSING_DIAGNOSTICS]
         │
         ▼
[CANARY_EVALUATION] ──(fails regression bar)───► [REJECT_CANDIDATE] ──► [IDLE]
         │
         ▼ (passes regression bar)
[PROMOTE_PROFILE] ──► [COMMIT_GIT_ARTIFACT] ──► [APPLY_HOT_RELOAD] ──► [IDLE]
```

1. **State `RUNNING_BENCHMARK`:** Executes target benchmarks in parallel across isolated test banks.
2. **State `PARSING_DIAGNOSTICS`:** Parses LLM-judge logs and latency records into structured `EvalTelemetry` records.
3. **State `SAMPLING_CANDIDATE`:** Bayesian optimizer (Optuna TPE) samples candidate parameter set $\Phi_{cand}$ within defined search spaces.
4. **State `CANARY_EVALUATION`:** Runs $\Phi_{cand}$ against a held-out canary split; compares against baseline $\Phi_{base}$.
5. **State `PROMOTE_PROFILE`:** Serializes $\Phi_{cand}$ to `benchmarks/profiles/<deployment>.toml` and invokes `config_profile_apply`.

---

### 7.2 Diagnostic Error Telemetry Schema (`EvalTelemetry`)

Every failed evaluation probe outputs a structured diagnostic artifact (`benchmarks/telemetry/<run_id>.jsonl`):

```json
{
  "telemetry_schema_version": "2026-09-20",
  "run_id": "eval_20260920_215012",
  "probe_id": "locomo_session_14_q03",
  "benchmark": "locomo",
  "competency": "conflict_resolution",
  "question": "What is the user's preferred editor as of session 14?",
  "ground_truth": "Neovim (updated from VS Code in session 11)",
  "candidate_answer": "The user prefers VS Code.",
  "judge_verdict": {
    "accuracy_score": 0.0,
    "temporal_correctness": false,
    "hallucination_penalty": 0.0,
    "failure_class": "stale_fact_supersession"
  },
  "retrieval_trace": {
    "retrieved_item_ids": ["mem_item_0192a", "mem_item_0184b"],
    "retrieved_token_count": 312,
    "retrieval_latency_ms": 42.6,
    "intent_gate_decision": "search",
    "bi_temporal_anomalies": [
      {
        "item_id": "mem_item_0184b",
        "valid_interval": ["2026-01-01T00:00:00Z", "2026-03-01T00:00:00Z"],
        "transaction_interval": ["2026-01-01T00:00:00Z", "2026-03-01T00:00:00Z"],
        "error": "closed_interval_retrieved_on_current_query"
      }
    ]
  },
  "current_hyperparameters": {
    "theta": 0.50,
    "w_utility": 0.20,
    "w_novelty": 0.20,
    "alpha_dense": 0.60,
    "alpha_lexical": 0.20,
    "alpha_graph": 0.20
  }
}
```

---

### 7.3 Formal Hyperparameter Search Space (Optuna TPE)

The optimizer systematically searches over bounded parameter spaces targeting specific memory subsystems:

| Subsystem | Parameter | Type | Search Range | Default | Tuning Objective Impact |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **Admission** | `theta` ($\theta$) | Float | $[0.40, 0.85]$ | $0.50$ | Controls memory density vs. noise filtering. |
| **Admission** | $w_{utility}$ ($w_1$) | Float (Simplex) | $[0.10, 0.60]$ | $0.20$ | Prioritizes task-critical and operational facts. |
| **Admission** | $w_{confidence}$ ($w_2$) | Float (Simplex) | $[0.05, 0.40]$ | $0.20$ | Discards uncertain LLM extractions. |
| **Admission** | $w_{novelty}$ ($w_3$) | Float (Simplex) | $[0.10, 0.50]$ | $0.20$ | Prevents redundant item ingestion in long contexts. |
| **Admission** | $w_{recency}$ ($w_4$) | Float (Simplex) | $[0.05, 0.30]$ | $0.20$ | Tunes decay sensitivity for transient notes. |
| **Admission** | $w_{type\_prior}$ ($w_5$) | Float (Simplex) | $[0.05, 0.40]$ | $0.20$ | Prioritizes persona/facts over dialogue gist. |
| **Retrieval** | $\alpha_{dense}$ | Float (Simplex) | $[0.20, 0.70]$ | $0.50$ | Weight for vector semantic similarity. |
| **Retrieval** | $\alpha_{lexical}$ | Float (Simplex) | $[0.10, 0.50]$ | $0.30$ | Weight for BM25 exact symbol/number lookup. |
| **Retrieval** | $\alpha_{graph}$ | Float (Simplex) | $[0.05, 0.40]$ | $0.20$ | Weight for associative graph traversal. |
| **Intent Gate**| `gate_threshold` | Float | $[0.15, 0.60]$ | $0.30$ | Asymmetric threshold to prevent false-negative skips. |
| **Graph** | $\eta$ | Float | $[0.02, 0.25]$ | $0.10$ | Co-activation edge growth step. |
| **Graph** | $\lambda_{decay}$ | Float | $[0.005, 0.08]$| $0.02$ | Lazy decay rate for inactive association edges. |
| **Graph** | $w_{min}$ | Float | $[0.05, 0.30]$ | $0.15$ | Co-activation pruning floor. |
| **MemTree** | `leaf_chunk_tokens`| Int (step 64) | $[256, 1024]$ | $512$ | Chunk size for hierarchical temporal leaves. |

*Constraint:* Weights in simplex groups ($\sum_{i=1}^5 w_i = 1.0$ and $\alpha_{dense} + \alpha_{lexical} + \alpha_{graph} = 1.0$) are normalized using a Dirichlet projection prior.

---

### 7.4 Mathematical Objective Function

The optimizer evaluates each trial configuration $\Phi$ against a multi-objective loss function balancing accuracy, token cost, and latency:

$$J(\Phi) = \overline{\text{Accuracy}}(\Phi) - \beta \cdot \frac{\overline{\text{TokensInjected}}(\Phi)}{\text{Budget}} - \gamma \cdot \frac{p95(\Phi)}{\text{LatencyTarget}} - \delta \cdot \text{FalseNegativeRate}(\Phi)$$

Where:
- $\overline{\text{Accuracy}}(\Phi) \in [0.0, 1.0]$: Mean LLM-judge score across all evaluated benchmark probes.
- $\beta = 0.15$: Regularization penalty against bloated context prompt sizes.
- $\gamma = 0.10$: Latency penalty preventing slow graph traversals or expensive BM25 joins.
- $\delta = 0.50$: Heavy penalty on Intent Gate false negatives (skipping retrieval when memory was needed).

---

### 7.5 Automated Non-Regression Canary Gate

Before any candidate configuration $\Phi_{cand}$ is promoted to replace active baseline $\Phi_{base}$, it must pass the automated canary regression gate:

```python
def verify_canary_gate(baseline: EvalSummary, candidate: EvalSummary) -> bool:
    # 1. Overall Accuracy must improve
    if candidate.mean_accuracy < baseline.mean_accuracy + 0.015:
        return False
        
    # 2. No individual core competency may regress by more than 1%
    for comp in ["accurate_retrieval", "test_time_learning", "conflict_resolution", "long_range_understanding"]:
        if candidate.competency_scores[comp] < baseline.competency_scores[comp] - 0.01:
            return False
            
    # 3. Context token overhead must not increase by more than 5%
    if candidate.mean_tokens_injected > baseline.mean_tokens_injected * 1.05:
        return False
        
    # 4. p95 retrieval latency must not degrade by more than 5%
    if candidate.p95_latency_ms > baseline.p95_latency_ms * 1.05:
        return False
        
    # 5. Span fidelity must remain above release bar (requirement.md §8)
    if candidate.span_fidelity < 0.99:
        return False
        
    return True
```

---

### 7.6 Actionable Profile Deployment & Hot-Reload

Once a candidate configuration passes the Canary Gate, the controller automatically deploys it:

1. **Serialize Profile:** Writes `benchmarks/profiles/<deployment_type>.toml` with Git commit hash and timestamp.
2. **Apply Live Configuration:** Invokes `config_profile_apply` via `clio-mcp` or the Rust runtime API:
   ```bash
   am-cli config apply --profile benchmarks/profiles/tuned_production.toml
   ```
3. **Record Performance Diff:** Generates a Markdown audit log (`benchmarks/reports/diff_YYYYMMDD.md`) documenting before/after score deltas across all five benchmark suites.
4. **Git Commit Automation:** Commits the new profile to version control with automated changelog message:
   ```
   chore(tuning): promote optimized memory profile [Acc: +2.4%, Tokens: -8.1%, p95: -3ms]
   ```

---

### 7.7 Parameter Tuning Matrix

When telemetry flags persistent regression patterns, the automated optimizer prioritizes search spaces aligned with these specific subsystems:

| Failure Symptom | Target Benchmark | Target Crate & File | Primary Parameter | Remediation Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Stale facts returned** | LongMemEval (CR) | `clio-store/src/postgres.rs` | SQL Query Predicate | Enforce $t_{valid\_end} = \infty \land t_{tx\_end} = \infty$ by default. |
| **Exact entity lookup miss** | MemoryAgentBench (AR) | `clio-retrieve/src/fusion.rs` | `alpha_lexical` | Increase `alpha_lexical` (0.20 $\rightarrow$ 0.35); verify FR-4 span grounding. |
| **Multi-hop reasoning fail** | LoCoMo (Multi-hop) | `clio-retrieve/src/hybrid.rs` | `alpha_graph`, `w_min` | Increase `alpha_graph` (0.15 $\rightarrow$ 0.25); lower `w_min` (0.20 $\rightarrow$ 0.15). |
| **Memory bloat / High cost** | BEAM (1M tokens) | `clio-admission/src/lib.rs` | `theta`, `w_novelty` | Raise `theta` (0.50 $\rightarrow$ 0.65); increase `w_novelty` (0.15 $\rightarrow$ 0.25). |
| **Macro summary degraded** | LoCoMo (Summarization)| `clio-write/src/memtree.rs` | `leaf_chunk_tokens` | Decrease `leaf_chunk_tokens`; route queries to intermediate ancestors. |

---

### 7.8 Failure Remediation Playbooks

#### 1. Conflict Resolution (CR) & Temporal Reasoning
- **Benchmark Diagnostic:** In LongMemEval or BEAM, the agent is asked for the current state (e.g., *"What is Alice's current job?"*), but returns a stale, superseded fact from an earlier turn.
- **Root Cause:** Vector similarity between the query and the older fact is higher than the newer fact, and the retrieval engine lacks temporal interval filtering.
- **Remediation Action:**
  1. Inspect `clio-store` queries: ensure all active-state retrieval queries enforce bi-temporal constraints:
     $$\text{WHERE } t_{valid\_start} \le \text{now}() < t_{valid\_end} \text{ AND } t_{tx\_start} \le \text{now}() < t_{tx\_end}$$
  2. Verify that `clio-write`'s consolidation pipeline correctly sets $t_{valid\_end}$ and $t_{tx\_end}$ on older conflicting records (PR-6).
  3. Ensure vector search results are post-filtered or pre-filtered against open intervals before ranking.

#### 2. Accurate Retrieval (AR) & Span Grounding
- **Benchmark Diagnostic:** In MemoryAgentBench or LoCoMo, the agent fails to recall exact numbers, hashes, error codes, or function names.
- **Root Cause:** Dense embeddings compress high-entropy alphanumeric strings into blurry semantic vectors.
- **Remediation Action:**
  1. Increase lexical BM25 fusion weight $\alpha_{lexical}$ to at least $0.30$–$0.35$ in `clio-retrieve`.
  2. Verify that incoming snapshots satisfy FR-4 span-grounding requirements via [`scripts/span_verify.py`](file:///Users/aiuser/Documents/projects/agentmemoir/clio/scripts/span_verify.py) ($\ge 99\%$ exact span fidelity). Snapshots failing span grounding must be discarded or repaired before indexing.

#### 3. Multi-Hop Associative Recall
- **Benchmark Diagnostic:** In LoCoMo multi-session tests, questions require connecting Fact A (Session 2) and Fact B (Session 14), but only Fact A is retrieved.
- **Root Cause:** Fact B has zero lexical or direct semantic similarity to the query; retrieval depends entirely on graph edge traversal.
- **Remediation Action:**
  1. Boost `alpha_graph` from $0.15$ to $0.25$ in `clio-retrieve`.
  2. Lower the association pruning floor $w_{min}$ from $0.20$ to $0.15$ to preserve weakly reinforced connecting paths.
  3. Increase graph traversal radius to 2 hops for queries classified by the Intent Gate as complex or comparative.

#### 4. Memory Bloat & Token Efficiency
- **Benchmark Diagnostic:** On BEAM 500K and 1M token tests, total prompt tokens injected per turn escalate rapidly, degrading LLM response quality and increasing token cost.
- **Root Cause:** The admission engine admits casual dialogue pleasantries, affirmations, and transient observations.
- **Remediation Action:**
  1. Raise five-factor admission cutoff $\theta$ from $0.50$ to $0.65$ in `clio-admission`.
  2. Increase novelty weight $w_3$ and utility weight $w_1$, while depressing recency weight $w_4$.
  3. Verify that the Intent Gate operates with an asymmetric threshold, bypassing retrieval completely for chit-chat and purely deductive turns.

#### 5. Long-Range Understanding (LRU) & Event Summarization
- **Benchmark Diagnostic:** In LoCoMo event summarization, the agent produces disjointed, piecemeal answers that miss major multi-session narrative arcs.
- **Root Cause:** Retrieval injects only localized leaf episodic items, overflowing the token budget before synthesizing the global timeline.
- **Remediation Action:**
  1. Direct macro-level queries (detected by intent classifier) to intermediate nodes of the **MemTree** hierarchy in `clio-write`.
  2. Trigger dirty-path ancestor refreshes to update multi-session summary nodes before evaluation queries execute.
  3. Restrict leaf item injection to specific temporal anchors identified by the high-level tree walk.

---

### 7.9 Continuous Shadow Canary Deployment (Unlimited Resource Roadmap)

To validate memory configurations under realistic production workloads beyond synthetic datasets:
1. **Live Traffic Shadowing:** Production agent sessions asynchronously mirror read queries and write operations to a background shadow bank running candidate configuration $\Phi_{cand}$.
2. **Dual-Evaluation Comparator:** Measures real-world retrieval overlap, context token consumption, and engine latency without impacting live user sessions.
3. **Automated Rollback Safeguard:** If shadow error logs detect an ungrounded hallucination or an invalid transaction interval, the canary run is immediately aborted and flagged for engineer review.

---

## 8. Summary of Immediate Next Steps

1. **Scaffold the `benchmarks/` workspace directory** with standard dataset loaders and environment definitions.
2. **Implement `ClioAdapter`** connecting Python runners to `clio` via stdio MCP (`clio-mcp`) and native CLI (`clio-lib`).
3. **Run the LoCoMo baseline test** against `clio` (SQLite backend) and `mnemosyne` to record the first official benchmark score.
4. **Review initial scores** to calibrate the five admission weights ($w_1 \dots w_5$) before expanding to BEAM and AMA-Bench.

---

## 9. Primary References & Weblinks Directory

This directory centralizes all official datasets, research papers, repositories, and leaderboards for the engineering team:

### 9.1 Benchmark Suites & Datasets
- **LoCoMo Benchmark:**
  - Project Portal: [https://snap-research.github.io/locomo/](https://snap-research.github.io/locomo/)
  - MemoryPapers Index: [https://memorypapers.org/benchmarks/locomo](https://memorypapers.org/benchmarks/locomo)
  - ArXiv Paper: [arXiv:2402.17753](https://arxiv.org/abs/2402.17753) — *Evaluating Very Long-Term Conversational Memory of LLM Agents*
- **LongMemEval Benchmark:**
  - Specification & Documentation: [https://reme.agentscope.io/en/benchmarks/longmemeval](https://reme.agentscope.io/en/benchmarks/longmemeval)
  - AgentScope ReMe Repository: [https://github.com/agentscope-ai/ReMe](https://github.com/agentscope-ai/ReMe)
  - ArXiv Paper: [arXiv:2410.10813](https://arxiv.org/abs/2410.10813) — *LongMemEval: Benchmarking Chat Assistants on Long-Term Memory*
- **BEAM (Agent Memory Benchmark / AMB):**
  - Official Platform & Leaderboard: [https://agentmemorybenchmark.ai/](https://agentmemorybenchmark.ai/)
  - Official Harness Repository: [https://github.com/vectorize-io/agent-memory-benchmark](https://github.com/vectorize-io/agent-memory-benchmark)
  - Research Codebase: [https://github.com/mohammadtavakoli78/BEAM](https://github.com/mohammadtavakoli78/BEAM)
- **MemoryAgentBench:**
  - Official GitHub Repository: [https://github.com/HUST-AI-HYZ/MemoryAgentBench](https://github.com/HUST-AI-HYZ/MemoryAgentBench)
  - ArXiv Paper: [arXiv:2507.05257](https://arxiv.org/abs/2507.05257) — *MemoryAgentBench: Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions* (ICLR 2026)
  - Follow-up Work (MemoryArena): [https://memoryarena.github.io/](https://memoryarena.github.io/)
- **AMA-Bench:**
  - Official GitHub Repository: [https://github.com/AMA-Bench/AMA-Bench](https://github.com/AMA-Bench/AMA-Bench) (Hub: [https://github.com/AMA-Bench/AMA-Hub](https://github.com/AMA-Bench/AMA-Hub))
  - Project Homepage: [https://ama-bench.github.io/](https://ama-bench.github.io/)
  - Hugging Face Dataset: [https://huggingface.co/datasets/AMA-bench/AMA-bench](https://huggingface.co/datasets/AMA-bench/AMA-bench)
  - Hugging Face Leaderboard: [https://huggingface.co/spaces/AMA-bench/AMA-bench-Leaderboard](https://huggingface.co/spaces/AMA-bench/AMA-bench-Leaderboard)
  - ArXiv Paper: [arXiv:2602.22769](https://arxiv.org/abs/2602.22769) — *AMA-Bench: Evaluating Long-Horizon Memory for Agentic Applications* (ICML 2026)

### 9.2 Competitor Projects & Codebases
- **Hindsight (Vectorize):**
  - Official Repository: [https://github.com/vectorize-io/hindsight](https://github.com/vectorize-io/hindsight)
  - Documentation: [https://hindsight.vectorize.io](https://hindsight.vectorize.io)
  - ArXiv Paper: [arXiv:2512.12818](https://arxiv.org/abs/2512.12818) — *Hindsight is 20/20: Building Agent Memory that Retains, Recalls, and Reflects*
  - Vectorize Engine: [https://vectorize.io](https://vectorize.io)
- **Mem0:**
  - Official Repository: [https://github.com/mem0ai/mem0](https://github.com/mem0ai/mem0)
  - Platform & Documentation: [https://mem0.ai](https://mem0.ai)
  - Evaluation Harness: [https://github.com/mem0ai/memory-benchmarks](https://github.com/mem0ai/memory-benchmarks)
  - Memory Papers Curated Library: [https://memorypapers.org/](https://memorypapers.org/)
- **Supermemory:**
  - Platform & Documentation: [https://supermemory.ai](https://supermemory.ai)
  - Official Repository: [https://github.com/supermemoryai/supermemory](https://github.com/supermemoryai/supermemory)
  - MemoryBench Repository: [https://github.com/supermemoryai/memorybench](https://github.com/supermemoryai/memorybench)
- **Honcho (Plastic Labs):**
  - Platform & Documentation: [https://honcho.dev](https://honcho.dev)
  - Plastic Labs Research: [https://plasticlabs.ai](https://plasticlabs.ai)
  - Evaluation Harness: [https://github.com/plastic-labs/honcho-benchmarks](https://github.com/plastic-labs/honcho-benchmarks)
- **Mnemosyne:**
  - Local-first graph-memory engine running on SQLite in this workspace ecosystem (`mnemosyne` MCP server / Hermes agent).

### 9.3 Relevant Research on Memory Architecture
- **A-MAC (Adaptive Memory Admission Control):** [arXiv:2603.04549](https://arxiv.org/abs/2603.04549) — Foundational five-factor memory admission policy.
- **AdaMem (Adaptive User-Centric Memory):** [arXiv:2603.16496](https://arxiv.org/abs/2603.16496) — Multi-agent working, episodic, and persona memory coordination.
- **All-Mem (Agentic Lifelong Memory via Topology Evolution):** [arXiv:2603.19595](https://arxiv.org/abs/2603.19595) — Dynamic memory topology and offline consolidation.

---

## 10. Phase 100480 Go/No-Go and Locked Build Estimate

### 10.1 Decision: **GO**

Evidence:
- Both first-suite datasets are pinned and byte-verified (§3.6): LoCoMo at a pinned commit with a verified git blob hash; LongMemEval with a verified sha256 for the oracle split and API-resolved hashes for S/M.
- Licenses are compatible with the intended use: LoCoMo CC BY-NC 4.0 and LongMemEval MIT. LoCoMo's CC BY-NC 4.0 restricts redistribution and commercial use; the intended use is internal evaluation with no redistribution and no commercial use, which is compatible but still requires the human approver confirmation recorded in the phase sign-off. LongMemEval's MIT terms permit redistribution with attribution. No restricted licensing arrangement (for example redistribution of the data) is entered into.
- The judge calibrates within budget: Tier-1 local judge measured at $0.00 with 60/60 discrimination agreement and 0/60 consistency mismatches on a 30-item sample (§5.3.1).
- No mandatory stop condition triggered: no dataset is unreachable or license-blocked, a judge was calibrated within budget, and the estimate below is bounded.

No-go triggers for Phase 100480 (record here, do not silently proceed): a pinned snapshot stops resolving byte-for-byte, a license change forbids the intended use, or the Tier-1 judge agreement drops below 80% on the expanded calibration set without an in-budget replacement.

### 10.2 Locked Build Estimate

**Estimate: 60 hours core (range 48–66 hours), ≈ 7–8 working days.** This supersedes the §6.1 full-plan hours for the Phase 100480 subset (steps 1, 2, 3, 4, 6 = 54 h) plus a 6 h integration margin for stub docs, docs, and reproducibility checks.

Scope covered by the estimate: harness scaffolding + shared types (8 h), judge engine with swap-position scoring and the two-tier client (10 h), Clio adapter via the product's public surface (12 h), LoCoMo pipeline + baseline runner (10 h), LongMemEval-oracle integration + competency probes (14 h), partitioning + stubs + docs (6 h). Rival adapters (§6.1 steps 5, 8, 10, 11) and CI wiring (step 12) are excluded.

Assumptions:
1. **Judge cost:** Tier 1 is local at $0.00. Tier 2 (`gpt-4o-2024-08-06`) costs ≈ $2.50/1M input + $10/1M output; a full official sweep (~2,500 probes × ~2 calls × ~700 tokens) ≈ 3.5M input + 0.5M output ≈ **under $15** per sweep, inside the §5.5 hard caps ($15/trial, $50/CI run) when sweep frequency is respected.
2. **Throughput:** Tier-1 scoring is batched across llama.cpp parallel slots (~2–3 s per verdict wall time on the 4-core host); a full LongMemEval-oracle sweep (500 questions) completes in under ~4 h.
3. **Datasets:** pins per §3.6; one-time full downloads of the S (277 MB) and M (2.7 GB) splits need ~3 GB disk; only the oracle split is the first-build adapter target, S is stretch, M is out of scope.
4. **Credentials:** hosted Tier-2 judge credentials are provisionable via the standard secret mechanism. If they are not, Tier 2 falls back to the local judge and official scores are flagged as provisional; this fallback is a scope decision that requires operator sign-off, not a silent substitution.
5. **No product changes:** retrieval, extraction, and admission behavior are untouched; §5.4 partitions are implemented in the harness only.

