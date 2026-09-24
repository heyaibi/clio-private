# Phase 100421: TEI Rerank Wire-Contract Correction and Retrieval Diagnostics (issue #3)

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | [TBD] | [TBD] |
| Adversary | r1 | [TBD] | [TBD] |
| Remediator | r1 | [TBD] | [TBD] |
| Remedy Approver | r1 | [TBD] | [TBD] |
| Finalize | r1 | [TBD] | [TBD] |

**Operator-finding phase 100421 · Effort: ~1–2 days · Source: GitHub issue #3 (`heyaibi/clio`) · Slot: after the in-progress Phase 100420**

## 1. Objective

### Goal
Make the configured TEI reranker actually run. The reranker is now attached to the live retriever (Phase 100350), but its request and response do not match the TEI `/rerank` contract, so every rerank attempt fails and retrieval silently falls back to fused (RRF) order. This phase corrects the TEI wire contract and fixes the shared transport error label that reported the failure as an embed failure. It also locks the two recall-path fixes already landed from the same investigation with regression coverage.

### Expected Outcome
- A configured TEI sidecar (`rerank.provider = "tei"`, `rerank.url` set) receives `POST {url}/rerank` with `{"query","texts"}`, returns a bare `[{"index","score"}, ...]` array, and the retriever applies that order.
- A live `clio recall` no longer prints `rerank unavailable, using fused order: ... embed endpoint returned HTTP 422 ...` when the TEI sidecar is healthy.
- A rerank transport/HTTP failure is reported as a rerank (or neutral endpoint) failure, never as an embed failure; hosted-extraction transport failures are likewise not reported as embed failures.
- The `results[]`/`scores[]` response shapes keep working, so no other rerank sidecar is broken.
- The recall path skips an unreadable candidate (missing or crypto-shredded DEK) with a warning instead of aborting, and text `recall` shows hit content; both behaviors are covered by regression tests.
- The four findings filed in issue #3 are closed or explicitly documented as already landed with evidence.

### Parent Requirement
`requirement.md` — §4.5 step 3 (adaptive retrieval: dense + lexical + graph, then reranking), FR-32 / §4.9.5.E (provider selection and effective configuration), FR-26 / PR-4 (no silent corruption of exact-value reads), PR-7 (retrieval is inspectable). Source: GitHub issue #3.

### Design References (validated at plan time)
- **TEI `/rerank` request** (verified from Hugging Face `text-embeddings-inference`, `router/src/http/types.rs::RerankRequest`): `{"query": String, "texts": [String], ...}`. There is no `documents` field and no `top_k` field. A request carrying `documents` instead of `texts` returns HTTP 422 `missing field \`texts\``.
- **TEI `/rerank` response** (`router/src/http/types.rs::RerankResponse` + `router/src/http/server.rs::rerank`): a bare JSON array `[{"index":<usize>,"score":<f32>}, ...]`, reverse-sorted by score (best-first). `text` is omitted unless `return_text` is set.
- **Current defect (request).** `crates/clio-retrieve/src/rerank.rs:105-124` (`HttpReranker::rerank`) posts `{"query","documents","top_k":N}`.
- **Current defect (response).** `crates/clio-retrieve/src/rerank.rs:280-334` (`parse_rerank_response`) accepts only `{"results":[{"index":...}]}` or `{"scores":[...]}`; a bare array falls to the final `else` and errors `rerank response must contain results[] or scores[]`.
- **Wrong contract baked into tests.** `crates/clio-retrieve/src/rerank_tests.rs:264-276` (`factory_selects_teiranker_by_provider`) asserts `"top_k":3` in the captured request and feeds a Cohere-shaped `{"results":[...]}` body, so the mismatch was never caught.
- **The failure is live.** `crates/clio-mcp/src/runtime_open.rs:137-149` builds the reranker from effective config and calls `HybridRetriever::set_reranker`; `crates/clio-retrieve/src/hybrid_rank.rs:84-127` (`apply_rerank`) calls it and, on error, pushes `rerank unavailable, using fused order: <error>` and keeps the fused order.
- **Transport mislabel.** `crates/clio-index/src/http.rs` hardcodes `embed endpoint` in the status branch of `transport_error` (line 157), in `get_ok` (line 252), and in `parse_response_json` (lines 265, 271, 277); URL validation also says `embed sidecar url` (lines 67, 80, 87, 95, 102, 111, 124). `post_json` is the shared transport used by embed (`crates/clio-index/src/embed.rs:151`), rerank (`crates/clio-retrieve/src/rerank.rs:121,206`), and hosted extraction (`crates/clio-write/src/extract.rs:205`), so rerank and extraction failures are both mislabeled.
- **Contradiction with Phase 100300.** `phase-100300-rerank-providers.md` §1/§2/§5 states the TEI contract is `{"query","documents","top_k"}` and `results[]`/`scores[]` and lists it under "Must Not Change". That statement is factually wrong about TEI. This phase corrects the adapter and the recorded contract; it does not change the `Reranker` trait or the fail-open policy. The correction is recorded as a defect fix, not a new design decision.
- **Already-landed recall fixes.** `crates/clio-retrieve/src/hybrid.rs:382-415` (`fetch_items`) already skips `ErrorCode::Forbidden`/`ErasedSubject` with a `skipped unreadable item` warning; `crates/clio-lib/src/cli_read_render.rs:36-75` already renders hit content via `recall_content`. Bug 4 has coverage (`crates/clio-lib/src/cli_read_tests.rs:126-154`, `recall_tty_text_and_explicit_output_override` asserts `terse answers`); bug 3 has no dedicated test.

---

## 2. Scope Boundaries

### In Scope
- Correcting the TEI `/rerank` request body to `{"query","texts"}` and dropping `documents`/`top_k` from that request.
- Teaching `parse_rerank_response` to accept the TEI bare array while preserving the existing `results[]` and `scores[]` shapes.
- Updating the TEI adapter tests that encoded the wrong contract, and adding request-capture coverage for the `texts` shape.
- Removing the hardcoded `embed` label from the shared transport error messages (or threading a caller-scoped label) so rerank and extraction failures are not reported as embed failures, without changing retry classification.
- Adding a regression test proving `recall` skips an unreadable candidate with a warning instead of aborting (bug 3).
- Verifying, with existing and any added tests, that text `recall` includes hit content (bug 4).

### Explicitly Out of Scope
- **Observation 1 — score honesty.** Surfacing the rerank relevance (0-1) when rerank runs and showing no numeric score otherwise. The `Reranker` trait returns only a permutation (`Vec<usize>`); surfacing a rerank score requires changing that trait (forbidden by Phase 100300's "Must Not Change") and extending the retrieval response and text/JSON renderers. It is a separate design decision with its own contract, so it is deferred (see §12).
- **Observation 2 — duplicate-content collapse.** Collapsing near-identical content shown once per item in `recall` output. This is a display/dedup policy choice; the read-time duplicate cap already exists under `duplicate_tolerance_read` (Phase 100250/100270), so this is a presentation follow-up, not this defect.
- Relaxing the `rerank.model` requirement for `rerank.provider = "tei"`. TEI does not receive a model field, but the current factory requires `rerank.model` when `rerank.url` is set. Changing that validation is a separate config-contract decision.
- Re-wiring the reranker to the live path (already delivered by Phase 100350).
- The Cohere-compatible adapter, fusion weights, candidate-count policy, or any embed-path behavior.
- Provider adapters beyond TEI/Cohere (Phase 100500).

### Must Not Change
- The `Reranker` trait signature (`crates/clio-retrieve/src/rerank.rs:47-58`).
- The fail-open policy: a rerank error keeps the fused order and never drops candidates (`hybrid_rank.rs:119-125`).
- The `results[]` and `scores[]` parsing semantics and the full-permutation guarantee (out-of-range and duplicate indices fail closed).
- Retry classification substrings in `clio-index/src/embed.rs:191-199` (`connect failed`, `sidecar unreachable`, `read timed out`, `read deadline exceeded`, `HTTP 429`, `HTTP 5`).
- The 401/403 body-suppression rule in `parse_response_json` (credentials echoed by an endpoint must never enter `AmError` text).
- Existing MCP tool names, schemas, and the pack format revision.
- Secret masking and effective-config precedence.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100300 landed (TEI and Cohere adapters plus the reranker factory) and Phase 100350 landed (reranker attached to the live retriever).
- Phase 100280 transport (`post_json`/`get_ok` over the TLS-capable client) is in place.
- A TEI rerank sidecar can be brought up for reproduction (the compose profile referenced by the issue).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| TEI `/rerank` server | Reachable for repro at `rerank.url` | `curl -s "$RERANK_URL/rerank" -H 'Content-Type: application/json' -d '{"query":"q","texts":["a","b"]}'` returns a 200 bare array |
| `HttpReranker` / `parse_rerank_response` | Present and wired | `crates/clio-retrieve/src/rerank.rs` |
| Live reranker attachment | `set_reranker` called at runtime | `crates/clio-mcp/src/runtime_open.rs:137-149` |
| Shared transport | `post_json`/`get_ok` in `clio-index` | `crates/clio-index/src/http.rs` |
| Recall candidate fetch | Skip-on-unreadable branch present | `crates/clio-retrieve/src/hybrid.rs:393-403` |
| Firewall/egress | Loopback sidecar reachable; no new egress when unconfigured | Manual/CI environment |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Reproduce the report end to end before editing: build and run the real CLI, bring up the TEI rerank sidecar, run `clio recall "<query>"`, and save the before output showing the warning and fused-only order. Per `AGENTS.md` "Reproduce Before You Fix", a unit test alone is not proof.
- Confirm the exact capture/parse code paths and line numbers in `rerank.rs` and `rerank_tests.rs`.
- Confirm which call sites use the shared `post_json`/`get_ok` (embed, rerank, extraction) and which hardcoded `embed` strings surface in each caller's errors.
- Confirm retry classification (`is_retryable`) and every test that asserts transport error text, so the label change does not silently break retry behavior.
- Confirm the `fetch_items` skip branch and whether a dedicated regression test exists (it does not, per discovery).
- Confirm `cli_read_render::recall_content` and the test that asserts content appears in text output.
- Confirm `http.rs` total size against the 450-line limit before editing.

### Discovery Output
- **Request/response mismatch is the primary cause.** As recorded in §1 Design References; the TEI request expects `texts`, and the response is a bare array.
- **The reranker is live.** `runtime_open.rs` builds and attaches it, so the mismatch disables rerank in the running server rather than only in tests.
- **Test-blind-spot.** `factory_selects_teiranker_by_provider` asserts the wrong request field and feeds the wrong response shape; `live_sidecar_reorders` also uses the non-TEI `results[]` body.
- **The mislabel is generic-transport-wide.** `post_json` is shared, so the fix must not be rerank-specific; hosted extraction (`clio-write/src/extract.rs:205`) is affected too.
- **Retry classification is substring-based**; a neutral label preserves it if the retryable substrings are untouched.
- **Bug 3 has no dedicated regression test**; bug 4 does. Both code fixes are already present in the working tree.
- **`crates/clio-index/src/http.rs` is 403 lines** at plan time, close to the 450-line source limit; the implementer must keep any change within budget or decompose.
- **Assumptions confirmed:** the live path benefits from the fix; the fail-open contract remains.
- **Assumptions contradicted:** Phase 100300's stated TEI contract is wrong; it is corrected here and the phase file records that correction.
- **Questions requiring clarification:** none blocking. Observation 1 is deferred (see §2/§12) rather than guessed.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths or module names unless they are an externally required contract. The TEI wire shapes above are an external contract and are normative for this phase.

---

## 5. Implementation Specification

### Task 1: Correct the TEI Rerank Wire Contract

#### Intent
Make the TEI adapter speak the sidecar's real request and response contract so rerank actually runs.

#### Required Capability or Behavior
- `HttpReranker::rerank` posts `{"query": <query>, "texts": <documents>}` to `{url}/rerank`; it no longer sends `documents` or `top_k`.
- `parse_rerank_response` accepts the TEI bare array `[{"index":i,"score":s}, ...]` as a best-first order, and still accepts `{"results":[{"index":...}]}` and `{"scores":[...]}`.
- The result remains a full permutation of `0..documents.len()`: omitted documents append in original order; out-of-range or duplicate indices fail closed.
- An empty document list short-circuits without a request.

#### Architectural Responsibility
`clio-retrieve` owns the adapter and the parser. The `Reranker` trait and the fail-open orchestrator are unchanged.

#### Required Changes
1. Change the TEI request body to the `{"query","texts"}` shape; keep the `top_k` trait parameter (trait signature frozen) but do not send it in the TEI body.
2. Extend `parse_rerank_response` with a bare-array branch, evaluated before the object-key branches, that reads `index` from each element and trusts array order (matching the sidecar's best-first sort).
3. Keep the existing `results[]`/`scores[]` branches and their fail-closed index checks.
4. Update `factory_selects_teiranker_by_provider` (and any test that assumes the old TEI body) to capture and assert the `texts` shape and to feed a bare-array response. Add a dedicated bare-array parse test.

#### Implementation Constraints
- Do not change the `Reranker` trait, the fail-open policy, or the full-permutation contract.
- Do not add dependencies; reuse the Phase 100280 transport.
- Keep the request body minimal (no new fields such as `truncate`/`raw_scores` unless required); no new egress beyond the configured sidecar.
- Keep every touched file at or below 450 lines.

#### Expected Result
Against a TEI sidecar, capture shows `POST /rerank` with `{"query":..., "texts":[...]}`; the bare array yields a best-first full permutation; a configured sidecar reranks live retrieval.

### Task 2: Scope Shared Transport Error Labels to the Failing Stage

#### Intent
Stop reporting rerank (and extraction) transport failures as embed failures.

#### Required Capability or Behavior
- A rerank HTTP/transport failure message contains no `embed` substring.
- A hosted-extraction transport failure message contains no `embed` substring.
- Retry classification is unchanged: 429/5xx and connect/timeout conditions still classify retryable; TLS/BadUri/Protocol still do not.
- The 401/403 body-suppression rule is preserved (no response body in the error).
- No credential or key material appears in any error text.

#### Architectural Responsibility
`clio-index` owns the shared transport text. Callers (`clio-retrieve` rerank, `clio-write` extraction, `clio-index` embed) own any stage-specific prefix they add at their own boundary.

#### Required Changes
1. Replace the hardcoded `embed endpoint`/`embed sidecar url`/`embed response ...` labels in `crates/clio-index/src/http.rs` with neutral endpoint wording, or thread a caller-supplied label through `post_json`/`get_ok`. If a label parameter is added, update every call site (embed, rerank, extraction, and tests).
2. Preserve the retryable substrings exactly (`connect failed`, `sidecar unreachable`, `read timed out`, `HTTP 429`, `HTTP 5`, etc.).
3. Optionally add a stage prefix at the reranker boundary (for example `rerank: ...`) so the failure names its stage; keep it substring-preserving.
4. Update any test that asserts the old label text.

#### Implementation Constraints
- Do not weaken retry classification or the 401/403 suppression.
- Do not leak response bodies, keys, or document text into errors.
- Keep `http.rs` at or below 450 lines; decompose if the change would exceed it.
- No new dependency.

#### Expected Result
A rerank 422 reads as a rerank/neutral endpoint failure; extraction transport errors read as extraction/neutral failures; retry behavior is provably unchanged.

### Task 3: Lock the Recall-Path Fixes with Regression Coverage

#### Intent
Turn the two already-landed recall-path fixes into guarded behavior with tests, and verify they are intact.

#### Required Capability or Behavior
- With one candidate whose content is unreadable (`Forbidden` or `ErasedSubject`), `recall`/`retrieve` returns the readable candidates and a warning naming the skipped item, instead of aborting the whole query; a direct `get` on that id still errors.
- Text-mode `recall` prints hit content (gist), not only `id`/`score`.
- Both behaviors hold at the real entry point (CLI/MCP), not only via a helper.

#### Architectural Responsibility
`clio-retrieve` owns candidate fetch and warning emission (`hybrid::fetch_items`); `clio-lib` owns text rendering (`cli_read_render`). This task adds tests and verifies behavior; it does not redesign either.

#### Required Changes
1. Add a regression test that seeds readable and unreadable candidates and asserts the readable set is returned with exactly one skip warning; assert the direct read still errors.
2. Confirm/extend text-output coverage that a hit's content appears in `recall` text mode.
3. Record that the production fixes are already present in the tree and identify their locations.

#### Implementation Constraints
- Do not change the skip policy or the renderer's contract except to add coverage.
- No new dependency; keep every touched file at or below 450 lines.

#### Expected Result
Regression tests fail if either fix is reverted; the current tree passes.

### Implementation Freedom
The agent may choose the transport-label mechanism (neutral wording vs. a label parameter vs. a caller prefix), the exact parser branch ordering, and test placement, provided the required behavior, boundaries, and contracts above hold and all acceptance criteria pass.

---

## 6. Agent Execution Rules

### Allowed Actions
- Reproduce the reported failure with the real binary and a TEI sidecar, then modify the TEI adapter, the parser, the shared transport messages, and tests.
- Add the recall-path regression tests.
- Perform local refactoring required to stay within the 450-line file limit.

### Forbidden Actions
- Change the `Reranker` trait signature, the fail-open policy, or the full-permutation contract.
- Change the `results[]`/`scores[]` parsing semantics or retry classification substrings.
- Weaken the 401/403 body suppression or leak secrets/document text into errors.
- Delete or bypass tests; disable security controls; add dependencies; commit secrets; claim completion without evidence.
- Expand scope into observation 1/2, the `rerank.model` validation, or provider adapters.

### Agent Decision Boundary
The agent may decide the label mechanism, parser branch order, and test organization. The agent must request approval for: changing the `Reranker` trait, changing the fail-open policy, adding a dependency, or any change to published MCP tool schemas. Correcting the TEI contract does **not** require approval because it is a factual defect correction, but the correction to Phase 100300's recorded contract must be documented in the completion evidence.

### Mandatory Stop Conditions
Stop and report if: the TEI sidecar cannot be reached for reproduction; the bare-array branch cannot be added without weakening the fail-closed index checks; the label change would alter retry classification; the recall skip branch is absent (meaning the branch was lost); or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- The rerank request continues to go only to the configured `rerank.url`; no new egress when rerank is unconfigured.
- Transport errors carry no key material, no response bodies for 401/403, and no full document text.
- Bounded timeouts and the response size cap are preserved.
- Recall warnings must not include decrypted content; they name the item id and the structured error only.

### Sensitive Data Rules
- Never log or return plaintext secrets, keys, or full document text.
- Reuse the existing transport and masking; do not hand-roll a second mechanism.

### Security Acceptance Conditions
- No key appears in any rerank/extraction error (test).
- 401/403 responses still omit the body snippet (test).
- The unreadable-candidate warning contains no content (inspection/test).

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (TEI body build, bare-array parse, compatibility parse, label text)
- [ ] Integration tests (request-capture through the real adapter; mock TEI rerank applies to a live retriever)
- [ ] Contract tests (`Reranker` trait unchanged; full permutation always returned; fail-open intact)
- [ ] End-to-end tests (real CLI `recall` against a TEI sidecar)
- [ ] Regression tests (existing `results[]`/`scores[]`; recall skip; recall content; workspace green)
- [ ] Security tests (no key in errors; 401/403 body suppression)
- [ ] Failure-mode tests (out-of-range/duplicate index; malformed body; dead sidecar keeps fused order; unknown provider fails closed)

### Required Test Scenarios
| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100421-01 | Capture the TEI request from `HttpReranker` | Body contains `"query"` and `"texts"`; no `"documents"`; no `"top_k"` |
| T100421-02 | TEI bare-array response `[{"index":1,...},{"index":0,...}]` | Order `[1,0,...]`; full permutation |
| T100421-03 | TEI bare array omits a document | Omitted document appended in original order |
| T100421-04 | TEI bare array with duplicate/out-of-range index | Fail-closed error; orchestrator keeps fused order |
| T100421-05 | Existing `results[]` and `scores[]` bodies | Parsed exactly as before (compat regression) |
| T100421-06 | Rerank HTTP failure (for example 422) | Error text contains no `embed`; may name rerank/neutral endpoint |
| T100421-07 | Hosted-extraction transport failure | Error text contains no `embed` |
| T100421-08 | 429/5xx and connect/timeout; TLS/BadUri/Protocol | Retryable unchanged; non-retryable unchanged |
| T100421-09 | Recall with one unreadable candidate | Readable hits returned; one skip warning; no abort |
| T100421-10 | Text-mode recall | Hit content appears in output |
| T100421-11 | No provider configured; unknown provider | No reranker / fail-closed config error; behavior unchanged |
| T100421-12 | Full workspace suite + coverage + clippy + fmt | Green; aggregate and per-file coverage ≥90% |

### Negative Testing
Verify that invalid TEI bodies fail closed and keep the fused order, duplicate/out-of-range indices never produce an invalid permutation, dead sidecars keep fused order, unreadable candidates are skipped without leaking content, and existing TEI/Cohere/embed behavior is intact.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence — including the before/after reproduction required by `AGENTS.md` "Reproduce Before You Fix".

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100421-01 | TEI request/response contract corrected; a configured sidecar reranks live retrieval | T100421-01…04; real CLI repro | Captured request body, bare-array parse test, before/after `clio recall` output showing rerank applied |
| AC-100421-02 | `results[]`/`scores[]` parsing and full-permutation guarantee preserved | T100421-05 | Existing tests green unchanged |
| AC-100421-03 | Rerank and extraction errors are not labeled embed | T100421-06, T100421-07 | Test output / error-text assertions |
| AC-100421-04 | Retry classification and 401/403 body suppression unchanged | T100421-08 | Test output |
| AC-100421-05 | Recall resilience and content fixes present and regression-tested | T100421-09, T100421-10 | New/updated test output; fix locations recorded |
| AC-100421-06 | No regression; size/coverage gates pass | T100421-11, T100421-12 | Workspace suite green; `make coverage` per-file ≥90%; files ≤450 lines; `clippy -D warnings`; `fmt --check` |

### Definition of Done
- [ ] All in-scope behavior is implemented.
- [ ] All acceptance criteria pass.
- [ ] Required tests pass (unit, integration, contract, end-to-end, regression, security, failure-mode).
- [ ] No unauthorized changes were introduced (no trait/fail-open/published-schema/retry changes; no dependency added).
- [ ] Existing behavior remains intact (`results[]`/`scores[]`, fail-open, embed path, extraction).
- [ ] Security checks pass (no key in errors; 401/403 suppression; no content in warnings).
- [ ] Documentation is updated where required (the TEI contract correction and any `crates.md` note).
- [ ] Evidence is collected (implementation summary, before/after repro, changed components, test output, coverage).
- [ ] Verification is completed and the required approval is obtained.

### Completion Evidence
- Implementation summary
- Before/after reproduction transcript (real CLI + TEI sidecar)
- Discovered/affected architectural components
- Changed-component summary (file sizes)
- Test execution output
- Coverage report (aggregate and per-file)
- Verification report
- Known limitations

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| TEI sidecar not reachable for repro | Manual/curl | Document that live repro was not possible; rely on capture-server tests and say so plainly |
| Bare-array branch weakens fail-closed checks | Test | Do not merge; keep the index validation on the shared path |
| Label change breaks retry classification | `is_retryable` tests | Revert to neutral wording that preserves substrings |
| A recall-path fix is absent (lost branch) | Discovery | Stop and report; re-landing it is in scope but the absence must be surfaced first |
| File approaches 450 lines | Size check | Decompose before exceeding the limit |

### Rollback Strategy
Revert the adapter/parser/label changes; the previous behavior (rerank failing open to fused order) remains safe because fail-open is unchanged. No data migration is involved.

### Partial Completion Policy
If only the contract fix or only the label fix lands, do not claim completion. Record each task separately, keep the tree green, and do not leave a state where a published contract is half-corrected.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| requirement §4.5 step 3 (rerank stage) | Task 1 | T100421-01…04 | AC-100421-01 |
| FR-32 / §4.9.5.E (provider selection) | Task 1 | T100421-01, T100421-11 | AC-100421-01 |
| Issue #3 finding 2 (mislabeled transport errors) | Task 2 | T100421-06…08 | AC-100421-03, AC-100421-04 |
| Issue #3 finding 3 (recall aborts on unreadable candidate) | Task 3 | T100421-09 | AC-100421-05 |
| Issue #3 finding 4 (recall text omitted content) | Task 3 | T100421-10 | AC-100421-05 |
| FR-26 / PR-4 (no silent corruption) | Tasks 1–3 | T100421-04, T100421-09 | AC-100421-01, AC-100421-05 |
| Phase 100300 recorded contract (corrected) | Task 1 | Inspection + evidence | AC-100421-01 |
| Regression / quality contract | All | T100421-12 | AC-100421-06 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- A TEI adapter whose request/response match the sidecar, with a bare-array parser branch and updated tests.
- A shared transport whose error labels no longer misattribute rerank/extraction failures to embed.
- Regression tests for the recall skip-on-unreadable and recall-content behaviors.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- A configured TEI reranker actually reorders the shortlist; the precision stage is live.
- Rerank and extraction failures are diagnosable and are never reported as embed failures.
- The recall path returns readable hits when some candidates are unreadable, with a warning.

### Known Limitations
- **Observation 1 (score honesty) is deferred.** Retrieval hits still expose the fused RRF `score`, not a calibrated rerank relevance. Surfacing rerank relevance would require extending the `Reranker` trait (returning scores, not only a permutation) and the retrieval response/renderers, which needs its own phase and approval. Until then, the text renderer keeps its existing "score is relative (rank fusion), not calibrated relevance" note.
- **Observation 2 (duplicate-content collapse) is deferred** as a display/policy follow-up; the read-time duplicate cap already exists.
- `rerank.model` is still required for `rerank.provider = "tei"` even though TEI does not receive it; relaxing that validation is a separate config-contract decision.
- `results[]`/`scores[]` compatibility is kept for non-TEI sidecars; no non-TEI adapter using `documents` is currently configured, but the parsing support remains.

### Downstream Prerequisites
- Observation 1, if pursued, needs a dedicated phase that changes the `Reranker` trait and the retrieval response contract; it should reference this phase's deferral.
- Any future TEI-contract change must update Phase 100300's recorded contract so the roadmap does not re-introduce the mismatch.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: [TBD]
- Verifier: [TBD]
- Human Approver: [TBD, if required]
- Date: [YYYY-MM-DD]
