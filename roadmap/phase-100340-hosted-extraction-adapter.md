# Phase 100340: Hosted Extraction Adapter (OpenAI-Compatible Chat Completions)

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r1 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100340 · **Effort:** `1.5×` · **Scope:** `gap/zero-deps.md` extraction portion, deferred from the zero-dependency provider phases (028–030) by operator decision

### Vocabulary (read first) — zero shared moniker
| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **`extract.provider`** | `template` \| `openai` | Effective config | Be conflated with `embed.provider`/`rerank.provider` |
| **template extractor** | Existing `TemplateApiExtractor` (`{"template","text",...}` → `{"snapshot","gist"}`) | `clio-write` | Change its wire shape; local NuExtract depends on it |
| **chat extractor** | OpenAI-compatible `/v1/chat/completions` adapter | `clio-write` | Return a snapshot that skipped span verification |
| **extraction egress** | Sending source text to a hosted LLM | This phase | Happen unless the operator explicitly selected the hosted provider |
| **span verification** | FR-4 grounding check on entities/numbers/dates | `clio-write` (existing) | Be relaxed, bypassed, or reimplemented by the adapter |

---

## 1. Objective

### Goal
Add the hosted-extraction half of the zero-dependency deployment: an `Extractor` implementation that prompts an OpenAI-compatible chat-completions endpoint to produce the same `{snapshot, gist}` candidate the local NuExtract sidecar produces, with output validation and the existing span verification unchanged. This closes the extraction portion of `gap/zero-deps.md` that the zero-dependency provider phases (028–030) deliberately deferred.

### Expected Outcome
- `extract.provider = "openai"` sends a chat-completions request whose system prompt requests the exact snapshot/gist JSON, and parses the assistant message into an `ExtractCandidate`.
- `extract.provider = "template"` keeps the existing local NuExtract behavior byte-shape compatible.
- Malformed, non-JSON, or ungrounded output never commits: the adapter fails closed, and the existing retry-once-then-refuse path (FR-4) applies.
- `credentials.extract_api_key`, `EXTRACT_URL`, `EXTRACT_MODEL`, `EXTRACT_PROVIDER`, `EXTRACT_API_KEY` reach the effective config; the key is masked everywhere.
- Source text is secret-scrubbed before egress, and hosted extraction is never enabled by default.

### Parent Requirement
`requirement.md` — FR-4 (span-verified extraction, retry once, then refuse), FR-5 (snapshot vs gist separation), PR-4 (gists non-authoritative), §4.9.5.E/FR-32 (config), NFR-6 (no secret leakage). Gap source: `gap/zero-deps.md`.

### Design References (non-trivial, validated)
- **OpenAI chat completions** — `POST /v1/chat/completions` with `messages[]` and `temperature: 0`; response `choices[0].message.content` is a string (`platform.openai.com/docs/api-reference/chat`). Structured-output modes exist but are provider-specific; the adapter must validate the plain JSON itself rather than assume a provider feature.
- **NuExtract is the local reference behavior** — the existing `TemplateApiExtractor` targets `numind/NuExtract-1.5-tiny` with a template + text request and a `temperature` of ~0; the hosted adapter reproduces the same output contract through a chat prompt.
- **Fail-closed structured extraction** — treating model output as untrusted and validating it before use is the standard pattern; the project already enforces this with the span verifier.

---

## 2. Scope Boundaries

### In Scope
- A new chat-completions `Extractor` adapter producing `ExtractCandidate { snapshot, gist, source_ref, diagnostic }`.
- A system prompt plus output validation that maps the assistant string into that struct.
- `extract.provider` selection and `credentials.extract_api_key`; env wiring for `EXTRACT_URL`, `EXTRACT_MODEL`, `EXTRACT_PROVIDER`, `EXTRACT_API_KEY`.
- Reuse of the Phase 100280 HTTPS transport (no second HTTP client).
- Secret scrubbing of the source text before egress.
- An extractor factory that Phase 100350 wires into the live runtime.
- Docs: README/`.env.example`/`hardware.md` note that hosted extraction is now an option and that it sends source text to a third party.

### Explicitly Out of Scope
- Offline training and model packaging of the extractor (out of scope entirely). A local model download is out of scope for this slice; hosting adapter scope is otherwise unaffected.
- Provider ingest (`import_provider` matrix) — unrelated.
- Changing the span verifier, admission gates, taxonomy, or the `ExtractCandidate` contract.
- Streaming, function/tool calling, or structured-output JSON-schema modes that not all providers implement.
- Extraction quality tuning beyond a single documented system prompt and output validation.
- Wiring extraction into the live MCP runtime (Phase 100350).

### Must Not Change
- `TemplateApiExtractor` wire shape and the local NuExtract path.
- FR-4: retry once, then do not commit the structured snapshot.
- PR-4: gists remain non-authoritative; exact-value consumers still read snapshots.
- Secret masking and the config precedence order.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100280 accepted: HTTPS transport, provider/config conventions, key masking.
- Phase 100310 accepted (recommended): the CLI runs zero-config, so the extraction provider is usable end to end.
- The existing extraction pipeline (`clio-write` `Extractor` trait, span verification, retry) is intact.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Phase 100280 transport | `post_json` reachable from the extraction owner | Import/build |
| `Extractor` trait + `ExtractCandidate` | Stable, unchanged | `clio-write/src/extract.rs` inspection |
| Live extraction consumer | Located, or its absence explicitly reported | Discovery + stop condition |
| Secret scrubbing | `clio_config::secret::scrub_inline_secrets` available | Existing tests |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Locate every consumer of the `Extractor` trait and `parallel_ingest` in production code, not only tests.
- Confirm the `Transport` seam (`clio-write/src/extract.rs`) and how a live transport would be supplied.
- Confirm the span-verification + retry-once flow and where a failed candidate is rejected.
- Confirm config allowlist and env overlay extension points (the zero-dependency plumbing still exposes only `url`/`model`/`temperature` for extraction).
- Confirm `clio-write`'s dependency direction so the transport can be reused without a cycle.

### Discovery Output
- **Extraction is not wired into the live MCP path.** `clio-write/src/extract.rs` defines `Extractor`, `TemplateApiExtractor<T: Transport>`, `FixtureExtractor`, and `PoisonExtractor`; `ingest.rs` drives chunk → extract → consolidate → gated leaf. But repository search shows no live `Extractor` construction outside tests and `clio-write` public re-exports (`lib.rs`). The MCP `store` path does not call extraction. This mirrors the dense-index wiring gap owned by Phase 100350.
- **The transport seam is injectable.** `Transport::post_json(url, body)` is the only I/O seam; CI runs with fixtures/poison extractors and no live I/O. A hosted adapter should implement `Extractor` over the same seam so tests stay offline.
- **`clio-write` does not depend on `clio-index`.** `clio-write` depends on `clio-types`, `clio-config`, `clio-admission`, `clio-store`, `chrono`, `serde`, `serde_json`, `unicode-normalization`. `clio-index` does not depend on `clio-write`, so adding `clio-write → clio-index` (to reuse `post_json`) is acyclic; alternatively `clio-lib` can supply the transport implementation. Either is acceptable; a second HTTP client is not.
- **Config gaps.** `validate.rs` allowlists `extract.url`, `extract.model`, `extract.temperature` (and `extract.day_first` in defaults) but has **no** `extract.provider` and no `credentials.extract_api_key`. `apply_process_env` does not wire any `EXTRACT_*` var.
- **`.env.example` lists `EXTRACT_*` as if wired** (URL, MODEL via GGUF, PORT) but only for the local Compose service; `EXTRACT_API_KEY`/`LLM_API_KEY` are commented and unwired.
- **Secret scrubbing exists.** `clio_config::secret::scrub_inline_secrets` is used by the embed path; the same scrubbing should run on source text before hosted egress.
- **Span verification is downstream and authoritative.** The adapter produces a candidate; the verifier decides commit. The adapter must not attempt to pre-verify or bypass.

### Repository Adaptation Rule
The agent must determine the concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, module names, or directory structures unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Chat-Completions Extraction Adapter

#### Intent
Reproduce the local extractor's output contract through a hosted chat API, validating output before it enters the pipeline.

#### Required Capability or Behavior
- `ExtractRequest { source_text, tool_payload, schema_template, verify_feedback }` maps to a chat request:
  - system message: instruction to return **only** a JSON object with `snapshot` (populated from the provided template) and `gist`, using exact values copied from the source, and to return an empty/absent snapshot rather than inventing values.
  - user message: the (scrubbed) source text, the schema template, optional tool payload, and retry `verify_feedback` when present.
  - `temperature` from `extract.temperature`.
- Response mapping: parse `choices[0].message.content` as JSON; extract `snapshot` (non-null object), `gist` (string, optional), `source_ref` (default from caller/`"extract"`), and an optional `diagnostic`.
- Validation: content must be a JSON object; a provider error, empty `choices`, a non-JSON body, or a content string that is not a JSON object is a structured `AmError`, not a panic. If `verify_feedback` is present (retry), invalid output is still an error so the pipeline can refuse commit.
- The adapter does not score, admit, or verify; it returns a candidate only.

#### Architectural Responsibility
`clio-write` owns the adapter (it owns extraction). It reuses the Phase 100280 transport through the existing `Transport` seam or a live transport supplied by a caller.

#### Required Changes
1. Add the chat adapter as an `Extractor` implementation.
2. Build the prompt (system + user) deterministically; no randomness; `temperature` honored.
3. Parse and validate the response into `ExtractCandidate`.
4. Keep `TemplateApiExtractor` unchanged and selectable.

#### Implementation Constraints
- No second HTTP client; reuse the Phase 100280 transport (direct dependency or caller-supplied).
- No streaming; bounded response size; request timeouts honored.
- The adapter never writes to the store and never bypasses span verification.

#### Expected Result
A mocked chat endpoint returning `{"snapshot":{...},"gist":"..."}` yields an `ExtractCandidate`; a mocked non-JSON content returns an error.

### Task 2: Prompt, Schema, and Output Validation

#### Intent
Make the hosted output as safe to consume as the local one, without trusting the model.

#### Required Capability or Behavior
- The system prompt states the output schema explicitly (top-level `snapshot` and `gist`), forbids commentary/markdown fences, and instructs that numeric/date/entity values be copied verbatim from the source.
- The user message includes the caller's `schema_template` so the model populates the requested keys rather than inventing a shape.
- On retry (`verify_feedback` present), the prompt includes the verifier feedback so the model can correct grounded values.
- Validation checks: JSON object; `snapshot` if present is an object (not an array/string); `gist` if present is a string; oversized content rejected by the transport cap; a fenced/annotated response is a validation failure (do not strip arbitrary fences silently).

#### Architectural Responsibility
`clio-write` prompt + parser; the verifier remains the authority on grounding.

#### Required Changes
1. Add the system prompt and user-message assembly as testable functions.
2. Add the response validator with explicit error messages (no panic).
3. Document that a hosted model's output is untrusted input.

#### Implementation Constraints
- No prompt content is derived from configuration in a way that could inject instructions; only the schema template and feedback are interpolated, inside clearly delimited sections.
- Determinism: identical request → identical prompt string (snapshot-testable).

#### Expected Result
Golden-prompt tests pin the message shape; validator tests cover malformed variants.

### Task 3: Config, Credentials, and Env Wiring

#### Intent
Make the hosted extractor selectable and keyed like embed/rerank.

#### Required Capability or Behavior
- New allowlisted paths: `extract.provider` (`template` | `openai`), `credentials.extract_api_key`.
- Bearer precedence: `credentials.extract_api_key` else `credentials.api_key` else none.
- Env overlay: `EXTRACT_URL`, `EXTRACT_MODEL`, `EXTRACT_PROVIDER`, `EXTRACT_API_KEY`.
- `credentials.extract_api_key` is masked in `config_get` and all diagnostics.
- A factory resolves provider/url/model/temperature/key from effective config and returns the configured `Extractor`; an unknown provider or a missing URL/model fails closed.

#### Architectural Responsibility
`clio-config` schema/masking/env; `clio-write` factory. No process-environment reads outside the established env overlay.

#### Required Changes
1. Extend `system_defaults_json` with `extract.provider` (default `template`).
2. Extend validation with the provider allowlist and key path.
3. Extend `apply_process_env` with the `EXTRACT_*` keys.
4. Add the masking path for `credentials.extract_api_key`.
5. Correct `.env.example`: separate local Compose vars from the hosted `EXTRACT_URL`/`EXTRACT_MODEL`/`EXTRACT_PROVIDER`/`EXTRACT_API_KEY` and label them clearly.

#### Implementation Constraints
- Hosted extraction is never enabled implicitly; `template` remains the default.
- No raw key in logs, errors, or config views.

#### Expected Result
With only env vars set, the factory returns the chat extractor with the key applied; `config_get` shows the key masked.

### Task 4: Extractor Factory (Live Wiring Owned by Phase 100350)

#### Intent
Ship a factory that turns effective config into a concrete `Extractor`, and hand live-path wiring to Phase 100350, which owns making dense indexing, reranking, and extraction run inside the MCP runtime.

#### Required Capability or Behavior
- A factory resolves provider/url/model/temperature/key from effective config and returns the configured `Extractor`; unknown provider or missing url/model fails closed.
- The factory is directly usable by a caller that runs the ingest pipeline, and is callable from Phase 100350's runtime wiring without further changes.
- Hosted extraction remains opt-in (`template` default); nothing in this phase adds network egress to the MCP runtime.

#### Architectural Responsibility
`clio-write` owns the adapter and factory. Runtime ingest wiring is Phase 100350's responsibility; this phase must not add extraction to the MCP `store` tool or start an ingest loop.

#### Required Changes
1. Add the config→`Extractor` factory.
2. Keep the transport injectable so Phase 100350 and tests can supply a live or stub transport.
3. Document the wiring seam Phase 100350 will call.

#### Implementation Constraints
- No new default network egress; hosted extraction only when explicitly configured.
- Span verification and admission gates stay between the adapter and any write.

#### Expected Result
With only env vars set, the factory returns the chat extractor with the key applied, and a Phase 100350 wiring can consume it without modifying this crate's adapter.

### Task 5: Documentation and Egress Disclosure

#### Intent
Make the data-egress and quality trade-offs explicit.

#### Required Capability or Behavior
- README/`hardware.md` describe hosted extraction as an optional quality tier, name the egress (source text to a third party), and state that the local NuExtract path remains the airgapped choice.
- `.env.example` documents the hosted extractor knobs.
- A note on quality: prompt-based extraction is expected to be less reliable than the fine-tuned local model; the span verifier is the backstop and rejects ungrounded snapshots.

### Implementation Freedom
The agent may choose concrete structure, naming, prompt wording, and internal design provided the required behavior is satisfied, architectural boundaries respected, existing contracts preserved, all acceptance criteria pass, and no prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the chat adapter, prompt/validator, factory, config/env wiring, tests, and docs.
- Add `clio-write → clio-index` if needed to reuse the transport (acyclic), or have `clio-lib` supply it.

### Forbidden Actions
- Add a second HTTP client or any dependency without approval.
- Bypass, weaken, or relocate span verification; change `ExtractCandidate`, the taxonomy, or admission.
- Make hosted extraction a default; send source text anywhere without explicit opt-in.
- Delete or bypass tests; commit secrets; claim completion without evidence.

### Agent Decision Boundary
The agent may decide prompt text, validator internals, and transport placement. The agent must request approval for: adding extraction to the MCP `store` write path (behavior + egress change), adding any dependency, publishing extraction fields in the versioned `tool_schema` pack, or changing the default provider.

### Mandatory Stop Conditions
Stop and report if: the extractor factory cannot be built without a dependency cycle; span verification would need modification; requirements are ambiguous; or correctness cannot be verified. Live-runtime wiring is not a stop condition here — it is owned by Phase 100350.

---

## 7. Security Constraints

### Required Controls
- Hosted extraction is opt-in; the default provider is `template`.
- Source text is secret-scrubbed with the existing scrubber before egress.
- The response is treated as untrusted: bounded size, JSON-validated, no code execution, no panic.
- Endpoint URL and provider are validated before use; the key travels only in the `Authorization` header over HTTPS.

### Sensitive Data Rules
- Never log source text or a response body that may contain secrets; log only sizes, provider, model, and masked metadata.
- Never log or return the key; mask `credentials.extract_api_key`.
- Never commit secrets.

### Security Acceptance Conditions
- With no extraction provider configured, no source text leaves the process.
- A key never appears in logs, errors, or config views.
- Malformed/malicious model output cannot cause a commit or a panic.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (prompt assembly, response parsing/validation, provider allowlist, bearer precedence, scrubbing before egress)
- [ ] Integration tests (mocked chat endpoint through the real factory and transport)
- [ ] Contract tests (`TemplateApiExtractor` wire shape unchanged; `ExtractCandidate` unchanged)
- [ ] End-to-end tests (candidate → span verification → retry-once → refuse-or-commit through the existing pipeline)
- [ ] Regression tests (workspace green; default `template` behavior unchanged)
- [ ] Security tests (no egress when unconfigured; no secret in logs; malformed output rejected)
- [ ] Failure-mode tests (provider error, empty choices, non-JSON content, fenced content, oversized response)

### Required Test Scenarios
| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100340-01 | Valid chat response | `ExtractCandidate` with snapshot + gist |
| T100340-02 | Content is not JSON | Structured `AmError`; pipeline refuses commit |
| T100340-03 | Content wrapped in markdown fences | Validation failure (no silent stripping) |
| T100340-04 | Empty/missing `choices` | Structured error |
| T100340-05 | `snapshot` present but not an object | Validation failure |
| T100340-06 | Retry with `verify_feedback` | Feedback included in the prompt; still validated |
| T100340-07 | Unknown `extract.provider` | `ConfigCorrupt` |
| T100340-08 | Bearer precedence | Expected key sent; key absent from logs |
| T100340-09 | No provider configured | Default `template`; no network egress |
| T100340-10 | Source contains a secret | Scrubbed before it appears in the request body |
| T100340-11 | Ungrounded snapshot from the model | Span verifier rejects; no commit |

### Negative Testing
Verify invalid input is rejected, unauthorized egress cannot occur, partial failures leave no candidate committed, retries are bounded, existing local extraction behavior is intact, and failure does not leave invalid state.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100340-01 | Chat adapter maps a valid response to `ExtractCandidate` | T100340-01 | PASS — `extract_chat_tests::t34_01_valid_response_maps_to_candidate`, `extract_factory_tests::t34_08_openai_factory_selects_chat_extractor_with_key` |
| AC-100340-02 | Malformed output fails closed and never commits | T100340-02, T100340-03, T100340-04, T100340-05 | PASS — `t34_02_non_json_content_fails_closed`, `t34_03_fenced_content_is_a_validation_failure`, `t34_04_empty_or_missing_choices_fails_closed`, `t34_05_wrong_snapshot_or_gist_shape_fails_closed`, `oversized_content_is_rejected`, `t34_02_pipeline_refuses_commit_on_malformed_content` (extractor error propagates; no candidate stored), `extract_chat_egress_tests::provider_error_body_is_surfaced_bounded_and_scrubbed` |
| AC-100340-03 | Prompt includes schema + retry feedback deterministically | T100340-06 | PASS — `golden_prompt_is_deterministic_and_delimited` (golden, byte-equal across calls, delimited sections) + `t34_06_retry_feedback_reaches_the_chat_prompt`; delimiter-breakout safety in `extract_chat_egress_tests::source_delimiter_tags_cannot_break_out_of_their_section` and `payload_and_feedback_delimiter_tags_are_neutralized` |
| AC-100340-04 | Provider/key/env config wired and masked | T100340-07, T100340-08 | PASS — clio-config `extract_knob_tests` (env wiring, allowlist, masking via `config_get`/`effective_masked`, bearer precedence) + `t34_07_unknown_provider_fails_closed`, `t34_08_openai_factory_fails_closed_without_key_or_target` |
| AC-100340-05 | Hosted extraction is opt-in; no default egress | T100340-09 | PASS — `extract_knob_tests::extract_provider_defaults_to_template`, `extract_factory_tests::t34_09_default_is_template_without_egress` (factory builds template, transport untouched) |
| AC-100340-06 | Source scrubbed before egress | T100340-10 | PASS — `t34_10_source_is_scrubbed_before_egress` (request untouched; egress string masked) + `extract_chat_egress_tests::tool_payload_secrets_are_masked_before_egress` (structured tool payload field-masked and inline-scrubbed) |
| AC-100340-07 | Span verification still rejects ungrounded snapshots | T100340-11 | PASS — `t34_11_ungrounded_snapshot_is_refused_by_span_verify` via `extract_and_verify` (candidate None, non-authoritative retention) |
| AC-100340-08 | Local `template` path unchanged | Contract/regression tests | PASS — `TemplateApiExtractor` untouched (`extract.rs` diff adds only the transport trait bearer method + `HttpTransport`); existing `extract_tests::template_api_uses_transport` green; full workspace suite green |
| AC-100340-09 | Factory selects the configured extractor from effective config | T100340-07, T100340-08, T100340-09 | PASS — `build_extractor_from` dispatch tests (template default, openai with key, unknown provider `ConfigCorrupt`); live MCP wiring deferred to Phase 100350 per plan |

### Definition of Done
- [x] All in-scope behavior implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation updated.
- [x] Evidence collected and verification completed.
- [x] Required approval obtained. (No agent-decision-boundary approval was needed: no dependency added — the chat adapter rides the existing Phase 100280 ureq transport via `clio-index` re-exports; no MCP store-path change; no tool_schema publish; default provider unchanged.)

### Completion Evidence
- **Implementation summary:** `clio-write/src/extract_chat.rs` — `ChatExtractor<T: Transport>` posting `{base}/v1/chat/completions` (base tolerates trailing `/` or `/v1`) with a fixed `SYSTEM_PROMPT`, deterministic delimited user message (schema template, optional tool payload, `scrub_inline_secrets`-scrubbed source text, retry feedback), configured `temperature`, optional bearer; `parse_chat_response` fails closed (object response, non-empty `choices`, string content, 1 MiB content cap, JSON-object content, object `snapshot`, string `gist`, optional `diagnostic`, `source_ref` default `"extract"`); fenced/non-JSON content is rejected, never stripped. `clio-write/src/extract_factory.rs` — `build_extractor_from(effective, bearer, transport)`: `template` (default incl. empty) → `TemplateApiExtractor`; `openai` → `ChatExtractor`, failing closed without url/model/key; unknown provider → `ConfigCorrupt`. `clio-write/src/extract.rs` — `Transport::post_json_bearer` default method (delegates, ignores bearer) + `HttpTransport` riding the Phase 100280 ureq transport (`clio_index::post_json`, verified TLS, 64 MiB cap). `clio-config` — `extract.provider` default `template` in `system_defaults`, allowlist + `template|openai` validation for `extract.provider`, `credentials.extract_api_key` set path (auto-masked via existing secret markers), env overlay `EXTRACT_URL`/`EXTRACT_MODEL`/`EXTRACT_PROVIDER`/`EXTRACT_API_KEY`, bearer precedence via the existing `bearer_for("extract")`. `clio-write` gained the `clio-index` dependency (acyclic; allowed by the plan) to reuse the shared HTTPS client — no second HTTP client, no new third-party dependency.
- **Changed components:** `clio-config`: `config/merge.rs`, `config/validate.rs`, `config/env.rs`, new `config/extract_knob_tests.rs`. `clio-write`: `Cargo.toml`, `src/lib.rs`, `src/extract.rs`, new `src/extract_chat.rs`, `src/extract_factory.rs` + test files. Docs: `README.md` (extraction provider section), `hardware.md` (egress note + hosted env), `.env.example` (hosted knobs separated from local Compose vars). All new/modified Rust files ≤450 lines with the AGENTS.md header.
- **Test execution output:** `make coverage` (final): exit 0 with `--fail-under-lines 90 --fail-under-functions 90`; TOTAL 97.90% lines / 98.93% functions; **no reported source file below 90/90**. Per new file: `extract_chat.rs` 94.27% lines / 100.00% functions, `extract_factory.rs` 100/100, `extract.rs` 100/100, `env.rs` 100/100, `merge.rs` 100/100, `validate.rs` 98.33/100. `cargo test -p clio-config -p clio-write` — 147 + 137 tests green (new: T100340-01…T100340-11 mapped as in the AC table; clio-write 137 after r1 remediation added 5 tests). Clippy `-D warnings` and `cargo fmt` clean workspace-wide.
- **Remediation (r1):** `cargo fmt` failures fixed; AGENTS.md headers completed on both test files; duplicate `t34_03_` prefix removed and `t34_04_empty_or_missing_choices_fails_closed` added; prompt delimiter neutralization (`neutralize_delimiters`) and tool-payload masking (`scrub_payload` = `masked_clone` + `scrub_inline_secrets`) added, with a new `extract_chat_egress_tests.rs` module; provider `error.message` now surfaced bounded (256 chars) and scrubbed. Re-verified: `cargo fmt --all -- --check` exit 0; `cargo test -p clio-write` 137 passed; `make check` exit 0 (47 suites, clippy `-D warnings` clean); `make coverage` exit 0 (TOTAL 97.90% lines / 98.93% functions, per-file scan 272 files, 0 below 90).
- **Golden prompt:** pinned by `golden_prompt_is_deterministic_and_delimited` — system prompt is the `SYSTEM_PROMPT` const; user message is `<schema_template>` / `<tool_payload>` (optional) / `<source_text>` (scrubbed) / `<verify_feedback>` (optional) sections, byte-equal for identical requests.
- **Masked config sample:** `config_get("credentials.extract_api_key")` returns `****`+last-4 (test `extract_api_key_set_ack_is_masked`, `extract_env_knobs_reach_effective_config_and_mask_key` asserts the raw key is absent from the masked view).
- **Live-consumer wiring report:** extraction has no live MCP consumer today (unchanged from plan-time discovery). The factory is the wiring seam: a Phase 100350 ingest caller resolves `runtime.effective_raw()` + `runtime.bearer_for("extract")` and passes a transport (`HttpTransport` for live I/O, any `Transport` stub for tests) to `clio_write::build_extractor_from`. The factory itself performs no I/O.
- **Verification report:** baseline gate before edits: 270 files, none below 90/90 (97.92/98.96). T100340-01…T100340-11 all pass as listed in the AC table. Two pre-existing flakes observed once under load and green on rerun (clio-config persist `save_is_owner_only_and_round_trips`, clio-ops `reindex_across_two_providers_and_widths`) — neither file was touched by this phase; both pass in isolation and in the final gate.
- **Known limitations:** see §12.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Model returns non-JSON / fenced text | Validator | Structured error; retry once with feedback; then refuse commit |
| Provider outage | Transport error | Bounded retries; candidate not committed; clear error |
| Wrong snapshot shape | Validator | Reject; no write |
| Ungrounded values | Span verifier | Retry once; then refuse; optional non-authoritative gist/diagnostic only |
| Key missing with hosted provider | Factory | Fail closed with a clear message |
| Unintended egress | Provider unset check | Default `template`; no network call |

### Rollback Strategy
Set `extract.provider = "template"` (the default) to return to local extraction; no stored data changes. Removing the adapter restores the previous build.

### Partial Completion Policy
Deliver the adapter only together with validation and tests. If wiring is not possible (no live consumer), say so explicitly and do not claim end-to-end extraction. Record completed and incomplete work separately.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-4 span-verified extraction (retry once, then refuse) | Tasks 1, 2, 4 | T100340-02, T100340-11 | AC-100340-02, AC-100340-07 |
| FR-5 / PR-4 snapshot vs gist | Task 1 | T100340-01 | AC-100340-01 |
| §4.9.5.E / FR-32 (config + profiles) | Task 3 | T100340-07, T100340-08 | AC-100340-04 |
| NFR-6 (no secret leakage) | Task 3, 5 | T100340-08, T100340-10 | AC-100340-04, AC-100340-06 |
| `gap/zero-deps.md` extraction portion | Tasks 1–5 | T100340-01…T100340-11 | AC-100340-01…AC-100340-09 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- OpenAI-compatible chat-completions extraction adapter with prompt + output validation.
- `extract.provider`, `credentials.extract_api_key`, and `EXTRACT_*` env wiring with masking.
- A factory selecting the extractor from effective config.
- Documentation of the egress and quality trade-offs.

### Guarantees Provided to Downstream Phases
- Extraction can be hosted or local with the same `ExtractCandidate` contract.
- Span verification and admission remain the authorities; the adapter cannot commit.

### Known Limitations
- Prompt-based extraction quality is expected to be lower than the fine-tuned local NuExtract model; the span verifier rejects ungrounded snapshots, so recall may drop before precision does.
- No structured-output/JSON-schema provider mode; the adapter validates plain JSON per provider-agnostic behavior.
- Hosted extraction sends source text to a third party; it is opt-in and documented. Source text is inline-secret scrubbed, and the optional tool payload is additionally field-masked (secret-looking keys) before egress. The schema template and retry feedback are delimiter-neutralized but not secret-scrubbed.
- Live runtime wiring (making extraction run inside the MCP path) is owned by Phase 100350; this phase ships the adapter, factory, and tests, so extraction is not exercised end to end from `am mcp stdio` until Phase 100350 lands.

### Downstream Prerequisites
- Phase 100350 wires the factory into the runtime ingest path so host and local extraction actually run.
- Phase 100330's wizard may add an extraction provider option once this phase is accepted; until then the wizard routes extraction to local or skips it.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS (developer round r1: implementation complete, evidence above; live wiring owned by Phase 100350)

### Verification Sign-Off
- Implementer: OpenCode CLI (Together . GLM-5.3 Flash High), Developer r1
- Verifier: [pending — Adversary r1]
- Human Approver: [not required at developer round]
- Date: 2026-09-22
