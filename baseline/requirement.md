# Clio — Requirements Document

**Document status:** Planning · **Version:** 1.11 · **Owner:** Memory Platform
**Applies to:** any long-horizon agent or companion chat product that must persist information across sessions

**Revision note:** v1.10 adds the native source `context` field and generalizes `evidence_ref` as the stable external source-identity field. Context is descriptive metadata; it is separate from category, epistemic truth, source text, and retrieval composition. Document-container (`doc_id`) semantics are explicitly deferred to a later phase (see §9). v1.11 adds the §9 retrieval temporal-anchor determinism risk: relative-date retrieval MUST use an explicit caller-supplied anchor and MUST NOT use an implicit server clock. The v1.10 context/evidence contract is unchanged.

---

## 0. Purpose, Scope, and How to Read This Document

This document defines the requirements for a memory system shared by (a) long-horizon autonomous agents and (b) companion/assistant chatbots. It is organized deliberately **problem-first**: Section 1 enumerates every failure mode that motivates the system, with evidence. Section 2 states the principles governing how the fixes for different problems interact with each other, since a fix for one problem can undermine the fix for another if applied without coordination. Section 3 collects the resulting non-negotiable design principles. Sections 4 onward specify the architecture, data model, APIs, algorithms, and acceptance criteria that a review board can hold an implementation to.

**Normative language:** MUST / MUST NOT / SHALL / SHALL NOT indicate mandatory requirements. SHOULD indicates a strong default that requires a documented, reviewed exception to deviate from. MAY indicates a permitted option.

**Non-goals:** This document does not specify a particular LLM provider, implementation language, or hosting environment. It specifies behavior and interfaces, not vendor choice — except for the storage backends named under **Supported storage backends** below. Tool names and semantics in §4.9 are normative; bindings (MCP, native FFI, HTTP, in-process) and language choice are implementation concerns.

**Supported storage backends:** Both **PostgreSQL with `pgvector`** and **SQLite** are supported. An implementation SHALL offer each as a selectable backend for persistence of memory items, graph/structure metadata, and the dense-vector index used by §4.5. Backend choice is deployment configuration only; it MUST NOT fork or weaken any behavioral requirement in this document. Other relational or vector engines are out of scope unless added by a later revision.

---

## 1. Problem Catalog

Each problem is stated with its mechanism (why it happens), its observable impact, and the stakeholder who feels it. Problems are numbered `P1`–`P13` and referenced by ID throughout the rest of the document so every later requirement can be traced back to the problem it addresses.

### P1 — Memory Bloat
Persisting entire conversation histories, or admitting every extracted fact without discrimination, causes long-term storage and — critically — the *context injected per turn* to grow without bound. Old reasoning traces, superseded plans, and one-off details compete for the same limited context budget as information that is actually relevant right now, and stale content can actively bias generation toward outdated assumptions. This is a governance failure (what is allowed in), not merely a storage-capacity failure.
*Affects: agents, companions, cost/latency budgets.*

### P2 — Slow Write Path
Architectures that run extraction → conflict-resolution → summarization → index-maintenance as one sequential pipeline cannot make new information queryable quickly. Under continuous agent operation (streaming tool calls, long-running tasks), this creates a backlog: the agent acts on stale memory because the fresh memory is still "in the write queue." Sequential dependency between *constructing* new memory and *maintaining* the overall structure (re-summarizing ancestors, rebalancing indices) is the dominant cost, not the LLM extraction call itself.
*Affects: agents operating continuously; real-time companion chat.*

### P3 — Garbage In, Garbage Out (Lossy Summarization)
Summarization is a lossy transform. Exact numbers, proper nouns, dates, and IDs are exactly the tokens a generic summarizer is most likely to paraphrase away or hallucinate a plausible-looking substitute for, because they carry the least redundancy and the model has the weakest prior over them.
*Affects: any downstream decision that depends on an exact figure, name, or date recalled from memory.*

### P4 — Inflated Token Count / Latency on Self-Contained Queries
Running full memory retrieval (embedding search + reranking + graph traversal) on every single turn — including "hi," "thanks," or a question fully answerable from the current turn alone — inflates both token cost and latency for the majority of turns that never needed old memory at all.
*Affects: cost, p50/p95 latency, user-perceived responsiveness.*

### P5 — No Cross-Session User Model (Companion Persona)
Companion chatbots that hold no durable model of the user force the user to re-state preferences, facts about themselves, and ongoing context every session. This is the single most-cited complaint about session-scoped assistants.
*Affects: companion/assistant products specifically; retention and trust.*

### P6 — Unbounded History Replay
Long-horizon agents that need "what happened before" have no way to get *only the relevant slice* of episodic, task, failure, or temporal history — the naive alternative is replaying the entire interaction log, which reintroduces P1 and P4.
*Affects: agents executing multi-day or multi-session tasks.*

### P7 — Repeated Mistakes Across Trials
Standard agents carry no memory of *why* a previous attempt failed. Weight-based RL fine-tuning after every failure is prohibitively expensive and too slow to apply between trials of the same task.
*Affects: agentic task execution, especially tool-use and coding agents.*

### P8 — Rigid, Rule-Based Memory Logic
Hard-coded rules for "when to store/retrieve/forget" cannot anticipate every situation and degrade to hit-or-miss behavior outside the cases their author enumerated. Rigidity here means the *mechanism* of memory operations is closed to the agent, not that governance boundaries don't exist (see P1, and §2.3).
*Affects: agent developers extending the system to new domains; edge-case reliability.*

### P9 — Preference Drift ("Memory Gets Outdated")
A user's stated preference today may be a temporary mood, not a durable trait. A system that treats every new statement as fully overwriting the old one is whipsawed by noise; a system that never updates is unable to track real drift.
*Affects: companion personalization quality.*

### P10 — Conflicting Facts Without Validity History
When a fact changes over time ("I moved to Boston," superseding "I live in Chicago"), naive systems either destructively overwrite the old fact (losing the ability to answer "where did I use to live?" or to explain a decision made under the old fact) or accumulate both assertions with no way to tell which is current — producing contradictions at retrieval time.
*Affects: correctness of any answer that depends on "what is true now" vs. "what was true then."*

### P11 — Beliefs Evolve With Accumulating, Sometimes Contradictory Evidence
Distinct from P10 (a fact about the world changing), this is about the agent's own *confidence in an inferred proposition* changing as more, possibly conflicting, evidence arrives — e.g., "the user is probably vegetarian" strengthening or weakening over several sessions. This requires tracking a confidence trajectory over time, not just a fact's current value.
*Affects: agents/companions that infer rather than are told; reasoning quality.*

### P12 — No Transparency Into What Is Remembered
Developers, and in many jurisdictions users themselves, have no visibility into what the system has stored, how confident it is, why an item was retrieved, or how a belief changed over time. This is a debuggability problem and, separately, a compliance problem (data subject access requests, right to correction/erasure).
*Affects: developers debugging bad behavior; legal/compliance; end-user trust.*

### P13 — Facts vs. Opinions Are Conflated
Systems that store "the user said X" and "X is true" in the same representation cannot later tell a subjective, possibly wrong, self-report apart from a verified objective fact — leading to false confidence when acting on opinions and to unnecessary distrust of verified facts.
*Affects: correctness of downstream reasoning; see §4.11 for the classification scheme.*

---

## 2. Design Tensions and Governing Principles

Several of the mechanisms implied by §1 interact with each other, and a fix for one problem can undermine the fix for another if the interaction is left implicit. This section states each interaction explicitly and the principle that governs it; §3 collects the principles.

### 2.1 Bloat Avoidance (P1) vs. Full History Access (P6)
*Tension:* "Store less" and "agents need access to episodic/task/failure/temporal history" look contradictory if storage and context-injection are treated as the same operation.
**Governing principle → PR-1 (§3):** Storage volume and context-injection volume are decoupled. The system MAY retain large amounts of cold, indexed episodic history; it MUST NOT inject more than a bounded token budget of it into any single context. Bloat is a context-budget problem, solved at retrieval time (§4.5), not a storage-volume problem, solved at write time.

### 2.2 Non-Destructive Fact History (P10) vs. Smoothing Outdated Preferences (P9)
*Tension:* Non-destructive fact history and preference smoothing look like two competing fixes for the same underlying problem — memory going stale — if applied to the same kind of attribute.
**Governing principle → PR-2 (§3):** These address different attribute types. P10 concerns **discrete, categorical facts** ("lives in Boston"), where the correct model is bi-temporal invalidation: the old value is superseded, never blended, and remains queryable as history. P9 concerns **continuous or scalar signals** (affinity score for a topic, sentiment intensity, engagement level), where blending via an exponential moving average (EMA) is the correct model of drift. The admission/update pipeline MUST classify every attribute as one or the other at schema-definition time (§4.6); an attribute is handled by exactly one of the two mechanisms.

### 2.3 Whitelisted Semantic Categories vs. Adaptive Agent-Controlled Memory Tools
*Tension:* A fixed whitelist of admissible semantic categories is, by definition, a rigid rule. But P8 identifies rigid rules as a source of failure.
**Governing principle → PR-3 (§3):** Rigidity and flexibility apply to different layers. The **taxonomy of what content types are eligible for long-term semantic admission** is a governance boundary and MUST remain closed and explicit (§4.1) — this is what prevents P1. The **mechanism by which an agent decides to invoke tools within that boundary** is exposed as the open catalog in §4.9 and MUST be agent-directed — this is what prevents P8. Closed taxonomy plus open tool-use is a two-layer design, and both layers MUST be present.

### 2.4 Five-Factor Admission Scoring vs. Whitelisted Categories
*Tension:* If a category is already whitelisted, why also score it?
**Governing principle:** Category membership is a **necessary but not sufficient** gate. Whitelisting answers "is this the *kind* of thing we ever store"; admission scoring (§4.2) answers "is *this specific instance* worth storing given confidence, novelty, recency, and utility." Both gates MUST pass before write.

### 2.5 Lossless Fidelity vs. Compact Summaries
*Tension:* Preserving exact entities/numbers and producing compact conversation summaries pull in opposite directions — compression is inherently lossy.
**Governing principle → PR-4 (§3):** The system MUST maintain two separate representations per operational memory unit, not one representation asked to do both jobs: a lossless **structured atomic-fact snapshot** (exact values, schema-typed) and a lossy **prose gist** (for narrative continuity only). Any downstream consumer that needs an exact value MUST read the snapshot; the gist is explicitly documented as non-authoritative and MUST NOT be the sole source for a numeric or identity-bearing claim.

### 2.6 Online Verification Is Not Training
Online extraction MUST NOT run a training loop or a multi-sample sampling loop at write time — treating extraction as a per-request sampling step would reintroduce the slow-write-path problem (P2) by adding an expensive sampling loop to every write. Offline training and packaging of the extractor model (including any fine-tuning) is out of scope for this codebase: training and packaging an extractor model is not this codebase's job. The only correctness mechanism at write time is the cheap runtime verification pass in §4.4, which checks each admitted snapshot against a locatable source span.

### 2.7 Intent Gate Skipping Retrieval vs. Persona Always Available
*Tension:* If the intent gate skips memory lookups for turns that "don't need it," does a companion ever get to use the persona it built?
**Governing principle:** The intent gate (§4.5) gates **search over episodic/semantic stores**. Persona/stable-preference injection (§4.7) is a separate, always-on, fixed-budget channel that is never subject to the intent gate — it is cheap by construction (small, bounded object), not cheap by being skipped.

### 2.8 Verbal Reinforcement Learning vs. Bounded Memory
*Tension:* Reflexion-style free-text self-reflections, appended every failed trial, are themselves a form of monotonically growing memory if left unbounded.
**Governing principle:** Failure memories (§4.8) are stored as structured `FailureRecord` objects with a length-capped natural-language `lesson` field, subject to the same admission scoring and consolidation path as any other episodic memory — not as an ever-growing free-text log exempt from governance.

### 2.9 Source Context vs. Context Budget vs. Provenance
*Tension:* A memory benefits from knowing the setting in which it was captured, but the system also needs a bounded model-facing context budget and a stable way to identify its source. Treating one free-form `context` value as all three would blur descriptive metadata, retrieval composition, and provenance.
**Governing principle → PR-10 (§3):** Source `context` is optional, bounded, descriptive metadata attached to a memory. It MUST NOT determine category or epistemic truth, MUST NOT replace `source_text` for span verification, and MUST NOT be injected without the PR-1 budget. `evidence_ref` is the provider-neutral stable source identity and MAY identify an external memory item, conversation turn, tool call, or other source record. Document-container semantics are a separate deferred concern (see §9).

---

## 3. Design Principles (Non-Negotiable)

| ID | Principle |
|----|-----------|
| PR-1 | **Storage ≠ context budget.** Retention volume and per-request injection volume are governed independently. |
| PR-2 | **Discrete facts are superseded; continuous signals are smoothed.** No attribute is handled by both models. |
| PR-3 | **Closed taxonomy, open tool-use.** What may be stored is a fixed governance boundary; how an agent operates within it is agent-directed via the §4.9 tool catalog. |
| PR-4 | **Snapshot for truth, gist for flow.** Every operational memory has a lossless structured half and a lossy narrative half; only the former is authoritative for exact values. |
| PR-5 | **Nothing is admitted without a decision.** Every candidate memory passes an explicit, logged admission decision (category gate + five-factor score); there is no implicit/default admission. |
| PR-6 | **Supersession is invalidation, not erasure.** When a discrete fact is superseded, the prior edge is invalidated and retained for history — never silently overwritten or erased by the supersession path. Routine removal from active use (`discard`, co-activation pruning, hygiene) is a separate, logged operations path (§4.9, §7.4). Compliance-grade destruction of personal content is only via crypto-shredding (§7.4). |
| PR-7 | **Retrieval is need-based, not turn-based.** Whether memory is searched at all, and which subset is searched, is decided per turn, not fixed. |
| PR-8 | **Every memory operation is attributable.** Provenance (source turn/session/tool call), confidence, and epistemic kind (fact vs. belief, with source provenance for beliefs) are mandatory fields, not optional metadata. Attribution is satisfied by system-recorded provenance (actor, bank, timestamps, item identity) on every operation; caller-supplied `evidence_ref` is optional on `store` but MUST be preserved when supplied, and provider-import paths MUST supply it. |
| PR-9 | **Write and structural maintenance are decoupled processes.** New memory becomes queryable before any background re-indexing/re-summarization completes. |
| PR-10 | **Context describes; evidence identifies.** Source context is bounded descriptive metadata, while `evidence_ref` identifies the source. Neither changes the closed category taxonomy, the fact/belief classification, or the authority of a verified snapshot. |

---

## 4. Solution Architecture

### 4.1 Memory Taxonomy

Two top-level stores, matching the standard semantic/episodic split used across current agent-memory literature (Mem0, Zep/Graphiti, MemGPT-style architectures):

**Semantic (contextual) memory** — reusable, largely time-invariant. Admission is restricted (PR-3) to exactly these categories; any candidate not matching one is rejected at the category gate regardless of score:
- Task specifications
- Data schemas
- Tool configurations
- Output constraints
- Persona (user-model — see §4.7 for its stricter sub-schema)

**Episodic (operational) memory** — time-indexed, about specific events:
- Semantic triples (subject–predicate–object, with validity interval — §4.6)
- Compact conversation summaries (gist only, non-authoritative — §2.5)
- Task/failure/temporal history records (§4.8)

The adjective **contextual** in “semantic (contextual) memory” describes reusable memory; it does not define a new category or a field. The optional per-item `context` field is defined in §4.4, §4.9, and §7 as bounded source metadata. It MUST NOT be used to add a sixth category.

Adding a sixth semantic category or a new episodic record type MUST go through a schema-change review; it MUST NOT be done ad hoc by widening a scoring threshold.

### 4.2 Admission Control (Second Gate)

Every candidate that passes the category gate (§4.1) is scored on five factors before write:

| Factor | Question it answers | Example signal |
|---|---|---|
| Future utility | Will this plausibly matter beyond this turn? | Referenced again later, tagged as a preference/decision/constraint |
| Factual confidence | How sure are we this is true/accurate? | Direct first-person statement > inferred > speculative |
| Semantic novelty | Does this add information not already stored? | Embedding distance to nearest existing item |
| Temporal recency | How fresh is this relative to what it might supersede? | Timestamp delta |
| Content-type prior | Does this content type historically prove useful once stored? | Empirical base rate per category |

`admission_score = w1·utility + w2·confidence + w3·novelty + w4·recency + w5·type_prior`, weights tunable per deployment, threshold `θ_admit` configurable per category. Items scoring below `θ_admit` are discarded (not silently — logged per PR-5/PR-8). This scoring layer is orthogonal to, and runs after, the category whitelist (§2.4).

`context` MAY be supplied to extraction or retrieval as a descriptive signal, but it MUST NOT make an otherwise ineligible category eligible, change `epistemic_kind`, or replace `source_type`/`source_ref`. A deployment MAY define an additional deterministic context-aware scoring signal only when that policy is documented; this revision does not make context an admission factor by default.

### 4.3 Write Path

The write path MUST satisfy PR-9: construction and structural maintenance are separate, non-blocking processes.

1. **Parallel chunk extraction.** New conversation/tool-call turns are extracted concurrently rather than as one sequential stream — matching the parallel-chunk-extraction approach used to break the sequential bottleneck in current write-optimized agent-memory designs.
2. **Canonical fact consolidation.** Because parallel extraction can fragment the same underlying fact into near-duplicate candidates, a consolidation step merges them into a stable canonical unit before indexing — this repairs the fragmentation that parallelization otherwise introduces.
3. **MemTree: a hierarchical temporal index.** Memory is organized as time-ordered trees, not a flat, globally-rewritten summary. Leaves hold granular episodic units; internal nodes hold aggregated, higher-level summaries; the root is the most abstract view. This mirrors the MemTree/MemForest design pattern, which organizes memory as time-ordered trees specifically to avoid rewriting a flat global summary on every update.
4. **Dirty-path refresh.** When a leaf changes, only the chain of ancestor nodes on the path from that leaf to the root is marked dirty and recomputed — analogous to write-optimized index structures (e.g., LSM-tree-style incremental maintenance) that avoid rewriting the whole structure on every insert.
5. **Parallel summary refresh.** Dirty ancestor nodes at the same tree depth, across different branches, are recomputed concurrently rather than one at a time.

When a write includes source `context`, the context MUST travel with the candidate through extraction, verification, admission, storage, and read projections. It is descriptive input only: it MUST NOT be concatenated into the structured snapshot as an authoritative field, and it MUST NOT be used as the source-span haystack. The authoritative evidence text remains `source_text`.

A new item MUST become queryable (via the leaf level) immediately after step 2, before steps 3–5 (structural maintenance) complete. This is the concrete mechanism that satisfies P2.

### 4.4 Fidelity Preservation

Fidelity at write time comes from a single online mechanism:

- **Online (write time):** every extraction output is a schema-typed "event snapshot" with **atomic constraints** — every entity, date, and number in the snapshot MUST be grounded in a **locatable source span** from the source turn, not a re-generated paraphrase with no substring evidence. A cheap verifier (not a second full LLM sampling loop) checks this before commit:
  - **Entities / identity strings:** the snapshot value MUST appear as a contiguous source substring (after documented minimal normalization such as Unicode NFC).
  - **Numbers and dates:** the verifier MUST locate a source substring that **parses** to the same numeric or calendar value under documented format rules (e.g. `1,000` vs `1000`, ISO vs locale dates). Matching a normalized value alone, with no locatable span, is a verification failure. Ambiguous dates without a configured day-first (or equivalent) policy MUST fail closed.
  On failure, the single extraction is retried once. If still unverified, the structured snapshot MUST NOT be committed. The rejection is logged (PR-5/PR-8). The system MAY retain a non-authoritative gist and/or a diagnostic candidate for offline review, but MUST NOT treat unverified spans as an admitted snapshot. This is what prevents P3 without reintroducing P2's latency problem.

Offline training and packaging of the extractor model is out of scope. If artifact training ever happens, it lives out-of-tree as a maintainer-side recipe, never as a user-facing step or an in-repo pipeline.

This two-representation design (structured snapshot + separate prose gist) is the direct implementation of PR-4.

**Source context (normative).** `context` is an optional, bounded, descriptive string that records the setting or circumstances surrounding a memory item, such as a conversation type, document setting, or workflow stage. It MUST be validated as UTF-8, MUST have a published maximum size, and MUST be rejected when empty or oversized rather than silently truncated. A reference maximum of 4 KiB UTF-8 bytes is the default target; deployments MAY lower it but MUST NOT raise it without a reviewed requirement revision. `context` MUST NOT be interpreted as a category, an epistemic kind, a source type, a confidence value, a source span, a model instruction, or a retrieval budget. It MAY be returned as metadata and MAY be used as a documented retrieval signal, but it MUST NOT change the authority of a structured snapshot or bypass §4.4 span verification. Ordinary updates MUST preserve the existing context; replacing it requires an explicit audited correction, and the prior value MUST remain reconstructable via `audit_trail` (prior context is reconstruction history, not queryable point-in-time state).

`evidence_ref` is the provider-neutral stable provenance reference for the source. It MAY identify a source turn, tool call, external memory item, or other source record, and at the item level it populates `source_ref` subject to the precedence rule in the glossary. It is not the `source_text` haystack and MUST NOT be used as an authorization token. It is not a document container: carrying an external document's identifier opaquely preserves identity only and confers no upsert, bulk-delete, or original-text semantics (see §9).

### 4.5 Retrieval Path

```
Intent Gate → Allowed memory domains → Adaptive retrieval → Relevant memories
```

1. **Intent Gate.** A lightweight classifier decides, per turn, whether the message plausibly requires old memory at all. Self-contained turns ("hi," "thanks," turns fully resolved by the current context) skip retrieval entirely. This directly targets P4 and is consistent with adaptive retrieval-necessity gating approaches used in current retrieval-augmented systems (retrieve only when the model's own signal indicates a knowledge gap, rather than on every turn).
2. **Allowed memory domains.** If retrieval is needed, the gate additionally scopes *which* domains (e.g., task history vs. persona vs. failure log) are plausibly relevant, so search hits only the relevant partitions rather than the entire store.
3. **Adaptive retrieval.** Within the allowed domains, retrieval combines embedding similarity, lexical/BM25 match, and — where a graph structure exists (§4.6) — bounded graph traversal, with reranking. This hybrid combination (dense + lexical + graph, then rerank) matches the retrieval design used in current temporal-knowledge-graph memory systems, which report it outperforming embedding-only search on both accuracy and the temporal-reasoning cases embedding search structurally cannot answer (which fact was true when).

   Retrieval hits MUST expose optional source `context` as metadata so a consumer can understand the setting of a result. A deployment MAY use the bounded context value as an additional lexical signal, but it MUST remain non-authoritative and MUST NOT change the item's category, `epistemic_kind`, or confidence. `compose_context` MUST count any context it includes against its existing token budget and MUST NOT inject context automatically merely because it was stored. The default composition policy MAY omit context; any policy that includes it MUST be explicit, bounded, and auditable.

4. **Co-activation reinforcement and decay.** Memories retrieved together for the same query have the association weight of their link increased (a Hebbian-style "fire together, wire together" update); future queries can then spread activation across strongly linked memories, surfacing related memories that pure similarity search would miss.

   **Association vs triple (normative data model).** Weighted links live as **`assoc_edge`** records in **graph/structure metadata** (the same persistence concern named under Supported storage backends and used by §4.6)—**not** a new memory *domain*, injection tier, or sixth semantic category. An `assoc_edge` links two **memory item ids** and carries `assoc_kind` ∈ {`coactivation`, `explicit`}. It is **not** a bi-temporal SPO triple: triples assert facts with `subject`+`predicate` identity and valid/transaction intervals (§4.6); association edges do not supersede facts and MUST NOT reuse the triple identity key or interval algebra. "Not a new storage tier" means associations MUST NOT bypass PR-1 injection budgets or invent an ungated memory class; dedicated tables/indexes for `assoc_edge` inside graph metadata are permitted and expected. Erase (§7.4) and sync (§4.9.5.D) MUST treat `assoc_edge` rows as graph metadata derived from / referencing item ids: drop or regenerate edges whose endpoints were erased; include association mutations in incremental sync when multi-host is claimed.

   Left unmanaged, growth-only edge weights accumulate without bound, so the **`association_weight_policy`** (name deliberately distinct from attribute **`update_rule`** ∈ {`discrete`,`continuous`} in FR-11) has four parts for **`assoc_kind=coactivation`** edges:

   - **Growth (on co-activation):** when items *i* and *j* both appear in the same retrieval result set, `w_ij ← w_ij + η · (1 − w_ij)`, with learning rate `η` (default 0.15) and `w_ij ∈ [0, 1]`. The `(1 − w_ij)` term makes growth saturating: an already-strong edge gains little from one more co-activation, so no edge can exceed 1 and no edge can dominate indefinitely from repeated hits alone. This saturating step is **not** the continuous EMA formula (`α` / Phase continuous engine).
   - **Passive decay (evaluated lazily at read time, not a scheduled sweep):** `w_ij_eff(t) = w_ij · exp(−λ · Δt)`, where `Δt` is elapsed time since the edge's last update and `λ = ln(2) / half_life` for a configured `half_life` (default 30 days). Because this is computed on read, decay cost scales with retrieval volume, not with total graph size.
   - **Pruning:** if `w_ij_eff` falls below `w_min` (default 0.05) when evaluated, the edge is deleted and the deletion is logged (PR-8). This bounds total edge count — an edge that stops being co-activated decays out and is eventually removed rather than persisting at a stale weight forever.
   - **Hub consolidation ("hub distillation"; research alias "Hebbian distillation"):** independent of individual edge decay, a node whose count of above-threshold edges exceeds a configured limit is flagged for consolidation — the same consolidation mechanism used in the write path (§4.3, step 2) is reused here to distill the hub and its strongly-connected neighbors into a single structured semantic item (subject to the §4.1 category gate, like any other admission). The original fine-grained edges MAY be pruned once the distilled item is written and cross-referenced.

   **Explicit edges (`assoc_kind=explicit`, via `graph_link`).** Identity key is **`bank` + ordered item-id pair + `relationship`** (multiple relationships between the same pair MUST be allowed). Explicit edges are **sticky by default**: they MUST NOT apply the co-activation lazy-decay/prune schedule unless a deployment documents a longer explicit half-life. They still participate in `associations` / `graph_query` / optional `expand_graph`.

   Together, saturating growth bounds any single co-activation edge, decay bounds staleness, and pruning plus hub distillation bound total co-activation graph size.

The Intent Gate governs search over episodic/semantic stores only; it MUST NOT gate the always-on persona channel (§2.7, §4.7).

### 4.6 Temporal & Fact-Revision Model

Applies to **discrete/categorical** attributes only (PR-2). Every semantic-triple edge carries a bi-temporal pair:
- `valid_time`: the interval during which the fact was true in the world.
- `transaction_time`: the interval during which the system believed/recorded it.

**Interval convention:** both axes use half-open intervals `[start, end)` with `end = null` meaning open-ended. A point-in-time `as_of` on an axis includes an edge iff `start ≤ as_of` and (`end` is null or `as_of < end`).

**Supersession identity (normative):** the open-edge identity key for default supersession is **`subject` + `predicate`** (aligned with §4.9.4.E `triple_add`). The **object** is not part of the identity key; it is what changes under contradiction. When a new discrete fact for the same `subject`+`predicate` contradicts an existing **open** edge (different object, or an explicit supersede/replace), the system invalidates the prior edge rather than deleting it: it MUST set both `valid_time.end` and `transaction_time.end` on the prior edge (at the supersession instant / new edge's valid start as documented for each axis), and the new edge becomes current. This is the bi-temporal invalidation model used in current temporally-aware agent-memory graph engines: new information wins on the transactional timeline while "what was true then" and "what the system believed then" remain answerable via `as_of` + `time_axis` (FR-24, NFR-4). This satisfies PR-6.

**Operators (discrete path):**
- **Assert / supersede** (`triple_add` with default `supersede=true`): insert new edge; close prior open `subject`+`predicate` on both time axes.
- **Retract** (`triple_end`): close valid (and transaction) time on a matching open edge without inserting a replacement.
- **Correct** (late correction): insert or adjust so transaction-time history reflects that the system was wrong; prior versions remain queryable on `time_axis=transaction`. Do not DELETE rows.

For **continuous/scalar** attributes (affinity scores, sentiment intensity, engagement level), the update rule is instead:

```
new_state = α · observed_value + (1 − α) · previous_state      (EMA, fast-moving)
trend      = long-window average over N most recent states      (slower-moving baseline)
```

with `α` tunable per attribute to separate short-term fluctuation (EMA) from longer-term tendency (the trend average). An attribute schema MUST declare an **`update_rule`** of `discrete` or `continuous` at definition time; this declaration determines which of the two update rules above is legal for it, and the write path MUST reject an update that uses the wrong rule. This `update_rule` is **not** the item `epistemic_kind` field (`fact`|`belief` in §4.11 / FR-14)—the two enums MUST NOT share a storage column or API parameter.

### 4.7 User Persona / Companion Memory

A small, bounded object, injected on every turn regardless of the Intent Gate (§2.7), holding only what changes rarely or is a durable preference:

```json
{
  "stable": [
    { "key": "name", "value": "…", "confidence": 0.95, "source": "explicit", "context": "team chat", "as_of": "2026-08-01" },
    { "key": "communication_style", "value": "concise", "confidence": 0.8, "source": "inferred", "as_of": "2026-09-10" }
  ],
  "preferences": [
    { "key": "brevity_affinity", "value": 0.82, "confidence": 0.8, "source": "inferred", "as_of": "2026-09-10", "trend": 0.72 }
  ]
}
```
`stable` entries hold durable **discrete/categorical** attributes (including categorical preference labels such as communication style) and follow the bi-temporal invalidation model (§4.6). `preferences` entries hold **continuous/scalar** intensities only (affinity, sentiment strength, engagement level) and follow the EMA model, carrying a `trend` field — never a categorical string under EMA (PR-2). Categorical preference changes use `persona_put_stable` (or equivalent discrete update); scalar observations use `persona_observe_preference`. The companion object is the **`persona_document`** (always-on channel); it is related to but not identical with semantic **category** `persona` on generic `store`—implementations MUST document a non-overlapping boundary so category-`persona` items do not silently bypass the companion budget. The object MUST stay within a fixed token budget (configurable, default target ≤ 400 tokens). Each entry MUST carry a durable **`admission_score`** stamped at its last gated write (`persona_put_stable` MUST run §4.2 and store the score; `persona_observe_preference` MUST retain the create-time admission score or a documented synthetic score in `[0,1]`). When over budget, entries are ranked by that stored `admission_score` descending (tie-break by `key` ascending) and truncated, never silently grown without bound. Persona entries MAY carry optional source `context`; it is descriptive metadata and MUST NOT change the discrete/continuous update rule or the always-on budget.

### 4.8 History Subsystem

Four record types, each retrieved selectively rather than replayed in full (satisfying P6/§2.1):

| History type | What it holds | Retrieval pattern |
|---|---|---|
| Episodic | Discrete events with timestamp, participants, outcome | MemTree leaf lookup, time-scoped |
| Task | Task definition, steps taken, final status | Keyed by task ID; summarized ancestor node for "what have I tried" queries |
| Failure | `FailureRecord {task_id, attempt_n, what_failed, lesson (capped length), evidence_ref, context?}` | Retrieved when a new attempt at the same/similar task begins |
| Temporal | Snapshots of how a tracked fact/preference changed over time | Bi-temporal edge history (§4.6) or EMA trend series (§4.6) |

Failure records implement verbal reinforcement learning: rather than fine-tuning weights after each failed trial, a natural-language "lesson" is derived from the failure and used as bounded reflection context on the next attempt at that task — the mechanism demonstrated in the Reflexion framework, where verbal self-reflection on a failed trajectory is stored in episodic memory and conditions the next attempt without any gradient update. Per §2.8, these records are subject to the same admission scoring and category-bounded storage as any other episodic memory; they are not an unbounded exempt log.

### 4.9 Adaptive Memory Tooling

Per PR-3, agents interact with memory through an open tool interface rather than hard-coded rules. This section is the **normative tool catalog**.

**Derivation rule:** Every tool in §4.9.4 (**Core — derived**) MUST trace to a mechanism already specified in §§1–4.8, 4.10–4.12, or §7. Tools in §4.9.5 (**Additive — harness/ops**) improve coding-agent operability but are **not** required to realize those earlier sections; deployments MAY omit an additive tool only with a documented exception. Implementation language remains unspecified (§0).

#### 4.9.1 Feature → tool coverage (document-native)

| Document feature | Primary tools | Gap closed |
|---|---|---|
| P1 / PR-1 bounded injection | `compose_context` | Agent can see/request a budgeted pack without replaying history |
| P1 / ops anti-bloat | `hygiene_audit`, `hygiene_clean` | Ranked noise cleanup with secret masking + audit log (§4.9.5.A) |
| P2 / PR-9 / §4.3 write vs maintenance | `store`, `maintenance_status`, `consolidate` | Leaf write stays fast; agent can inspect dirty-path state and trigger maintenance |
| P3 / PR-4 / §4.4 snapshot vs gist | `get_snapshot`, `get_gist`, `summarize`, `store` | Exact values never depend on gist alone |
| P4 / PR-7 / §4.5 intent gate | `intent_gate`, `retrieve` | Gate is inspectable; explicit retrieve still runs when agent calls it (FR-24) |
| P5 / §4.7 persona | `persona_get`, `persona_put_stable`, `persona_observe_preference` | Discrete/categorical (incl. labels) vs scalar EMA intensities |
| P6 / §4.8 history slices | `task_*`, `failures_for_task`, `failure_record`, `memtree_query`, `temporal_history` | Selective history, not full-log replay |
| P7 / §4.8 / §2.8 FailureRecord | `failure_record`, `failures_for_task` | Structured lesson write + retrieve on retry |
| P8 / PR-3 open mechanism | full catalog | Agent chooses when; gates choose whether |
| P9 / PR-2 continuous EMA | `persona_observe_preference`, `update(..., update_rule=continuous)` | Smoothing, not overwrite |
| P10 / PR-6 / §4.6 bi-temporal | `triple_*`, `invalidate`, `retrieve`/`triple_query` with `as_of` + `time_axis` | Supersede without delete; query "true then" |
| P11 / §4.10 beliefs | `belief_observe`, `belief_history` | Append-only confidence trajectory |
| P12 / §4.12 / §7.4 transparency & erasure | `inspect`, `correct`, `audit_trail`, `export`, `erase_request` | Visibility, correction, compliance path |
| P13 / §4.11 fact vs belief | `store`/`belief_observe` + mandatory `epistemic_kind` on reads | Epistemic kind is a field, not optional metadata |
| PR-10 / FR-34–35 source context and evidence identity | `store`, `retrieve`, `inspect`, `export`, `import` | Context and stable external source references survive the memory lifecycle without becoming categories or truth claims |
| §4.1 taxonomy | `store` category enum | Only five semantic categories admit |
| §4.2 five-factor admission | `admit_preview`, `admit_preview_batch`, gated writes return score/rejection | Decision is explicit and inspectable before/after write |
| §4.3 MemTree | `memtree_query`, `memtree_get`, `consolidate` | Hierarchical temporal index is agent-reachable |
| §4.5 co-activation / graph | `retrieve(expand_graph)`, `associations`, `graph_link`, `graph_query` | Hebbian links inspectable; explicit edges for coding causality |
| §4.6 discrete vs continuous | `update` rule split; `invalidate` vs EMA tools | Wrong rule MUST fail (FR-11) |
| FR-9 task retry | `failures_for_task` | Mandatory retrieve path for repeated attempts |

#### 4.9.2 Delivery and binding (language-agnostic)

1. Every tool below MUST be published with a machine-readable parameter schema (JSON Schema or equivalent).
2. An implementation SHALL expose every **Core** tool (§4.9.4) through at least one harness-consumable binding. **MCP (stdio and Streamable HTTP)** SHOULD be the reference binding; legacy HTTP+SSE MAY be offered only when a harness still requires it. Native library / FFI / other HTTP MAY also be provided. Binding syntax MAY differ; names and semantics MUST NOT.
3. **MCP protocol revision pin.** When MCP is used, the implementation SHALL pin and document a single MCP specification revision for tools and transports together. **Clio first-release reference revision is `2025-11-25`** (stdio + Streamable HTTP as that revision defines, including optional `MCP-Session-Id` session management). Mixing transport rules from a later revision (e.g. `2026-07-28` sessionless Streamable HTTP) with `2025-11-25` session tests is FORBIDDEN. A migration to a newer revision MUST be an explicit, tested change. Published machine-readable tool definitions are **`tool_schema`** artifacts (MCP `inputSchema` / optional `outputSchema`) and MUST NOT be confused with semantic category `schema`.
4. Coding-agent deployments SHALL also expose every **Additive** tool in §4.9.5 unless a reviewed exception documents the omission.
5. Destructive tools (`discard`, `erase_request`, `hygiene_clean`) MUST require explicit confirmation when invoked from an agent harness, except authorized compliance workflows.
6. Optional parameters marked `?` MAY be omitted; defaults MUST be those stated here or in the published schema.
7. Schemas for long-term memory items MUST publish the optional `context` type, maximum size, and preservation semantics when supported. When omitted, context is absent rather than an empty string. `context` is item-level metadata, not a global operation parameter; where a tool accepts `context?` beside an item shell, it populates that item's context field. `evidence_ref` is the stable source-identity parameter. All bindings MUST expose identical semantics for both fields.

#### 4.9.3 Gating matrix

| Class of tool | Category gate (§4.1) | Admission score (§4.2) | Notes |
|---|---|---|---|
| Long-term writes (`store`, `triple_add`, `failure_record`, `task_upsert`, `persona_put_stable`, gated `batch` ops, additive `shared_store` / `canonical_put`) | MUST (where category applies) | MUST | Structured rejection required (PR-5). Episodic types use the episodic admission path, not a forged semantic category. Optional `context` is descriptive metadata and MUST NOT bypass either gate. |
| Belief writes (`belief_observe`) | N/A | MUST on **create**; **append** validates without full re-admission (see §4.10) | Beliefs are §4.10 objects—not a sixth semantic category and not an episodic type tag. Category gate does not apply. |
| Mutators (`update`, `invalidate`, `triple_end`, `persona_observe_preference`) | N/A | N/A | Enforce `update_rule` discrete vs continuous (FR-11); emit audit (FR-15). |
| Reads / inspect / compose / intent | N/A | N/A | Automatic intent gate MAY skip *background* retrieval; explicit tool calls MUST still run. |
| Scratchpad (additive) | N/A | N/A | MUST NOT enter long-term stores; size-bounded. |
| `consolidate` | N/A | Derived long-term writes re-enter gates | Aligns with §4.3 dirty-path / hub distillation. |

#### 4.9.4 Core tool catalog (derived from this document)

##### A. Admission, write, and fidelity (§4.1–4.4, PR-4, PR-5, PR-9)

| Tool | Effect | Traces to |
|---|---|---|
| `admit_preview(item, category)` | Run category + five-factor scoring; validate optional item `context` when present; return `{pass, admission_score, factors, rejection_reason?}` without writing. | §4.2, PR-5, PR-10 |
| `admit_preview_batch(items[], bank?, profile_override?)` | Batch dry-run of `admit_preview` over 1–50 candidates under the bank's resolved retention profile (or an unpersisted `profile_override`); each item's optional `context` is validated as in `admit_preview`; return per-item decisions in input order plus `{would_admit, would_reject, by_reason}`. Read-only: zero writes, zero store or index side effects. | §4.2, PR-5, PR-10 |
| `store(item, category, epistemic_kind, source_type?, confidence?, evidence_ref?, context?, source_text?, snapshot?, gist?)` | Admit a long-term item. `category` for semantic writes MUST be one of: `task_spec` \| `schema` \| `tool_config` \| `output_constraint` \| `persona`. Episodic writes use an episodic type tag (`triple` \| `gist` \| `task` \| `failure` \| `temporal`) rather than inventing a sixth semantic category. `context` is optional, bounded, descriptive source metadata; it is not a category, `source_type`, `epistemic_kind`, source span, or retrieval budget. When `snapshot` is present, `source_text` MUST be provided and FR-4 span verification MUST pass before taxonomy/admission scoring; context MUST NOT substitute for that evidence. `evidence_ref` is the stable provider-neutral source identity and populates item `source_ref` per the glossary precedence rule (it is never the span haystack). Returns `{id, admission_score}` or structured rejection. Leaf MUST be queryable before ancestor refresh completes (PR-9). | §4.1–4.4, PR-10, P1–P3 |
| `get(item_id)` | Exact fetch by id (metadata + refs, including optional `context` and `source_ref`). | §4.12, PR-10 |
| `get_snapshot(item_id)` | Return the authoritative structured snapshot only. | PR-4, FR-5 |
| `get_gist(item_id)` | Return the non-authoritative prose gist only. | PR-4 |
| `summarize(scope)` | Regenerate gist for a scope; MUST NOT alter snapshots. | PR-4, §4.3 |
| `update(item_id, new_value, update_rule)` | `update_rule` is `discrete` → invalidation path; `continuous` → EMA path. Wrong rule MUST fail. MUST NOT accept `fact`/`belief` here (those are the item `epistemic_kind` field, FR-14). | §4.6, PR-2, FR-11 |
| `invalidate(item_id, replacement_id?)` | Close validity; do not delete (PR-6). | §4.6, FR-12 |
| `discard(item_id, reason)` | Logged operations removal from active use (§7.4); not supersession and not compliance erasure. | §4.9, §7.4, PR-6 |
| `maintenance_status(item_id?)` | Report whether leaf is queryable and which MemTree ancestors are dirty / refreshing. | §4.3, PR-9, P2 |
| `consolidate(scope?, force?)` | Trigger dirty-path / parallel ancestor refresh and eligible hub distillation (§4.5); MUST NOT block new leaf writes. | §4.3, §4.5 |

##### B. Retrieval, intent, injection budget (§4.5, PR-1, PR-7)

| Tool | Effect | Traces to |
|---|---|---|
| `intent_gate(turn_text)` | Return `{retrieval_needed, domains[]}` for this turn. Diagnostic/override aid; does not by itself inject memory. | §4.5, P4, FR-6 |
| `retrieve(query, domains?, limit?, as_of?, time_axis?, expand_graph?, budget_tokens?, recall_scope?, prefer_consolidated?)` | Adaptive retrieval (dense + lexical + optional graph) over domains: `semantic` \| `episodic` \| `task` \| `failure` \| `temporal` \| `persona`. `time_axis` is `valid` (default) or `transaction` for bi-temporal reads. `recall_scope` is `full` (default, unless the bank `recall_scope_default` says otherwise) or `consolidated_only`, which returns consolidated units only and signals `scope_empty` instead of silently widening; `prefer_consolidated` drops raw items whose consolidated parent is also returned and backfills the freed slots from the next-best candidates, and is a no-op when no parent is returned. Retrieval hits expose optional source `context` as metadata; a deployment MAY use bounded context as a documented lexical signal, but it MUST NOT change category, `epistemic_kind`, or confidence. Scope and dedup never exceed the token budget, never cross banks, and leave explicit caller parameters in control. Co-activation updates apply on result sets (§4.5); reinforcement observes the pre-dedup candidate page under the same limit and budget, so suppression never silently drops reinforcement. | §4.5–4.6, PR-10, NFR-4, FR-17 |
| `compose_context(query?, domains?, budget_tokens, recall_scope?, prefer_consolidated?)` | Return the bounded pack the system *would* inject under PR-1 (persona channel + selected memories), without requiring the agent to assemble it ad hoc. MUST respect token budget. `recall_scope` / `prefer_consolidated` apply to the memory section only; the persona channel is always emitted under its own budget. Stored source `context` is metadata by default; if an explicit policy includes it in a pack, its tokens count against the same budget and the policy MUST be auditable. | PR-1, PR-10, §2.1, §4.7 |
| `associations(item_id, min_weight?)` | List co-activation / explicit edges and effective weights (after decay). | §4.5, FR-17–18 |

##### C. Persona (§4.7, P5, P9)

| Tool | Effect | Traces to |
|---|---|---|
| `persona_get()` | Return the current bounded persona object (`stable` + `preferences` + trends). | §4.7, FR-7 |
| `persona_put_stable(key, value, confidence?, evidence_ref?, context?)` | Upsert a discrete/categorical stable entry (invalidation semantics), including categorical preference labels. Enforces persona token budget. MUST reject scalar-intensity payloads that belong on the EMA path. `context`, when supplied, is bounded descriptive source metadata and does not change the persona update rule. | §4.7, PR-2, PR-10 |
| `persona_observe_preference(key, observed_value, confidence?, evidence_ref?, context?)` | EMA-update a continuous/scalar preference intensity; updates `trend`. `observed_value` MUST be numeric. MUST reject categorical strings (use `persona_put_stable` instead). `context`, when supplied, is bounded descriptive source metadata and does not change the EMA rule. | §4.7, P9, PR-2, PR-10 |

##### D. History subsystem (§4.8, P6, P7)

| Tool | Effect | Traces to |
|---|---|---|
| `task_upsert(task_id, definition, steps?, status, evidence_ref?, context?)` | Create/update a task history record (gated episodic write). `definition` and `status` are required (the implemented contract rejects an empty definition or status; there is no partial-update form). `context`, when supplied, is bounded descriptive source metadata. | §4.8, PR-10 |
| `task_get(task_id)` | Fetch task record + optional summarized ancestor view. | §4.8, FR-8 |
| `task_history(task_id, limit?)` | Prior attempts/steps for a task without full-log replay. | §4.8, P6 |
| `failure_record(task_id, attempt_n, what_failed, lesson, evidence_ref?, context?)` | Store a structured `FailureRecord` (§7.3); `lesson` length-capped; gated. `context`, when supplied, is bounded descriptive source metadata. | §4.8, §2.8, P7, PR-10 |
| `failures_for_task(task_id_or_query, limit?)` | Retrieve prior failures for same/similar task (FR-9). | FR-9, P7 |
| `memtree_query(time_range?, task_id?, depth?, limit?)` | Query MemTree leaves and/or ancestor summaries by time/task/depth. | §4.3, §4.8 episodic |
| `memtree_get(node_id)` | Fetch one MemTree node (leaf or aggregate). | §4.3 |
| `temporal_history(target, as_of?, time_axis?)` | Trajectory for a discrete fact, preference trend series, or belief confidence history. | §4.6, §4.8 temporal, §4.10, NFR-4 |

##### E. Triples, beliefs, explicit graph (§4.6, §4.10–4.11, §7.2)

| Tool | Effect | Traces to |
|---|---|---|
| `triple_add(subject, predicate, object, epistemic_kind, source_type?, valid_from?, valid_until?, confidence?, supersede?, snapshot_ref?, gist_ref?, context?)` | Write bi-temporal SPO edge; default supersede closes prior open subject+predicate. `context`, when supplied, is bounded descriptive source metadata. Gated. | §4.6, §7.2, P10, PR-10 |
| `triple_query(subject?, predicate?, object?, as_of?, time_axis?)` | Pattern query; point-in-time via `as_of` + `time_axis`. | §4.6, NFR-4 |
| `triple_end(subject, predicate, object?, valid_until)` | Expire without replacement. `valid_until` is required (the implemented contract has no "end at now" default). | §4.6, PR-6 |
| `belief_observe(proposition, confidence, evidence_ref, source_type, context?)` | Append a confidence-history entry (create belief if needed). `context`, when supplied, is bounded descriptive source metadata for the belief item; each evidence entry's `evidence_ref` remains the source identity. On append, `context` MUST be omitted or identical to the stored value; a differing value is a usage error (use `correct()` to change context). MUST NOT overwrite history. **Create** (no prior belief for the identity key): MUST pass five-factor admission (§4.2); category gate does not apply. **Append** (belief exists): MUST validate enums/ranges, bank/auth, and emit audit; MUST NOT re-run novelty/utility admission as if admitting a new item. | §4.10, FR-13, P11, PR-10 |
| `belief_history(belief_id_or_proposition)` | Return full confidence trajectory + source_types. | §4.10, P12, NFR-4 |
| `graph_link(source_id, target_id, relationship, weight?)` | Declare an explicit `assoc_edge` (`assoc_kind=explicit`). Identity includes `relationship` so multiple distinct relationships between the same item pair are allowed. Sticky by default (§4.5). | §4.5–4.6 |
| `graph_query(seed_id, max_hops?, edge_type?, min_weight?)` | Bounded multi-hop traversal over `assoc_edge` (filter by `assoc_kind` via `edge_type`). MUST NOT silently treat SPO triples as association weights. | §4.5 |

##### F. Transparency, correction, compliance (§4.12, §7.4, P12)

| Tool | Effect | Traces to |
|---|---|---|
| `inspect(filter?, limit?, offset?)` | List items for user/session/bank with epistemic_kind, scores, validity windows, optional source `context` subject to read authorization, and `source_ref`/evidence identity. | FR-16, PR-10, §4.12 |
| `correct(item_id, new_value, reason, context?)` | Auditable correction (uses update/invalidate rules). `context`, when supplied, is an explicit audited replacement; the prior context remains reconstructable via `audit_trail`. | FR-16, P12, PR-10 |
| `audit_trail(item_id)` | Reconstruct value/confidence/context/evidence history from write-path data; raw context is available only to authorized readers. | §4.12, FR-15, PR-10 |
| `export(destination, filter?)` | Export including confidence, admission, telemetry, optional source `context`, and `source_ref`/evidence identity (NFR-6), with a completeness manifest per §4.9.5.B. | NFR-6, PR-10, P12, §4.9.5.B |
| `erase_request(subject_id, legal_basis, request_id)` | Compliance crypto-shred path only (FR-19). MUST NOT alias `discard`. | §7.4, PR-6 |

##### G. Common parameters (all core tools)

| Parameter | Meaning |
|---|---|
| `bank` | Isolation key (per-repo / per-user / per-agent). Coding agents SHOULD use a stable per-repository bank. |
| `actor` | Attribution (agent / harness / user / system). |
| `dry_run` | Validate and report without durable mutation when the tool mutates. |
| `explain` | On reads: return score/domain/hop trace (P12). |

`context` is an item/record-level optional field on tools that create or update long-term memory; it is not a common global parameter. `evidence_ref` is the stable source-identity field. Tools that do not create a source-contextual long-term record MUST document that omission in their schema rather than silently accepting an unbounded value.

#### 4.9.5 Additive tools and operations platform

These exist so coding agents and operators can run the system under real harness constraints. They do **not** invent new memory *semantics* beyond this document; if an additive capability is omitted, Core tools must still satisfy all non-ops FRs. Coding-agent deployments SHALL expose the capabilities in this section except where a subsection explicitly allows single-host omission.

##### A. General additive tools

| Tool | Effect | Why additive |
|---|---|---|
| `batch(operations, dry_run?)` | Atomic multi-mutation of Core write tools. | End-of-turn ergonomics. |
| `scratchpad_write` / `scratchpad_read` / `scratchpad_clear` | Ephemeral workspace; not long-term memory. | Prevents P1 pollution in practice. |
| `canonical_put` / `canonical_get` | Single-slot upsert/read with supersession history; a context-bearing write MUST preserve bounded context and evidence identity. | Convenience over `store`+`invalidate`; still gated by §4.1. |
| `shared_store` / `shared_retrieve` / `shared_discard` | Cross-agent surface bank; shared long-term writes MUST preserve bounded context and evidence identity when supplied. | Multi-agent ops. |
| `validate(item_id, action, note?, new_content?)` | Collaborative attest/update/invalidate/delete. | Reviewer loops. |
| `hygiene_audit` / `hygiene_clean` | Ranked noise audit + confirmed cleanup (§4.9.5.A Hygiene). | Operational anti-bloat (P1). |
| `stats()` | Counts by bank/tier/category. | Operations. |

**Hygiene audit & cleanup (`hygiene_audit` / `hygiene_clean`):**

These tools implement operational anti-bloat. They are **operations removal** (§7.4 / PR-6), not fact supersession and not compliance erasure. `hygiene_clean` MUST NOT invoke crypto-shredding or alias `erase_request`.

1. **`hygiene_audit` (read-only).** Scan selected stores/banks for noise candidates (examples: terminal spam, command dumps, heartbeats, stack traces, accidental secrets). Return candidates **ranked by descending noise score** (`0.0`–`1.0`), each with `{item_id, noise_score, noise_reasons[], suggested_action, preview?}`. Support `min_score`, `limit`/`offset` (or equivalent pagination), and bank scope. MUST NOT mutate memory. Scoring weights MAY be deployment-tunable; given identical inputs and config, ranking MUST be deterministic (same spirit as NFR-5).

2. **`hygiene_clean` (mutating, confirmed).** Accept candidates from a prior audit (or equivalent id list). Actions: `flag` (mark for review, no removal), `archive` (reversible removal from active retrieval — e.g. decay/flag metadata), `discard` (ops removal from active use per §7.4; `delete` MAY be accepted as an alias for `discard` and MUST be documented as non-compliance), `keep` (apply each candidate's `suggested_action`). `confirm=true` is required for any mutation; without it the call is dry-run only and MUST report would-flag / would-archive / would-discard counts without writing.

3. **Secret protection.** `hygiene_audit` and `hygiene_clean` responses, dry-run reports, and hygiene audit-log entries MUST **mask** credentials, DEKs, API keys, tokens, and sync secrets (last-4 or redacted form only). When `noise_reasons` includes a secret-class hit, any content `preview` MUST be redacted; cleanup still addresses the item by `item_id`.

4. **Hygiene audit log.** Every `hygiene_clean` invocation that mutates (and every dry-run SHOULD) MUST append a durable, queryable hygiene audit-log entry: `{timestamp, actor, bank, action, item_ids[], noise_scores?, confirm, dry_run, result}`. Operators MUST be able to review every cleanup via a **hygiene-log list surface** (e.g. `hygiene_log_list`) and SHOULD also see item-level effects via `audit_trail` on affected items. Item-level telemetry for `discard`/`archive` paths MUST also satisfy FR-15.

##### B. Import / export

| Tool / command surface | Effect |
|---|---|
| `export(destination, filter?, content_mode?)` | Write a JSON export of selected memories **plus a completeness manifest**. `content_mode` defaults to `dsar_plaintext` (authorized decrypt → readable content); `ciphertext_backup` MAY emit opaque payloads without DEKs for like-to-like restore. |
| `import(source, dry_run?, force?)` | Idempotent JSON import from a prior export, preserving optional `context` and `source_ref`/evidence identity when present. |
| `import_provider(provider, credentials?, options?, dry_run?)` | Provider importer (mapped external memory systems — Hindsight, Mem0, Mnemosyne, Honcho, Supermemory; not LLM/chat vendors). **First release MAY stub** this tool (`PROVIDER_IMPORT_UNSUPPORTED`); full adapters are out of first release. |

**Export MUST include:**

1. **Payload** — memory items with snapshot/gist refs, optional source `context`, `source_ref`/evidence identity, triples, persona, task/failure/temporal records, graph edges including **`assoc_edge`** (coactivation + explicit), confidence/admission/telemetry fields (NFR-6). Under default `content_mode=dsar_plaintext`, content is decrypted in-process under caller authorization before write. Under `ciphertext_backup`, content bodies MAY remain opaque (no DEKs in file); metadata inventory remains complete. Erased subjects contribute tombstone metadata only.
2. **Completeness manifest** — machine-readable inventory: schema/export format version, `content_mode`, bank id(s), item counts by type/category, content checksums (or equivalent integrity hashes) covering context and evidence identity when present, filter used, generated-at timestamp, and an explicit `complete: true|false` flag. If the export was filtered or truncated, `complete` MUST be `false` and the manifest MUST state what was omitted.
3. **No secrets in plaintext** — DEKs, API keys, and sync credentials MUST NOT appear in the export file.

**Import MUST:**

1. Be **idempotent by default** — re-importing the same export (same item identities / content hashes) MUST NOT duplicate durable rows; `force=true` MAY overwrite with an auditable reason.
2. Run every candidate through §4.1–§4.2 before commit (same gates as `store`) for `dsar_plaintext` imports.
3. Support `dry_run=true`, which MUST return a **dry-run report** (would-create / would-skip / would-reject / would-overwrite counts and sample rejection reasons) **without writing**.
4. For `import_provider`, **when a provider adapter is implemented**, accept credentials only via secure binding parameters or environment; any logged or returned diagnostic MUST **mask** credentials (show last-4 or redacted form only). Provider dry-run MUST produce the same report shape as JSON import dry-run before any write. Provider items enter with provenance `provider:<id>` (external item id in `source_ref`), pass §4.1–§4.2 like JSON imports, skip FR-4 span grounding (no local source span exists), default to `epistemic_kind=belief` with `source_type=third_party` unless independently verified, and are idempotent by external id (repeat pull no-ops; provider-side deletions are not mirrored). **First release MAY ship `import_provider` as a non-writing stub**; the masking rule still applies to any credential parameters accepted by the stub.
5. Import MUST preserve optional `context` and `source_ref`/evidence identity from the bundle, validate them against §4.4, and carry them through the same admission, audit, sync, and erase paths as the item content. If a provider adapter is implemented later, its context field MUST map to the native `context` field rather than create a parallel provider-specific contract. External document identifiers MAY be carried opaquely in `evidence_ref`; doing so preserves identity only and confers no document-container semantics (see §9).

##### C. Diagnose / doctor / verify / repair / reindex

Operator and agent-facing health surfaces. All are PII-safe: they MUST NOT return memory content, DEKs, or API keys.

| Tool | Effect |
|---|---|
| `diagnose()` | Read-only install + database health snapshot (backend reachable, schema version, vector index presence, embedding pipeline ready, bank list, obvious corruption signals). |
| `verify()` | Deeper consistency checks (referential integrity of snapshot/gist/triple refs, orphan edges, manifest-vs-store count drift, vector row coverage vs episodic leaves). Returns pass/fail findings. |
| `doctor(dry_run?)` | Compose an ordered **repair plan** from `diagnose`+`verify` findings. Default `dry_run=true`: print the plan only. **`doctor` MUST NOT mutate** the store under any `dry_run` value; `dry_run=false` only materializes/persists a plan id for `repair`. |
| `repair(plan_id_or_actions, confirm)` | Apply gated fixes from a doctor plan. `confirm=true` required to mutate. MUST refuse unknown actions. |
| `reindex(target?, dry_run?)` | Rebuild dense-vector and/or lexical indexes (and optional MemTree ancestor materializations) for a bank or whole store. `dry_run=true` reports scope/cost without writing. |

**Process / CLI contract:** when these surfaces are invoked as commands (or equivalent non-interactive jobs), a failed `verify`, a refused `repair`, or an aborted `reindex` MUST exit **non-zero** so automation treats it as failure. Interactive agent-tool bindings MUST return a structured `{ok: false, code, findings}` instead of silently succeeding.

##### D. Sync protocol (client + server)

Deployments that claim multi-host or multi-device memory SHALL implement a **client/server sync protocol**. Single-host deployments MAY omit sync; if omitted, docs MUST say so.

| Surface | Effect |
|---|---|
| `sync_serve(bind, auth?)` | Run a sync **server** that accepts pull/push from authenticated clients for one or more banks. |
| `sync_push(remote?, mode?)` | Client: send local durable mutations since last cursor. |
| `sync_pull(remote?, mode?)` | Client: fetch and apply remote mutations since last cursor. |
| `sync_status()` | Device id, cursors, pending counts, remote endpoint, auth/encryption state, last error. |

**Protocol requirements (improvised, normative for this project):**

1. **Roles** — at least one process MAY run as server; one or more processes run as clients. A node MAY be both (serve while also pushing to an upstream) if documented.
2. **Delta / cursor** — sync is incremental; clients and server track opaque cursors (or equivalent) so only unseen mutations move.
3. **Idempotent apply** — duplicate delivery MUST NOT duplicate memories; identity is by stable item/event id.
4. **Conflict rule** — document one deterministic default (e.g. later `transaction_time` wins; tie-break on admission_score/importance then device id). Conflicts MUST be logged and visible via `sync_status`. Sync apply of already-admitted peer creates MUST NOT re-run local admission scoring in a way that rejects convergent replicas (schema/category/authz/erasure checks still apply).
5. **Auth** — server endpoints MUST require authentication in non-dev mode.
6. **Encryption** — content MAY be client-encrypted before leaving the node; server MUST be able to store opaque ciphertext without needing DEKs (compatible with §7.4 separation of KMS and item store).
7. **Bank scope** — sync SHOULD be selectable per `bank`; default MAY be all banks on that device.
8. **Modes** — push-only, pull-only, and bidirectional MUST be supported.
9. **Association edges** — when multi-host sync is claimed, durable `assoc_edge` mutations (coactivation reinforce, explicit `graph_link`, prune) MUST be included in the sync payload with the same idempotent-apply rules as other graph metadata.
10. **Context and evidence identity** — when multi-host sync is claimed, source `context` and `source_ref`/`evidence_ref` identity MUST travel with the corresponding item mutation, remain subject to the same encryption and erase rules, and use the same idempotent-apply identity.

##### E. Effective configuration, profiles, and ranking environment

| Tool | Effect |
|---|---|
| `config_get(path?)` | Show **effective** configuration after defaults + files + env + runtime overlays (not merely the raw file). Secrets MUST be masked. |
| `config_set(path, value, scope?)` | Change a config value at `session` \| `profile` \| `deployment` scope; validate types/ranges before apply. |
| `config_profiles()` | List named profiles (e.g. `coding_local`, `coding_ci`, `companion_low_latency`). |
| `config_profile_apply(name)` | Activate a profile; returns the effective config diff. |
| `ranking_env_get()` | Show effective hybrid ranking / admission-related environment: retrieval weights (dense, lexical, importance, temporal), admission weight vector `w1…w5`, co-activation constants (`η`, half-life, `w_min`), intent-gate thresholds if any. |
| `ranking_env_set(patch, dry_run?)` | Patch ranking/admission env for current profile/session; `dry_run` returns the normalized weights that would apply. Weights that must sum to 1.0 MUST be renormalized or rejected with a clear error. |
| `retention_profile_get(bank?)` | Show the effective per-bank `retention_profile` (verbosity, bounded per-category `theta_offsets`, `duplicate_tolerance_write`, version), where it resolved from (`bank` \| `deployment` \| `builtin`), and the read-side scope/dedup fields (`duplicate_tolerance_read`, `recall_scope_default`) inside an `accepted_but_inert` envelope that names the capability honoring them and reports them active. |
| `retention_profile_set(bank?, profile, scope?, confirm?)` | Validate and store a bank-scoped `retention_profile` (`scope=bank`, default) or the deployment default (`scope=deployment`); without `confirm=true` it returns a no-write preview. Profile strictness changes admission thresholds and duplicate cutoffs only; it never deletes, invalidates, or shreds anything (PR-6). |

Profiles are named bundles of effective settings (backend choice hints, bank defaults, ranking env, injection budgets, sync remotes). Applying a profile MUST NOT bypass §4.1–§4.2 gates; it only changes knobs those sections already allow to be deployment-tunable (§4.2 weights, §4.5 constants, NFR budgets).

#### 4.9.6 Coding-agent profile

Coding-agent deployments SHALL expose **all Core tools (§4.9.4)** and **all Additive capabilities (§4.9.5)** except §4.9.5.D sync when the deployment is single-host. Highest-leverage Core tools for coding agents:

1. `store` / `retrieve` / `compose_context` / `batch` — admit and budgeted recall without replay (P1, P6).
2. `failure_record` / `failures_for_task` / `task_*` — retry without repeating mistakes (P7).
3. `triple_*` / `get_snapshot` / `temporal_history` — durable facts and exact values (P3, P10).
4. `memtree_query` / `consolidate` / `maintenance_status` — long-session structure without blocking writes (P2).
5. `persona_*` only when the coding agent also acts as a companion; otherwise bank-scoped `store` of `tool_config` / `output_constraint` carries conventions.

Operators and coding agents SHOULD also use `hygiene_audit`/`hygiene_clean`, `doctor`/`verify`/`reindex`, manifest-backed `export`/`import`, and `config_profile_apply` / `ranking_env_*` when tuning a repo bank.

#### 4.9.7 What tools MUST NOT do

- Bypass category whitelist or admission scoring for long-term writes (PR-3, PR-5).
- Treat `discard` as compliance erasure, or `erase_request` as casual cleanup (§7.4).
- Return gist-only payloads as authoritative for exact identifiers, versions, ports, hashes, or error codes (PR-4).
- Auto-inject unbounded scratchpad, full MemTree, or full history into model context (PR-1).
- Apply EMA updates to discrete/categorical attributes or invalidation to continuous/scalar preferences (PR-2, §4.7). Never pass `fact`/`belief` as `update_rule`, or store `update_rule` in the item `epistemic_kind` column.
- Treat source `context` as descriptive metadata rather than a category, truth claim, source span, or instruction; never inject it into model context without the PR-1 budget and an explicit policy.
- Log or return unmasked credentials, DEKs, or sync keys from import, diagnose, doctor, config, sync status, or hygiene (`hygiene_audit` / `hygiene_clean`) surfaces.

The agent decides *when* to call; the system decides *whether gated calls succeed* (§2.3 / PR-3).

### 4.10 Belief Evolution & Confidence Tracking (addresses P11)

A belief is any proposition that is **not independently verified** (per §4.11) — including agent inferences (e.g., "user is likely vegetarian") and user-stated self-reports. Provenance lives in `source_type`, not in a separate epistemic kind. It is stored as a versioned **belief object** (§4.10 store), distinct from a discrete fact's bi-temporal edge and distinct from the five §4.1 semantic categories:

```json
{
  "proposition": "user_diet_preference = vegetarian",
  "context": "team chat",
  "epistemic_kind": "belief",
  "confidence_history": [
    {"as_of": "2026-06-01", "confidence": 0.4, "evidence_ref": "turn_112", "source_type": "agent_inferred"},
    {"as_of": "2026-07-14", "confidence": 0.65, "evidence_ref": "turn_340", "source_type": "agent_inferred"},
    {"as_of": "2026-09-02", "confidence": 0.9,  "evidence_ref": "turn_501", "source_type": "user_stated"}
  ]
}
```
Each new piece of evidence appends a confidence-history entry rather than overwriting the prior one; the current confidence is the latest entry, but the trajectory remains inspectable — directly serving the transparency requirement (§4.12/P12) and giving a concrete, queryable answer to how a belief evolved over time.

Each confidence-history entry carries a `source_type` (`user_stated` / `agent_inferred` / `third_party`), recording how that piece of evidence arrived. This is what distinguishes a user's stated view from the agent's own inference, without requiring a separate epistemic kind (§4.11). A belief item MAY carry an optional item-level `context` describing the setting in which the proposition was captured; each confidence-history entry's `evidence_ref` remains the source identity for that evidence, and context MUST NOT replace it. On append, `context` MUST be omitted or byte-identical to the stored item-level value; a differing value is a usage error, and changing context requires the authorized correction path (`correct()`).

**Admission (normative):** Beliefs are **not** admitted by inventing a sixth semantic category or a new episodic type tag. `belief_observe` uses the §4.9.3 belief-writes row: category gate **N/A**; five-factor admission **MUST** when **creating** a new belief identity; subsequent **appends** to an existing belief MUST validate `confidence` / `source_type` / bank scope and emit audit, and MUST NOT re-score the proposition as a brand-new admission candidate (novelty/utility gates already decided at create).

### 4.11 Fact vs. Belief Classification (addresses P13)

A statement can be evaluated along two independent dimensions: whether it is independently verifiable, and, if not, who supplied the evidence behind it. Conflating these into three peer classes (fact / opinion / belief) forces a judgment call on every ambiguous self-report — a user's subjective statement ("I think I'm mostly vegetarian") could plausibly be filed under either of two non-fact classes with no principled way to choose. Tracking provenance as a *field* rather than as a peer *kind* removes that judgment call: a user's stated view is a belief with `source_type = user_stated`, typically at high initial confidence; an agent's inference is a belief with `source_type = agent_inferred`, typically starting lower and accumulating over several pieces of evidence (§4.10). Both are the same structure with different provenance.

The taxonomy is therefore two epistemic kinds:
- `fact` — directly verifiable or system-of-record content that has passed the §4.4 verification pass. High default confidence; superseded via bi-temporal invalidation (§4.6), not gradually updated, and never carries a confidence trajectory.
- `belief` — everything else. Always carries a `source_type`-tagged confidence history (§4.10). Never treated as ground truth for downstream actions without a confidence check against a caller-supplied threshold, regardless of `source_type` — a high-confidence `user_stated` belief is still a belief, not a fact, because the user's self-report is not independently verified.

Retrieval responses MUST surface `epistemic_kind`, and, when `epistemic_kind = belief`, `source_type` and current confidence, alongside content. A consuming agent that treats any `belief` — high-confidence or `user_stated` included — as a `fact` without an explicit confidence-threshold check is a bug, per PR-8.

### 4.12 Transparency & Audit (addresses P12)

- Every store/update/discard/invalidate/**hygiene_clean** operation MUST emit a telemetry event: `{operation, item_id, category, epistemic_kind, confidence, admission_score, actor (agent/system/user), timestamp}` (hygiene events MAY omit fields that do not apply, but MUST include `operation`, `item_id`, `actor`, `timestamp`, and the hygiene `action`). For items carrying `context`, telemetry MUST record whether context was present, its length, and a hash for change detection only (the hash is not a confidentiality mechanism for low-entropy values); ordinary telemetry MUST NOT emit raw context.
- A queryable audit trail MUST allow reconstructing, for any item, its full history of values, confidences, context changes, and the evidence references that produced each change, reusing the confidence-history and bi-temporal structures already required in §4.6/§4.10 — transparency is a read-side view over data the write path already tracks, not a separate logging system to build and keep in sync. Raw context is available only through an authorized content read and MUST be redacted in ordinary diagnostics. Hygiene cleanups MUST additionally be reviewable via the hygiene audit log in §4.9.5.A.
- A "memory inspector" read/correct/erase path MUST exist for developers (and, where required by applicable regulation, end users) and MUST be exposed through the `inspect`, `correct`, and `erase_request` tools in §4.9 (FR-16).

---

## 5. Functional Requirements

| ID | Requirement | Traces to |
|---|---|---|
| FR-1 | The system SHALL reject, at write time, any candidate semantic item whose category is not one of the five whitelisted categories in §4.1. | P1, PR-3 |
| FR-2 | The system SHALL compute an admission score for every category-eligible candidate and SHALL discard candidates scoring below the configured threshold, with the discard logged. | P1, PR-5 |
| FR-3 | New episodic items SHALL be queryable at the leaf level of the memory index before any ancestor-node structural maintenance for that item completes. | P2, PR-9 |
| FR-4 | Extraction of a candidate memory SHALL verify every entity/number/date in the structured snapshot against a **locatable source span** before commit (entities: contiguous substring; numbers/dates: a source substring that parses to the same value under documented format rules—normalized value alone without a span is insufficient); on verification failure, the system SHALL retry extraction once, then SHALL NOT commit the structured snapshot. The rejection SHALL be logged; a non-authoritative gist or diagnostic candidate MAY be retained for review but MUST NOT be treated as an admitted snapshot. | P3, PR-4 |
| FR-5 | Every operational memory unit SHALL maintain both a structured snapshot and a prose gist as separate fields; no downstream consumer SHALL be given only the gist when the query concerns a specific number, name, or date. | P3, PR-4 |
| FR-6 | The system SHALL classify every incoming turn via an intent gate before running any embedding/graph retrieval, and SHALL skip retrieval when the gate determines it is not needed. | P4, PR-7 |
| FR-7 | The persona/stable-preference object SHALL be injected on every turn independent of the intent-gate decision, subject to its own fixed token budget. | P5, §2.7 |
| FR-8 | History retrieval SHALL return only the subset of episodic/task/failure/temporal records relevant to the current query scope; full-log replay SHALL NOT be the default retrieval path. | P6, PR-1 |
| FR-9 | On repeated attempts at the same or a **similar** task, the system SHALL surface prior `FailureRecord`s for that task before or alongside the agent's next attempt. **Same** = identical `task_id`. **Similar** = task definitions meeting a configured lexical and/or embedding similarity threshold (defaults documented; MUST be implemented—exact-`task_id`-only is not sufficient). Surfacing MUST be a system path (retrieve/compose domain `failure` and/or a dedicated prepare-retry helper), not documentation-only. | P7 |
| FR-10 | Memory operations SHALL be exposed to agents as the callable tool catalog in §4.9. Core tools (§4.9.4) are mandatory for all deployments. Additive capabilities (§4.9.5) are mandatory for coding-agent deployments (§4.9.5.D sync excepted on single-host). No memory admission/eviction decision SHALL bypass those tools' gating logic. | P8, PR-3 |
| FR-11 | Every attribute schema SHALL declare an `update_rule` of `discrete` or `continuous` at definition time; the write path SHALL reject an update using the invalidation rule on a `continuous` attribute or the EMA rule on a `discrete` attribute. The `update` tool parameter is `update_rule` (not item `epistemic_kind`). | P9, P10, PR-2 |
| FR-12 | Superseding a discrete fact SHALL invalidate the prior edge by setting **both** `valid_time.end` and `transaction_time.end` (identity key: `subject`+`predicate` per §4.6); the supersession path SHALL NOT delete the prior edge. Compliance destruction of personal content uses §7.4 crypto-shredding only. Operations `discard`/pruning are a separate logged path and MUST NOT be used as silent supersession. | P10, PR-6 |
| FR-13 | Belief objects SHALL store a confidence history (append-only) rather than a single overwritten confidence value; agents SHALL append evidence via `belief_observe` and read trajectories via `belief_history`. Creating a new belief identity SHALL pass admission scoring; appending to an existing belief SHALL NOT require re-passing novelty/utility admission. | P11, §4.10 |
| FR-14 | Every stored item SHALL carry an `epistemic_kind` field with value `fact` or `belief`; every item with `epistemic_kind = belief` SHALL additionally carry, per confidence-history entry, a `source_type` of `user_stated`, `agent_inferred`, or `third_party`. Retrieval responses SHALL surface `epistemic_kind` and, for beliefs, current `source_type` and confidence, to the consumer. | P13, §4.11 |
| FR-15 | Every store/update/discard/invalidate/hygiene_clean operation SHALL emit a telemetry/audit event sufficient to reconstruct the item's full history, including context changes when present (and, for hygiene, the cleanup action); `audit_trail` SHALL expose that history. | P12, PR-10 |
| FR-16 | A memory inspector API SHALL allow listing, correcting, and requesting deletion of items associated with a given user or session, via `inspect`, `correct`, and `erase_request`. | P12 |
| FR-17 | Memories retrieved together within one retrieval call SHALL have their pairwise **co-activation** association weight increased on `assoc_edge` records; retrieval MAY use these weights to spread activation to associated items beyond direct similarity matches; `associations` SHALL expose effective weights. The increase MUST be **durably handed off** before or with the retrieve response (same transaction, or durable outbox/queue). Silently skipping reinforce on transient errors is FORBIDDEN; if durable handoff fails, the retrieve MUST fail closed or return a structured degraded error that forces retry—best-effort soft-drop of FR-17 updates is not compliant. | Co-activation retrieval |
| FR-18 | Co-activation (`assoc_kind=coactivation`) edge weights SHALL follow the `association_weight_policy` (saturating growth, lazy exponential decay, pruning threshold) in §4.5; such an edge SHALL NOT grow without bound or persist indefinitely once its decayed weight falls below the pruning threshold. Explicit sticky edges follow §4.5 explicit-edge rules, not co-activation decay, unless a documented longer half-life is configured. | §4.5 |
| FR-19 | A verified data-subject erasure request SHALL result in destruction of that subject's data encryption key within the legally mandated window, SHALL trigger dirty-path regeneration of every derived structure referencing the erased content, and SHALL produce a tombstone containing no reconstructable personal data. | P12, §7.4 |
| FR-20 | The implementation SHALL publish a machine-readable **`tool_schema`** for every exposed tool in §4.9 and SHALL expose Core tools through at least one harness-consumable binding; MCP (stdio and Streamable HTTP) SHOULD be the reference binding (legacy HTTP+SSE only when a harness still requires it), pinned per §4.9.2 item 3. Tool semantics MUST be identical across bindings. | §4.9.2, P8 |
| FR-21 | Long-term write tools SHALL enforce §4.1 / §4.2 as specified in the §4.9.3 gating matrix; `admit_preview` SHALL expose the same decision without writing; scratchpad tools (additive) SHALL NOT write to long-term stores. | PR-3, PR-5, §4.9 |
| FR-22 | Coding-agent deployments SHALL support per-repository `bank` isolation and SHALL expose all Core tools plus Additive capabilities per FR-10 / §4.9.6. | P6, P7, P8, §4.9.6 |
| FR-23 | `batch` (when exposed) SHALL apply mutations atomically. `discard`, hygiene `discard`/`delete`, and `erase_request` SHALL remain distinct (hygiene never satisfies compliance erasure). | §4.9, PR-6, §7.4 |
| FR-24 | `retrieve`, `triple_query`, and `temporal_history` SHALL honor `as_of` and `time_axis` (`valid` \| `transaction`) when provided. Explicit agent read tools SHALL execute even when the automatic intent gate would skip background retrieval. | NFR-4, §4.5–4.6, §4.9 |
| FR-25 | The system SHALL expose `persona_get`, `persona_put_stable`, and `persona_observe_preference` so the §4.7 split is agent-callable without overloading generic `store`/`update`: categorical/durable attributes via `persona_put_stable` (discrete), scalar intensities via `persona_observe_preference` (EMA). | P5, P9, §4.7 |
| FR-26 | The system SHALL expose `get_snapshot` and `get_gist` as separate reads; consumers needing exact values SHALL use snapshots (PR-4). | P3, FR-5 |
| FR-27 | The system SHALL expose `failure_record`, `failures_for_task`, `task_upsert`, `task_get`, `task_history`, `memtree_query`, and `temporal_history` so §4.8 history types are selectively retrievable without full-log replay. | P6, P7, FR-8, FR-9 |
| FR-28 | The system SHALL expose `intent_gate`, `compose_context`, and `maintenance_status` so intent decisions, PR-1 injection budgets, and PR-9 dirty-path state are inspectable by agents and developers. | P1, P2, P4, PR-1, PR-9 |
| FR-29 | JSON `export` SHALL include a completeness manifest (version, counts, checksums, filter, `complete` flag, `content_mode`). Default export mode `dsar_plaintext` SHALL decrypt under authorization for readable audit/DSAR content; `ciphertext_backup` MAY emit opaque payloads without DEKs. JSON `import` SHALL be idempotent by default, SHALL enforce §4.1–§4.2 for plaintext imports, and SHALL support a dry-run report with zero writes. **When** a provider adapter is implemented, it SHALL mask credentials in all logs/reports and SHALL offer the same dry-run report before writing. First release MAY stub `import_provider` as non-writing (masking still required for any accepted credential params). | §4.9.5.B, NFR-6, P12 |
| FR-30 | The system SHALL expose `diagnose`, `verify`, `doctor`, `repair`, and `reindex` per §4.9.5.C. `doctor` SHALL NOT mutate the store. Mutating repair/reindex SHALL be gated by confirmation (or equivalent). Non-interactive failures SHALL surface as non-zero process exit status; tool bindings SHALL return structured failure objects. | §4.9.5.C |
| FR-31 | Multi-host deployments SHALL implement the client/server sync protocol in §4.9.5.D (`sync_serve`, `sync_push`, `sync_pull`, `sync_status`) with incremental cursors, idempotent apply, authentication in non-dev mode, a documented deterministic conflict rule, and apply semantics that do not reject already-admitted peer creates solely due to local admission θ. | §4.9.5.D |
| FR-32 | The system SHALL expose effective-configuration and profile tools (`config_get`, `config_set`, `config_profiles`, `config_profile_apply`) and ranking-environment tools (`ranking_env_get`, `ranking_env_set`) per §4.9.5.E. Secrets in config views SHALL be masked. Profile/ranking changes MUST NOT bypass admission or category gates. | §4.9.5.E, §4.2, §4.5 |
| FR-33 | Coding-agent deployments (and any deployment that exposes §4.9.5.A hygiene) SHALL provide `hygiene_audit` and `hygiene_clean` per §4.9.5.A: candidates ranked by noise score; confirmed `flag`/`archive`/`discard` (optional `delete` alias) with dry-run when unconfirmed; secret masking on all hygiene I/O; a durable hygiene audit log; and a callable hygiene-log list surface so every cleanup is reviewable. Hygiene MUST NOT perform compliance erasure. | P1, P12, PR-6, §4.9.5.A, §7.4 |
| FR-34 | The system SHALL support an optional, bounded, UTF-8 `context` field on long-term memory items. `context` MUST be descriptive source metadata; it MUST NOT be a category, `epistemic_kind`, `source_type`, confidence value, `source_text`, or model instruction. It MUST be preserved through create, read, update/correct, import/export, sync, and authorized audit, and MUST be removed or rendered unreadable through the erase lifecycle according to §7.4. `retrieve`, `get`, `inspect`, and `audit_trail` MUST expose it as metadata rather than silently discard it; other domain reads that return context-bearing records (`persona_get`, `task_get`/`task_history`, `temporal_history`, `belief_history`) MUST surface the stored context alongside the record. Context included in a model-facing pack MUST count against the PR-1 budget and require an explicit bounded policy. | P1, P3, P12, PR-1, PR-4, PR-8, PR-10, FR-4, FR-5, FR-15, FR-20, FR-29, NFR-3, NFR-6 |
| FR-35 | The system SHALL treat `evidence_ref` as the provider-neutral stable source/provenance identity for a memory item. At the item level, the `store` tool's `evidence_ref` MUST populate `source_ref` per the glossary precedence rule; per-entry `evidence_ref` values inside belief confidence history identify individual evidence items and are exempt from the item-level alias. `evidence_ref` MAY identify a source turn, tool call, external memory item, or other source record. It MUST NOT be used as the source-span haystack or as an authorization token. No document-container semantics are implied (see §9). | P12, PR-8, PR-10, §4.4, FR-14, FR-20, FR-29 |

---

## 6. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | p95 latency added by the intent gate itself SHALL NOT exceed 50 ms; a "no retrieval needed" turn SHALL add no embedding-search or graph-traversal latency beyond the gate call. |
| NFR-2 | A newly written episodic item SHALL be retrievable within a bounded time window (target: under 2 seconds) of the source turn completing, independent of background structural maintenance duration. |
| NFR-3 | Persona-channel injection SHALL NOT exceed its configured token budget on any turn. |
| NFR-4 | The system SHALL support point-in-time queries ("what did we believe/know as of date X") for any discrete fact and any belief's confidence trajectory. |
| NFR-5 | Admission scoring, category gating, and epistemic_kind tagging SHALL be deterministic given identical inputs and configuration. |
| NFR-6 | All confidence, admission-score, telemetry, source `context`, and `source_ref`/evidence-identity fields SHALL be included in any data export produced for audit or data-subject-access purposes when present and authorized. |
| NFR-7 | Tool-catalog bindings SHALL remain language-agnostic at the requirements layer: an agent MUST be able to exercise every §4.9 tool through the published schema without depending on a specific implementation language. |
| NFR-8 | Non-interactive invocations of `verify`, `repair`, and `reindex` that do not fully succeed SHALL exit with a non-zero status code suitable for CI/automation. |
| NFR-9 | Context values SHALL have a published maximum and SHALL be rejected when they exceed it; context MUST NOT create unbounded storage, retrieval, or model-injection cost. Any context included in `compose_context` SHALL count against the requested token budget. |

---

## 7. Data Model (Reference Schemas)

All long-term memory record schemas MAY carry the optional source `context` field defined in §4.4. `context` is descriptive metadata associated with the record's source; it is not a field of the closed category taxonomy and is not authoritative for exact values. The schemas below show the field where the record type is expected to carry it.

### 7.1 Semantic Item
```json
{
  "id": "sem_0001",
  "category": "persona|task_spec|schema|tool_config|output_constraint",
  "epistemic_kind": "fact|belief",
  "source_type": "user_stated|agent_inferred|third_party (present only when epistemic_kind=belief)",
  "value": "…",
  "confidence": 0.0,
  "admission_score": 0.0,
  "source_ref": "turn_id or tool_call_id or namespaced external source id",
  "context": "…",
  "created_at": "ISO-8601",
  "valid_time": {"start": "ISO-8601", "end": null},
  "transaction_time": {"start": "ISO-8601", "end": null}
}
```

### 7.2 Episodic Triple
```json
{
  "subject": "…", "predicate": "…", "object": "…",
  "epistemic_kind": "fact|belief",
  "source_type": "user_stated|agent_inferred|third_party (present only when epistemic_kind=belief)",
  "source_ref": "turn_id or namespaced external source id",
  "context": "…",
  "valid_time": {"start": "…", "end": null},
  "transaction_time": {"start": "…", "end": null},
  "snapshot_ref": "atomic_fact_0004",
  "gist_ref": "summary_node_112"
}
```

### 7.3 Failure Record
```json
{
  "task_id": "…", "attempt_n": 2,
  "what_failed": "…", "lesson": "≤ N tokens",
  "evidence_ref": "trace_id or namespaced external source id",
  "context": "…", "epistemic_kind": "belief"
}
```

### 7.4 Deletion vs. Invalidation — Compliance-Grade Erasure

Invalidation, operations removal, and compliance erasure are not the same operation with a different flag; they sit at different layers of the stack, and only crypto-shredding is a compliance mechanism.

**Invalidation (default, §4.6, PR-6).** The mechanism for ordinary fact supersession. The record stays in the graph; its `valid_time` and `transaction_time` intervals close as specified in §4.6—the row is not deleted. On its own, invalidation is **not** sufficient to satisfy a data-subject erasure request, because the personal-data content remains stored and reconstructable.

**Operations removal (`discard`, pruning, hygiene — §4.9).** Logged removal from *active use* (and, for pruning, deletion of low-weight co-activation edges). This path is not fact supersession and is not compliance erasure. Implementations MUST keep it auditable (PR-8) and MUST NOT treat it as satisfying a data-subject erasure request.

**Compliance erasure (deletion), specified as follows:**

1. **Field-level encryption per data subject.** Every memory item's content payload — the structured snapshot (§7.2), the gist text, the belief proposition text, and source `context` when present — is stored encrypted under a per-data-subject data encryption key (DEK) held in a key-management service separate from the item store. The bi-temporal *structure* (that an edge existed, its timestamps, its relationships to other edges) is treated as metadata and MAY remain in plaintext; the *content* is unreadable without the DEK. `source_ref`/`evidence_ref` is provenance metadata and MUST NOT be used as a substitute for content protection when its value can contain personal data.
2. **Crypto-shredding on verified request.** On a verified erasure request, the subject's DEK is destroyed within the legally mandated window (e.g., without undue delay and in any case within one month under GDPR Art. 12(3)/17, subject to permitted extensions). Destroying the DEK renders every encrypted payload for that subject — in the primary store, replicas, and any encrypted backups sharing the same ciphertext — permanently unrecoverable, without requiring the system to locate and rewrite every historical backup snapshot individually. This is the standard mechanism for satisfying erasure obligations against append-only, versioned, or backed-up storage, and it is what makes PR-6 (supersession retains history) compatible with a real erasure right: PR-6 governs the supersession/structural layer; the DEK governs whether the content behind that structure is legible at all.
3. **Propagation to derived structures.** Anything that references or paraphrases the erased content — MemTree ancestor summaries (§4.3), gist prose, belief confidence-history entries (§4.10), source-context-bearing derived projections, co-activation edges (§4.5) — MUST be regenerated via the existing dirty-path mechanism (§4.3), so no derived summary or readable context projection continues to describe content that is no longer legible. Deletion triggers the same recomputation pipeline as an ordinary update; it is not a separate code path that can silently fall out of sync with it.
4. **Content-free tombstone.** The audit tombstone (PR-8, §4.12) records that a deletion occurred, its legal basis, timestamp, and authorizing request ID — but MUST NOT contain the erased content itself, only the item's category, a one-way hash of the item ID, and a deletion reason code. A tombstone that reconstructed the erased personal data would defeat the erasure it is supposed to evidence.
5. **Anonymized derivatives are handled explicitly, not assumed exempt.** A distilled hub-cluster semantic item (§4.5) or an aggregate statistic that no longer identifies the individual falls outside the personal-data scope of most erasure obligations and MAY be retained — but this determination MUST be affirmatively logged per item at the time of distillation, not assumed by default merely because the item is "derived."

Crypto-shredding is the sole **compliance** deletion path. Routine memory management uses three distinct mechanisms and MUST NOT conflate them: (1) invalidation for ordinary supersession (PR-6), (2) logged `discard` / pruning / hygiene for operations removal from active use (§4.9), and (3) crypto-shredding only on a verified legal erasure request. That separation keeps PR-6 intact for everyday supersession while making compliance erasure a specified, auditable exception.

---

## 8. Evaluation & Acceptance Criteria

- Retrieval quality SHOULD be benchmarked against established long-term conversational memory benchmarks (e.g., multi-session QA benchmarks such as LongMemEval-style and LoCoMo-style evaluations) covering single-hop, multi-hop, and temporal-reasoning question categories, since temporal-reasoning questions specifically stress the bi-temporal model in §4.6 and are the category where naive embedding-only retrieval is known to fail.
- Fidelity (P3/FR-4/FR-5) acceptance: on a held-out set of turns containing exact numbers/names/dates, ≥ 99% of admitted structured snapshots SHALL pass FR-4 span grounding (locatable source span; numbers/dates via span-parse rules in §4.4); failures below this bar block release. Snapshot fields MAY store a documented canonical form of a located span; they MUST NOT admit values with no locatable span.
- Write-path latency (P2/FR-3/NFR-2) acceptance: time-to-queryable for a new episodic item SHALL be measured independent of any queued structural-maintenance job; the two SHALL be reported as separate metrics, not conflated.
- Retrieval-skip precision (P4/FR-6) acceptance: the intent gate's false-negative rate (needed memory, gate says skip) SHALL be tracked separately from and held to a stricter bound than its false-positive rate (unneeded memory, gate says search), because a false negative produces a wrong answer while a false positive only costs latency.
- Context contract (FR-34/NFR-9) acceptance: valid context round-trips through store/read/import/export/sync/audit/erase; empty or oversized context is rejected without silent truncation; context does not change category, epistemic classification, or span verification; and any context included by `compose_context` remains within the requested budget.
- Evidence identity (FR-35) acceptance: an external document or memory identifier supplied through `evidence_ref` remains stable and attributable through import/export and all bindings, without being used as source-span evidence; no document-container behavior is asserted.

---

## 9. Risks & Open Issues

- **Admission-scoring weight drift.** The five weights in §4.2 (`w1`…`w5`) are tuned empirically against how a *deployment* — a distinct instantiation of this specification with its own users and task domain (e.g., a companion chatbot, an autonomous coding agent, an enterprise research assistant, each running on this same memory architecture but configured independently) — actually uses memory in practice. Weights tuned to perform well for one deployment are not guaranteed to perform well for another, because what counts as high "future utility" or a trustworthy "content-type prior" differs by task domain: a coding agent's task-history items and a companion's persona items do not share a utility distribution. This is left open by design: it is an empirical question that must be answered per deployment via measurement and A/B testing, using deployment profiles and the ranking-environment tools in §4.9.5.E (`ranking_env_*`, `config_profile_*`) so weight changes are explicit and attributable — and no fixed constant in this specification can settle it in advance. NFR-5 still requires that, *given* a fixed configuration, online admission remains deterministic. The same caveat applies to the default constants introduced in §4.5 (`η`, `λ`/half-life, `w_min`, hub threshold) — they are reasonable starting points, not values this document can certify as correct for every deployment.
- **NFR-2 vs live extractor latency.** Time-to-queryable (NFR-2) is measured from ingest completion to leaf readability with maintenance decoupled (§8). Live LLM/extract latency is a separate metric. Deployments MUST NOT conflate slow extraction with a failed NFR-2 leaf-publish path.
- **Document-container (`doc_id`) parity deferred.** A Hindsight-style `document_id` names a document container with replace-on-re-retain, bulk-delete, and original-text-fetch semantics — behaviors this revision deliberately does not define, because migration rehearsal has not yet shown which of them Clio needs. `evidence_ref` preserves source identity only and MUST NOT be mistaken for that container contract. If migration rehearsal demonstrates container parity is required, a dedicated later phase SHALL research the provider document lifecycle and design a `doc_id` (or equivalent) contract including upsert, bulk operations, and chunk/original-text handling; that phase MUST NOT reuse `evidence_ref` as the container key without an explicit supersession design.
- **Context privacy and prompt-injection risk.** Source context may contain personal data or instruction-like text. It MUST be bounded, encrypted with content, treated as untrusted data by extractors and retrieval, redacted from ordinary telemetry, and excluded from automatic model injection unless an explicit budgeted policy permits it.
- **Context relevance and retrieval drift.** Adding context to lexical matching can improve source-aware recall but can also increase noise or alter ranking. Deployments SHOULD evaluate context-aware retrieval against context-free baselines and MUST keep the policy deterministic for identical inputs and configuration.
- **Retrieval temporal-anchor determinism.** A retrieval arm that resolves relative date/time expressions (for example "last week") MUST resolve them against an explicit caller-supplied anchor timestamp or an explicit absolute window; an implicit server clock MUST NOT be a hidden input, so the deterministic-policy rule above holds for identical inputs and configuration. An implementation MAY offer a documented wall-clock default only as an explicit opt-in that cannot silently alter results.
- **Evidence-reference collision and identity ambiguity.** An external document or item identifier reused by different providers can collide if it is not namespaced. Provider references SHOULD use a stable provider/kind namespace, and identity/idempotency behavior MUST be documented rather than inferred from display text.

---

## 10. Glossary

- **Admission** — the decision to write a candidate item into long-term memory.
- **Association edge (`assoc_edge`)** — weighted link between two memory item ids in graph/structure metadata (`assoc_kind` = `coactivation` \| `explicit`). Durable SQL table name is `assoc_edges` (plural). Not an SPO triple; not a memory domain/tier; hub distillation produces a write-path item, not an `assoc_kind` value (§4.5).
- **Association weight policy (`association_weight_policy`)** — saturating growth, lazy decay, prune, and hub distillation for co-activation edges (§4.5). Must not be named or stored as `update_rule`.
- **Belief object** — the §4.10 versioned proposition with append-only `confidence_history`; not a sixth §4.1 semantic category and not an episodic type tag.
- **Bi-temporal** — tracking both when a fact was true in the world (valid time) and when the system recorded/changed it (transaction time).
- **Completeness manifest** — export inventory stating version, counts, checksums, filters, `content_mode`, and whether the export is complete (§4.9.5.B).
- **Context** — optional, bounded, descriptive metadata about the setting or circumstances surrounding a memory item. It is not a category, epistemic kind, source type, source span, model instruction, or retrieval budget; `compose_context` is a separate bounded retrieval operation.
- **Dirty-path refresh** — recomputing only the ancestor chain affected by a change, not the whole index.
- **Effective configuration** — the resolved settings after defaults, files, environment, profile, and runtime overlays (§4.9.5.E).
- **Epistemic kind (`epistemic_kind`)** — item/triple/belief field `fact` \| `belief` (FR-14 / §4.11). Durable SQL column name is `epistemic_kind` (not `class`). Never used as the `update` tool's routing parameter.
- **Evidence reference (`evidence_ref`)** — provider-neutral stable provenance/source identity supplied by a caller. At the item level it populates `source_ref` per the `source_ref` precedence rule and MAY identify a turn, tool call, external memory item, or other source record; it is not the source-span haystack. Per-entry values inside belief confidence history identify individual evidence items. It confers no document-container semantics (see §9).
- **Export content mode** — `dsar_plaintext` (authorized readable export) or `ciphertext_backup` (opaque bodies, no DEKs) for §4.9.5.B bundles.
- **Gist** — a lossy, prose summary retained for narrative continuity, never authoritative for exact values. Distinct from the episodic type tag value `gist`, which names a kind of episodic record rather than the PR-4 prose half.
- **Hygiene audit** — read-only ranking of noise candidates by score; paired with confirmed `hygiene_clean` and a durable cleanup log (§4.9.5.A).
- **Intent gate** — a per-turn classifier deciding whether memory retrieval is needed at all.
- **Invalidation** — closing a discrete fact's `valid_time` and `transaction_time` on supersession/retract, without deleting the row (PR-6, §4.6).
- **Operations removal** — logged `discard`, co-activation pruning, or hygiene that removes an item or edge from active use; not supersession and not compliance erasure (§7.4).
- **Persona document (`persona_document`)** — bounded always-on companion object (`stable` + `preferences`) under its own token budget (§4.7); distinct from semantic category value `persona` on `store`.
- **Profile** — a named bundle of effective settings (ranking, budgets, bank defaults, sync remotes) applied via `config_profile_apply`.
- **Provider (ingest)** — an external memory system source for `import_provider` (`hindsight` | `mem0` | `mnemosyne` | `honcho` | `supermemory`); distinct from `embed.provider` / `rerank.provider` / `extract.provider`, which select LLM-side adapters. The tool name `import_provider` stays for compat; its `provider` argument names a memory system, not a chat vendor.
- **Retention profile (`retention_profile`)** — a per-bank policy object (`verbosity`, bounded per-category `theta_offsets`, `duplicate_tolerance_write`, `duplicate_tolerance_read`, `recall_scope_default`, version) resolved bank override → deployment default → builtin default, read and written via `retention_profile_get` / `retention_profile_set`. `recall_scope_default` and `duplicate_tolerance_read` are honored at retrieval time: the first sets the default `recall_scope` for a bank, the second drives the page-local read-time duplicate cap with its own thresholds, independent of `duplicate_tolerance_write`. Distinct from the named deployment **Profile** above and from `ranking_env` weights; it tunes admission strictness and read-time scope only and never deletes, invalidates, or shreds anything (PR-6). The write-side novelty floor is part of §4.2 admission and applies to every gated long-term write surface in the §4.9.3 matrix; under a non-zero floor an identical re-write of an upsert-shaped write (`canonical_put`, `triple_add`, `task_upsert`) is rejected at the duplicate gate while a changed value is admitted.
- **Scratchpad** — ephemeral, size-bounded agent workspace that MUST NOT be treated as long-term memory (§4.9).
- **Shared surface** — a cross-agent memory bank for compact, gated conventions and corrections (§4.9).
- **Snapshot** — a lossless, schema-typed structured extraction of a memory unit.
- **Source text (`source_text`)** — inline evidence string supplied with a snapshot-bearing `store` / extract call; the FR-4 span verifier searches this haystack. Distinct from descriptive `context` and provenance ids.
- **Source ref (`source_ref`)** — durable provenance id on a memory item (e.g. turn id or namespaced external source/item id). The `store` tool's `evidence_ref` populates `source_ref` when `source_ref` is otherwise unset; when both are supplied they MUST agree or the write is rejected; provider import sets `source_ref` directly and the accompanying `evidence_ref` MUST equal it. Neither field is the span haystack.
- **Span verification** — cheap online check that extractive snapshot entities/numbers/dates are locatable source spans (FR-4 / §4.4); distinct from ops `verify` and peer `validate`.
- **Sync protocol** — client/server incremental exchange of durable memory mutations (§4.9.5.D), including `assoc_edge` graph-metadata mutations when multi-host sync is claimed; trusted peer-admitted creates MUST NOT be rejected solely by local admission θ.
- **Tool catalog** — the normative set of agent-callable memory operations defined in §4.9.
- **Tool schema (`tool_schema`)** — machine-readable MCP/JSON Schema for a catalog tool; not semantic category `schema`.
- **Update rule (`update_rule`)** — attribute-schema / `update` parameter `discrete` \| `continuous` (FR-11 / §4.6). Routes invalidation vs EMA. MUST NOT be stored in the `epistemic_kind` column and MUST NOT name co-activation weight mechanics.

---

## 11. References

- Shinn, N. et al. *Reflexion: Language Agents with Verbal Reinforcement Learning.* arXiv:2303.11366.
- Chhikara, P. et al. *Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory.* arXiv:2504.19413.
- Rasmussen, P. et al. *Zep: A Temporal Knowledge Graph Architecture for Agent Memory.* arXiv:2501.13956.
- Graphiti / Zep documentation on bi-temporal modeling and fact invalidation. getzep.com.
- *MemForest: An Efficient Agent Memory System with Hierarchical Temporal Indexing* (introduces MemTree). arXiv:2605.23986.
- *HeLa-Mem: Hebbian Learning and Associative Memory for LLM Agents.* arXiv:2604.16839 / ACL 2026.

---

*End of document.*