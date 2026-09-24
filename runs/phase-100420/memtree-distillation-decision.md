# MemTree ancestor distillation decision (G-09)

Decision: **documented exception — ancestor summaries remain deterministic
template aggregates. No real model-backed distillation ships in this phase.**

## Why this decision

1. What is missing: ancestor `summary_gist` values are produced by
   `MemTreeMaint::summarize_children` (`crates/clio-write/src/memtree_maint.rs`)
   as `aggregate[N]: gist | gist | ...` — a deterministic fold of child gists,
   not a synthesized, abstracted summary. Long-session "what have I tried"
   answers over ancestor summaries are therefore thinner than the §4.3
   MemTree description promises.
2. Why it is not implemented here:
   - Real distillation requires model-backed summarization inside the refresh
     engine. `MemTreeMaint` is an in-process, non-blocking maintenance hook
     (PR-9 / FR-3): summaries are computed between brief lock holds on worker
     threads with no network dependency. Adding extractor-sidecar calls would
     put model latency on the structural-maintenance path and change the
     leaf-first latency contract that phases 100060/100070 establish.
   - The existing "distill machinery" in-repo (`hub_distill` /
     `hub_distill_model::build_distill_item`) is itself template-derived
     (`"hub_distill: {hub} related to {a | b | c}"` + admission gating). It is
     consolidation, not abstraction; folding it into ancestor refresh would
     produce another template, not a real distillation, and would misrepresent
     the result as "real".
3. Debt ownership: **unowned.** No scheduled phase covers model-backed
   ancestor distillation (checked phases 100400, 100440, 100460, 100480,
   100520). Giving it an owner requires a roadmap addition (operator decision);
   this note records the shortfall so it cannot be silently accepted.

## Workaround that exists today

- Leaves remain immediately queryable through the leaf index; retrieval answers
  come from leaf gists and items, not from ancestor summaries.
- Related content is consolidated into admitted semantic items by `hub_distill`
  under the admission gate, which is the durable, gated path for aggregated
  knowledge.
- Ancestor summaries remain non-authoritative: the MemTree contract keeps
  snapshots/gists authoritative at the leaf (phase-100070 contract).

## What would discharge the debt

A reviewed roadmap phase that adds async model-backed summarization to the
refresh engine with a bounded queue, plus the §4.3 "what have I tried"
synthesis test from the phase-100420 test table (T100420-09), and updates to
`CONTEXT.md`/glossary describing the summary authority model.