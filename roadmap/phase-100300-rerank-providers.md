# Phase 100300: Rerank Provider Adapters (TEI and Cohere-Compatible)

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100300 · **Effort:** `1×` · **Scope:** rerank half of `gap/zero-deps.md`; split from the former single zero-dependency phase

### Vocabulary (read first) — zero shared moniker
| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`rerank.provider`** | `tei` \| `cohere` | Effective config | Share a wire format across providers |
| **reranker** | Type implementing `Reranker` | `clio-retrieve::rerank` | Be attached to the live retriever here (Phase 100350) |
| **permutation** | Expected `Reranker` output | `clio-retrieve` | Drop or duplicate a document index |
| **fail-open** | Orchestrator keeps the fused order on error | `clio-retrieve::hybrid` | Be reversed by an adapter |

---

## 1. Objective

### Goal
Produce reranked shortlists from either the existing local TEI sidecar or a Cohere-compatible hosted rerank API, selected by configuration, reusing the Phase 100280 transport. The adapters are built and tested here; attaching the configured reranker to the live retrieval path is Phase 100350.

### Expected Outcome
- `rerank.provider = "tei"` keeps `POST {url}/rerank` with `{"query","documents","top_k"}` and the existing `results[]`/`scores[]` parsing.
- `rerank.provider = "cohere"` sends `POST {url}/v1/rerank` with `{"query","documents","top_n","model"}` and parses `results[].index`.
- Both return a full permutation of document indices; omitted documents are appended in original order; out-of-range or duplicate indices fail closed.
- Unknown provider values fail closed; no provider configured means no reranker.
- Rerank remains precision-only and fail-open at the orchestrator.

### Parent Requirement
`requirement.md` — §4.9.5.E/FR-32 (config), P4/§4.5 (bounded rerank stage), FR-26 (no silent reordering corruption). Gap source: `gap/zero-deps.md` rerank portion.

### Design References (validated)
- **Cohere rerank** returns `{"results":[{"index":N,"relevance_score":R}]}` for `POST /v1/rerank` with `top_n` (`docs.cohere.com/reference/rerank`). Order is best-first; the adapter maps it to a full permutation.
- **TEI rerank** is the existing local contract (`POST /rerank`, `results[]` or `scores[]`), unchanged.
- The existing `parse_rerank_response` already treats rerank as fail-open precision (the orchestrator keeps fused order on error); the adapter must not weaken that.

---

## 2. Scope Boundaries

### In Scope
- Cohere-compatible rerank adapter selected by `rerank.provider`, on the Phase 100280 transport.
- A reranker factory resolving provider/url/model/bearer from effective config.
- Provider body normalization into the existing permutation parser where practical.

### Explicitly Out of Scope
- Attaching the reranker to the runtime `HybridRetriever` (Phase 100350).
- Rerank model quality, prompt/instruction tuning, or candidate-count policy.
- Embedding adapters (Phase 100290) and extraction (Phase 100340).
- Changing fusion, budgets, or the fail-open policy.

### Must Not Change
- TEI rerank wire shape; `Reranker` trait signature; `parse_rerank_response` semantics (full permutation, fail-closed on out-of-range/duplicate).
- Fail-open behavior: a rerank error never blocks compose and never drops candidates.
- Secret masking and config precedence.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100280 accepted: transport + `rerank.provider`/`rerank.url`/`rerank.model`/`credentials.rerank_api_key` config and env.
- Existing `HttpReranker` and `parse_rerank_response` intact.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Phase 100280 transport | `post_json` reachable | Import/build |
| Rerank config paths | Allowlisted and masked | `validate.rs` tests |
| `Reranker` + permutation parser | Stable | `clio-retrieve/src/rerank.rs` inspection |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Inspect `HttpReranker` and `parse_rerank_response` and confirm the fail-open caller.
- Confirm the Phase 100280 rerank config paths and bearer resolution.
- Identify the existing rerank tests and the mock-server harness.

### Discovery Output
- **One reranker exists.** `clio-retrieve/src/rerank.rs::HttpReranker` posts `{"query","documents","top_k"}` to `{url}/rerank` via `clio_index::post_json` and parses `results[].index` or `scores[]` into a full permutation; `parse_rerank_response` appends omitted documents in original order and rejects out-of-range/duplicate indices.
- **Fail-open caller.** `apply_rerank` in `clio-retrieve/src/hybrid_rank.rs` keeps the fused order on any error; `HybridRetriever` exposes `set_reranker`/`clear_reranker`, but `McpState::build` never calls it — that wiring is Phase 100350.
- **Config from Phase 100280.** `rerank.provider`, `rerank.url`, `rerank.model`, and `credentials.rerank_api_key` are allowlisted and env-wired there; this phase only consumes them.
- **`top_k` is clamped** to `documents.len()` before the request; the Cohere `top_n` must be the same clamped value.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, or module names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Cohere-Compatible Rerank Adapter

#### Intent
Translate the Cohere rerank wire format into the existing permutation contract.

#### Required Capability or Behavior
- `POST {url}/v1/rerank` with `{"query","documents","top_n":<clamped top_k>,"model":<rerank.model>}` and bearer auth when configured.
- Parse `results[].index` as the best-first order; reuse `parse_rerank_response` semantics so the result is always a full permutation with omitted documents appended.
- Reject out-of-range or duplicate indices; malformed bodies are errors.
- Empty document lists return an empty permutation without a request.

#### Architectural Responsibility
`clio-retrieve` owns the adapter; it reuses the Phase 100280 transport and the existing parser.

#### Required Changes
1. Add the Cohere adapter selected by `rerank.provider`.
2. Normalize the provider body into the parser (directly or via a thin shim).
3. Keep `HttpReranker` (TEI) unchanged.

#### Implementation Constraints
- No second HTTP client; bounded timeout preserved (`DEFAULT_RERANK_TIMEOUT` or configured).
- Errors surface to the fail-open orchestrator; the adapter does not swallow them into a wrong order.

#### Expected Result
A mocked Cohere response yields the same permutation as a TEI `results[]` response with equal scores.

### Task 2: Reranker Factory

#### Intent
Construct the configured reranker from effective config.

#### Required Capability or Behavior
- Resolve provider, url, model, and bearer; unknown provider or missing url/model fails closed.
- No provider configured → no reranker (`None`), matching current behavior.
- Bearer precedence: `credentials.rerank_api_key` else `credentials.api_key` else none.

#### Architectural Responsibility
`clio-retrieve` (or the runtime owner) provides the factory; Phase 100350 consumes it.

#### Required Changes
1. Add the config→`Option<Reranker>` factory.
2. Keep construction cost one-per-runtime.
3. Document the seam Phase 100350 calls.

#### Implementation Constraints
- No environment reads outside the config layer.
- No key in any error text.

#### Expected Result
With env vars set, the factory returns the configured adapter; with nothing set, it returns `None`.

### Task 3: Documentation

#### Intent
Document rerank provider selection and the deferral of live wiring.

#### Required Capability or Behavior
- README/`.env.example` document `rerank.provider`, `rerank.url`, `rerank.model`, `rerank.api_key`, with correct model examples (a reranker model, not an embedding model).
- State that attaching the reranker to the live path is Phase 100350.

### Implementation Freedom
The agent may choose concrete structure, naming, and internal design provided the required behavior is satisfied, boundaries respected, contracts preserved, all acceptance criteria pass, and no prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the Cohere adapter and factory; update docs and tests.

### Forbidden Actions
- Attach the reranker to the live retriever (Phase 100350); change fusion/fail-open semantics; add dependencies.
- Delete or bypass tests; disable security controls; commit secrets; claim completion without evidence.

### Agent Decision Boundary
The agent may decide adapter internals and test organization. The agent must request approval for changing the `Reranker` trait, the permutation contract, or the fail-open policy.

### Mandatory Stop Conditions
Stop and report if the transport cannot be reused, the parser cannot express the Cohere order without weakening fail-closed checks, requirements are ambiguous, or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Provider URL validated; key sent only in the `Authorization` header over HTTPS.
- Response parsed without panic; bounded size enforced by the transport.
- Rerank candidates are documents already selected locally; no new data egress beyond the shortlist the operator chose to rerank.

### Sensitive Data Rules
- Never log the key or full document text; log counts and timing only.
- Mask `credentials.rerank_api_key`.

### Security Acceptance Conditions
- No key in logs/errors.
- Malformed provider output cannot produce a permutation containing an out-of-range index.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (Cohere body build, permutation parse, provider allowlist, bearer precedence)
- [ ] Integration tests (mock TEI and mock Cohere servers through the real adapter)
- [ ] Contract tests (existing TEI parsing unchanged; full permutation always returned)
- [ ] Regression tests (workspace green; no-provider behavior unchanged)
- [ ] Security tests (no key in output)
- [ ] Failure-mode tests (malformed body, out-of-range/duplicate index, empty documents, unknown provider)

### Required Test Scenarios
| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100300-01 | Cohere mock | Full permutation; omitted docs appended in order |
| T100300-02 | Duplicate/out-of-range index | Error; orchestrator keeps fused order |
| T100300-03 | Unknown `rerank.provider` | `ConfigCorrupt` |
| T100300-04 | Empty documents | Empty permutation, no request |
| T100300-05 | Bearer precedence | Expected key sent; no key in logs |
| T100300-06 | No provider configured | Factory returns `None`; behavior unchanged |

### Negative Testing
Verify invalid input is rejected, malformed provider output fails closed, existing TEI behavior is intact, and failures never reorder or drop candidates incorrectly.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100300-01 | Cohere-compatible rerank yields a full permutation | T100300-01, T100300-02 | PASS. `rerank_tests::cohere_permutation_equals_tei_results_parse` (Cohere mock `[2,0]` -> `[2,0,1]`, omitted doc appended) and `cohere_adapter_rejects_bad_indices_fail_closed` (duplicate and out-of-range indices error). Mocked via one-shot capture HTTP server through the real adapter (`POST /v1/rerank`, `top_n`, `model`, `authorization: Bearer`). |
| AC-100300-02 | TEI behavior unchanged | Contract tests | PASS. `HttpReranker` and `parse_rerank_response` bodies untouched; all pre-existing TEI tests green unchanged (`parse_results_order_appends_omitted_documents`, `parse_scores_argsorts_descending`, `live_sidecar_reorders`, `dead_sidecar_fails_open_to_caller`, `empty_shortlist_short_circuits`, plus `hybrid_tests` fail-open coverage). clio-retrieve: 139 tests passed, 0 failed. |
| AC-100300-03 | Provider selection fail-closed; factory config-driven | T100300-03, T100300-05, T100300-06 | PASS. `factory_fails_closed_on_bad_provider_config` (`rerank.provider=openai` -> `ConfigCorrupt` "tei|cohere"; missing model -> `ConfigCorrupt`; cohere without key -> `ConfigCorrupt`; bad scheme rejected); `factory_selects_teiranker_by_provider` / `factory_empty_provider_keeps_tei_default` / `factory_selects_cohere_with_bearer` prove wire-path selection; `cohere_adapter_posts_v1_rerank_with_top_n_model_and_bearer` proves the key goes only in the Authorization header. |
| AC-100300-04 | Empty/no-provider paths are no-ops | T100300-04, T100300-06 | PASS. `cohere_empty_documents_skip_the_request` + existing `empty_shortlist_short_circuits` (empty permutation, no request); `factory_without_url_is_none` and `runtime_factory_without_rerank_config_is_none` (factory returns `None` when `rerank.url` is empty). |
| AC-100300-05 | No regression in retrieval/fusion | Regression suite | PASS. Full workspace coverage run: all 261 reported files >=90% functions and lines; aggregate 98.92% functions / 97.89% lines; fusion/hybrid suites green (hybrid.rs 99.26% lines, hybrid_rank.rs 97.47%). |

### Definition of Done
- [x] All in-scope behavior implemented. (Cohere adapter `CohereReranker`, factory `build_reranker`/`build_reranker_from`, docs)
- [x] All acceptance criteria pass. (AC-100300-01..AC-100300-05 above, real test output)
- [x] Required tests pass. (clio-retrieve 139 passed / 0 failed; full workspace suite green under llvm-cov)
- [x] No unauthorized changes introduced. (Diff: clio-retrieve rerank code+tests, `fixtures_tests` capture server, lib.rs exports, README, .env.example, phase file)
- [x] Existing behavior remains intact. (TEI adapter and parser untouched; no-provider behavior unchanged)
- [x] Security checks pass. (Bearer only in Authorization header; key masked in `CohereReranker` Debug; no key in error text — asserted by tests)
- [x] Documentation updated. (README "Embed / rerank provider configuration"; `.env.example` rerank knobs)
- [x] Evidence collected and verification completed. (Below; coverage JSON + test output)
- [x] Required approval is obtained (downstream pipeline step).

### Completion Evidence
- **Implementation summary.** Task 1: `clio-retrieve/src/rerank.rs` gained `CohereReranker` (`POST {url}/v1/rerank` with `{"query","documents","top_n","model"}`, bearer auth, response parsed by the existing `parse_rerank_response`, so omitted documents append in original order and out-of-range/duplicate indices fail closed; empty document lists short-circuit without a request; manual `Debug` impl masks the bearer as `****`). `HttpReranker` (TEI) is byte-identical to before. Task 2: `build_reranker()` (effective config via `clio_config::Runtime`, bearer via `bearer_for("rerank")` precedence) and `build_reranker_from(&Value, bearer)` (no env reads): `rerank.url` empty -> `Ok(None)`; empty provider keeps the TEI sidecar default; `rerank.model` required when `rerank.url` is set (fail closed, `ConfigCorrupt`); `rerank.provider = "cohere"` additionally requires the bearer key (hosted provider, fail closed with a clear message); unknown provider -> `ConfigCorrupt` listing allowed values; error text never contains key material. This is the Phase 100350 seam: `clio_retrieve::build_reranker() -> Result<Option<Arc<dyn Reranker>>, AmError>` feeds the existing `HybridRetriever::set_reranker`.
- **Changed components.** `crates/clio-retrieve/src/rerank.rs` (324 lines), `rerank_tests.rs` (316), `fixtures_tests.rs` (338, added request-capturing fake server), `lib.rs` (119, exports), `README.md`, `.env.example`. All Rust files <=450 lines with truthful AGENTS.md headers.
- **Test output.** `cargo test -p clio-retrieve --locked`: 139 passed, 0 failed. T100300-01/T100300-02/T100300-04/T100300-05/T100300-06 as named tests in `rerank_tests.rs` (see AC table); T100300-03 covered by `factory_fails_closed_on_bad_provider_config`; orchestrator fail-open regression covered by existing `hybrid_tests` (FailReranker keeps fused order).
- **Masked config sample.** `credentials.rerank_api_key` masking proven by clio-config test `rerank_api_key_masked_everywhere` (config_get shows `****` suffix, raw key absent from serialized view); adapter-side masking proven by `cohere_debug_masks_the_bearer`.
- **Verification report.** Pre-change baseline gate JSON at `/tmp/cov-baseline.json`: 261 reported files, 0 below 90% (aggregate 98.91% fns / 97.89% lines). Final workspace JSON (`cargo llvm-cov --workspace --locked --json`): rerank.rs 17/17 functions, 181/181 lines (100%); aggregate 98.92% fns / 97.89% lines; per-file scan: 0 files below 90% functions or lines. `cargo clippy -p clio-retrieve --all-targets -- -D warnings` clean; `cargo fmt -p clio-retrieve` clean.
- **Known limitations.** The reranker is not attached to the live retrieval path (runtime wiring is a later phase), so configuring it has no runtime effect yet. `rerank.provider = "cohere"` requires a bearer key at construction, so keyless local Cohere-compatible endpoints are not supported (rollback for local sidecars is `rerank.provider = "tei"`). The pre-existing derived `Debug` for `HttpReranker` still prints its bearer verbatim (debt predating this phase, not changed here); the new adapter masks it.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Provider outage | Transport error | Fail-open: fused order kept; warning recorded |
| Malformed order | Parser | Error; fused order kept |
| Unknown provider | Factory | Fail closed at construction |
| Key missing with hosted provider | Factory | Fail closed with clear message |

### Rollback Strategy
Set `rerank.provider = "tei"` and point `rerank.url` at the local sidecar, or leave `rerank.url` empty to disable rerank.

### Partial Completion Policy
Do not claim completion if only one provider adapter works. Record completed and incomplete work separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.9.5.E / FR-32 | Task 2 | T100300-03, T100300-05, T100300-06 | AC-100300-03 |
| P4 / §4.5 bounded rerank | Task 1 | T100300-01, T100300-02 | AC-100300-01 |
| `gap/zero-deps.md` rerank portion | Tasks 1–3 | T100300-01…T100300-06 | AC-100300-01…AC-100300-05 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- Cohere-compatible rerank adapter and a reranker factory.
- Documentation of rerank provider knobs.

### Guarantees Provided to Downstream Phases
- Phase 100350 can attach the configured reranker to the live retriever via the existing `set_reranker`.

### Known Limitations
- The reranker is not attached to the live retrieval path until Phase 100350, so configuring it has no runtime effect before then.
- No rerank-specific candidate-count tuning or model selection logic beyond config.
- Fail-open remains the policy; a rerank failure silently keeps fused order except for a structured warning.

### Downstream Prerequisites
- Phase 100350 consumes the factory and the existing `set_reranker` hook.

### Final Status
PASS | PASS WITH DOCUMENTED LIMITATIONS | BLOCKED | FAILED

### Verification Sign-Off
- Implementer: Developer r1 (OpenCode CLI, Together . GLM-5.3 Flash High)
- Verifier: [TBD - Adversary/Remediator rounds]
- Human Approver: [TBD, if required]
- Date: 2026-09-21
