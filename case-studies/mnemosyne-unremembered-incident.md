# Case Study: The Unremembered Incident
## Design Lessons for a Memory Provider — When Capture Exists but Salience Doesn't

*Based on diagnostic research into Mnemosyne (as a Hermes Agent memory provider) and a real-world incident where a rule violation with a $7.1K P&L consequence was never durably remembered across sessions.*

---

## 1. Executive Summary

A production incident occurred: an agent violated a governance rule, realized a +$7.1K P&L swing from the violation, and the user chose to embrace the outcome. The correct procedural fix was applied within hours. Yet **no memory of the incident survived in a form the agent could recall in a future session** — despite the memory system having captured the conversation, having a purpose-built temporal knowledge graph, having fact-extraction machinery, and having a consolidation pipeline.

The failure was not a missing capability. It was a missing **salience policy**: nothing in the stack — provider, harness, model, or skill guidance — was responsible for recognizing that *something notable happened* and ensuring it was written at retrievable weight. Three high-quality components each did their defined job; the gap lived between them.

**Core lesson for your provider:** *Automatic capture without automatic salience assessment produces an archive, not a memory.* This document decomposes the failure and specifies concrete mechanisms to prevent it.

---

## 2. The Incident Timeline

| Phase | What happened | What memory did |
|---|---|---|
| 1. Violation | Agent performs a re-entry action that breaks a stated rule | Turn content auto-captured at importance 0.5, veracity `tool` |
| 2. Discovery | User identifies the violation; agent acknowledges | Captured as another flat turn echo |
| 3. Remediation | Playbook patched with a new gate (v1.0.2) within hours | Procedural fix landed in the *correct* artifact (playbook), not memory |
| 4. Aftermath | User decides to embrace the outcome | Nothing written — "too episodic for a skill, not a stable preference" |
| 5. Next session | — | Incident effectively unrecoverable without manual transcript archaeology |

The procedural knowledge survived (in the playbook). The **episodic-but-instructive** knowledge — *what happened, why, what it cost, what was chosen* — did not. This category is the blind spot: it's neither a rule nor a fact nor a preference, and no layer claimed ownership of it.

---

## 3. Architecture Under Study (What Mnemosyne Does Well)

Before the failure analysis, credit where the design is sound — these are features worth copying:

- **Hybrid recall**: vector + FTS5 + importance, per-query tunable weights (default 50/30/20).
- **Tiered memory**: working → episodic via consolidation (`sleep`), with age-based degradation instead of deletion.
- **Veracity signal**: every memory carries a trust level (`stated` 1.0×, `inferred` 0.7×, `tool` 0.5×) that multiplies retrieval score — contamination control.
- **Temporal knowledge graph**: SPO triples with `valid_from`/`valid_until` — exactly the right shape for incident lifecycles.
- **Structured extraction layer**: facts, timelines, KG triples, instructions, preferences auto-populated during writes (when enabled).
- **Fail-soft philosophy**: memory failures never block the agent.
- **Lifecycle hooks**: `pre_llm_call`, `on_session_start`, `post_tool_call` — extension points exist.

The architecture has every *drawer* needed. The failure is that no drawer opens automatically when an incident walks in.

---

## 4. Root Cause Analysis: Six Compounding Gaps

### Gap 1 — Capture ≠ Salience
Post-turn sync auto-captures every turn verbatim at a flat importance default (0.5). The incident *is* in the database — indistinguishable, at write time, from small talk. **Automatic capture answers "what was said," never "what mattered."**

### Gap 2 — Importance is a write-time parameter with no writer
Salience judgment is delegated to the agent via an optional `importance` parameter. But agents assign salience *mid-task*, when attention is consumed by remediation. The system optimizes for the moment of least availability. Result: **salience debt** — everything is equal weight until someone manually promotes it, and nobody does.

### Gap 3 — Retrieval weights compound write-time neglect
A captured incident echo enters retrieval with three handicaps stacked: importance 0.5 (weight ×0.2 in scoring), veracity `tool` (×0.5 multiplier), and recency decay. Effective competitive weight ≈ 0.05 against a casual stated user preference at ~0.8. **Even captured incidents are structurally buried at recall time.** Write-time neglect is multiplied, not corrected, by the read path.

### Gap 4 — Reflection is dormant by default
The consolidation pipeline (the only place old memories get reprocessed) runs on `auto_sleep_enabled = false` in the Hermes integration — contradicting the core library's documented default of `true`. Fact extraction requires explicit `extract=True` per write. Fact-recall merging is off. **The system has a reflection organ, but it's switched off at install.**

### Gap 5 — No incident type exists
The schema has scopes, veracity levels, expirations, entities — but no first-class **event/incident/lesson** type with lifecycle states. Incidents must masquerade as generic memories, so nothing can query "show me open incidents" or "have we violated this rule before?"

### Gap 6 — Guidance is a routing skill, not a salience policy
The installed skill (`mnemosyne-memory-override`) only tells the agent *which tool to prefer*, not *when writing is obligatory*. Neither the harness system prompt nor model defaults carry a policy like "on error, correction, or rule violation: write a lesson at importance ≥0.8." **The guidance layer — the cheapest fix of all — was simply never authored.**

---

## 5. Transferable Design Principles

These generalize beyond Mnemosyne to any memory provider:

1. **P1 — Every automatic write path must carry an automatic salience estimate.** If you capture without assessing, you are building a log, not a memory.
2. **P2 — Salience assigned at write time will be under-assigned.** Never rely solely on the in-the-moment judgment of a busy agent (or its model). Provide a machine backstop.
3. **P3 — Write for the future query, not the present moment.** The retrieval question will be *"what happened with X?"* or *"have we seen this failure?"* — writes should be shaped and weighted to answer those.
4. **P4 — Reflection must be scheduled, not optional.** A consolidation/review pass that only runs when someone remembers to invoke it never runs.
5. **P5 — Guidance is a system layer, not documentation.** Escalation policies belong in skills/prompts (soft) *and* hooks (hard), because skills alone lose to task pressure.
6. **P6 — Fail-soft must not mean fail-silent.** Never blocking the user is right; quietly dropping the lesson is the failure mode to design against.

---

## 6. Design Recommendations for Your Provider

### 6.1 Capture Layer — dual-path writes
Every turn produces two records:

- **Verbatim echo** (as today): full interaction, importance 0.5, retention via consolidation.
- **Salience-flagged candidate** when a cheap detector fires (see 6.2): written as a typed, high-importance memory.

### 6.2 Salience Engine — detect, don't ask
A deterministic, zero-LLM scorer over tool results and turn content:

| Signal | Examples | Min salience bump |
|---|---|---|
| Tool failure | non-zero exit, exception classes, error payloads | +0.3 |
| Correction language | "no, that's wrong", "don't do that again", user overrule | +0.4 |
| Rule/policy reference | violation, gate, compliance terms from governing docs | +0.4 |
| Quantified impact | currency amounts, percentages, "broke", "failed for N users" | +0.3 |
| Repetition | same failure signature seen before | +0.3 (and auto-link to prior) |

Composite score ≥ threshold → write an **incident candidate** (importance 0.85–0.95, veracity `tool`). Deduplicate by signature. Non-blocking, best-effort — fail-soft preserved.

### 6.3 Typed Incidents with Lifecycle
First-class record, not a generic memory:

```
type: incident
state: open → remediated → lesson_extracted
trigger, impact, resolution, superseded_by
valid_from / valid_until          # temporal semantics
linked_memories[]                  # the echoes, the fix, the rule
```

Enables the queries generic memories can't answer: open incidents, recurrence detection, "what did we learn from this class of failure?"

### 6.4 Retrieval-Aware Write Shaping
When an incident closes, the *lesson* (not the raw event) is written at importance ≥0.9, veracity `stated`, with extraction enabled — so it wins the 50/30/20 scoring fight and passes veracity filters. Rule of thumb: **raw events are archived; distilled lessons are promoted.**

### 6.5 Scheduled Reflection Pass
Consolidation runs on a timer/threshold *by default*. Its prompt includes one additional instruction beyond summarization: *"Flag summaries containing errors, corrections, unresolved problems, or rule violations; emit a lesson record or an incident triple for each."* This catches anything the write-time detector missed. One LLM pass per consolidation cycle is an acceptable cost; make it optional for offline deployments.

### 6.6 The Guidance Layer (your skill)
Ship a behavioral skill with an explicit escalation policy:

- On any rule violation, user correction, or unexpected failure → **before ending the turn**, write: incident record (or lesson if closed) + temporal triple (`rule X violated at T, superseded by fix Y`) + task-tracker entry if unresolved.
- On session start with open incidents → surface them unprompted.
- On recurrence of a known failure signature → recall prior fix *before* acting.

Skill = the teaching layer; the 6.2 detector = the enforcement layer. Neither substitutes for the other.

### 6.7 Observability
Expose capture-quality metrics: incident candidates per session, lesson extraction rate, recall hit-rate on injected test incidents. You cannot fix what you don't measure — this is how Mnemosyne's gap stayed invisible.

---

## 7. Anti-Patterns to Avoid (Each Observed Here)

| Anti-pattern | Consequence |
|---|---|
| Importance as purely optional write parameter | Flat salience; archive-not-memory |
| `tool`-veracity memories heavily discounted *and* auto-generated | System burying its own observations |
| Powerful reflection features defaulting to off | Dead capability; silent gap |
| One generic memory type for everything | No incident queries, no lifecycle, no recurrence detection |
| Skill that only routes tools | Guidance without obligation |
| Fail-soft swallowing salience decisions | Lessons dropped without a trace |

---

## 8. Validation Plan

Adopt Mnemosyne's own README test and harden it:

1. **Base test (theirs):** "Investigate the failing payment-sync test and fix it" → new session: "A similar failure appeared; check prior fixes first." Must recall the fix.
2. **Rule-violation test (ours):** Agent violates a stated rule; user corrects; agent remediates. New session: *"Why can't we do X anymore?"* — must surface the incident, its impact, and the rule, without the user supplying keywords.
3. **Burial test:** After 100 turns of unrelated chatter, the incident memory must still surface above casual preferences on a targeted query. (This is the test Mnemosyne fails today — incident at effective weight ~0.05 loses.)
4. **Detector precision test:** Run a benign session; incident-candidate false-positive rate should be near zero, or users will distrust the salience engine.

---

## 9. Summary

Mnemosyne failed this incident not through any broken component but through an unowned responsibility: **nobody's job was to notice that something mattered.** Your provider's differentiating design decision should be exactly that — make salience assessment a first-class, automatic stage of the write path, back it with typed incident lifecycles and scheduled reflection, and encode the escalation policy in both guidance (soft) and hooks (hard). Capture is table stakes; *remembering what mattered* is the product.