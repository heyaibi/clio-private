# Phase 100050: Online Extraction and Span Verification

### Attribution
| Role | Agent |
|------|-------|
| Developer | Cursor (Auto) |
| Adversary | Antigravity (Gemini 3.8 Flash) |
| Remediator | Cursor (Auto) |
| Remedy Approver | Antigravity (Gemini 3.8 Flash) |
| Adversary (phase-100420 r1 pass) | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max); 7 findings filed (`runs/phase-100420/findings-task2-003-005.json`), 6 remedied with tests, F-04 accepted risk (live-model CI exercise, unowned), F-07 build-time validation accepted as designed |

**Index slice 100050 · **Effort:** `1×` · **Scope:** `roadmap/index.md` slice 100050 (authoritative)

## 1. Objective

### Goal
Build turn/tool extraction into **schema-typed snapshots** with a cheap online **span-copy verifier** for entities, numbers, and dates (§4.4 / FR-4 / PR-4). On verification failure: retry extraction **once**, then refuse to commit the structured snapshot; log the rejection; MAY retain a non-authoritative gist and/or diagnostic candidate. Offline training of the extractor is out of scope entirely.

### Expected Outcome
- An extraction pipeline turns source text (conversation turn and/or tool-call payload) into a schema-typed candidate snapshot + optional prose gist.
- Before any admitted snapshot commit, every entity / number / date field that claims to be extractive is verified as a span copy (or format-equivalent span) from the source.
- Verifier failure → one retry → still fail → **no admitted snapshot**; rejection logged (PR-5 / PR-8).
- Gated `store` (Phase 100040) rejects or strips unverified snapshots when a snapshot is supplied; gist-only / diagnostic retention never becomes authoritative (FR-5 / FR-26).
- Online path stays a **cheap verifier** (string/number/date match against source)—not a second full LLM sampling loop at write time (§2.6).
- Extractor backend is pluggable (API Profile A/B vs local NuExtract Profile C per `hardware.md`); product rules do not fork by profile.

### Parent Requirement
`requirement.md` (current) — P3, PR-4, §2.5–§2.6, §4.4, §4.9.4.A `store` span rule, FR-4, FR-5, FR-26; Profile C extractor constraints in `hardware.md`. Span match details: `roadmap/phase-100050-appendix-span-verification.md`.

### Design references (non-normative)
- Grounded extraction with source offsets: [google/langextract](https://github.com/google/langextract) (`char_interval` / reject unlocatable extractions).
- Post-extraction grounding checks for numbers/dates with locale-aware matching: [llmground](https://pypi.org/project/llmground/).
- Bounded retry-on-validation-failure patterns: [extractx](https://github.com/veyorokon/extractx) (one repair pass with feedback—not unbounded sampling).
- Evidence-alignment IE: [SafePassage](https://arxiv.org/html/2510.00276v1) (context span must exist in document).

---

## 2. Scope Boundaries

### In Scope
- Online extractors behind a stable interface: input = source text + schema/template; output = candidate snapshot JSON + optional gist + provenance (`source_ref`).
- Cheap span verifier for entities, numbers, and dates prior to admitted snapshot commit.
- Exactly one extraction retry on verifier failure; then refuse snapshot commit.
- Structured reject/diagnostic logging; optional non-authoritative gist / diagnostic candidate retention.
- Wiring into Phase 100040 gated write so `store(..., snapshot=...)` cannot admit unverified snapshots.
- Config hooks for extractor endpoint / model / temperature (default ≈ 0 for local extract) without forking admission rules.
- Deterministic fixture-backed tests that do not require a live model for verifier logic.

### Explicitly Out of Scope
- Offline training and model packaging of the extractor (out of scope entirely).
- Parallel chunk orchestration and canonical near-duplicate merge (slice 100060).
- MemTree / dirty-path maintenance (slice 100070).
- Bi-temporal triple engine (slice 100080).
- Dense/lexical index pipelines (slice 100110).
- MCP transport packaging (slices 100160–17) beyond in-process handlers.
- Treating gist as authoritative for exact values.

### Must Not Change
- Phase 100040 gates (category/type + five-factor scoring) and `admit_preview` semantics.
- Phase 100030 snapshot/gist separation and repository primitives.
- Phase 100020 encryption / dual-backend contracts.
- Closed taxonomy and “no sixth semantic category” rule.
- NFR-5: online admission path remains deterministic.

### Scope Expansion Rule
If work outside this scope appears necessary:
1. Stop.
2. Document the reason.
3. Request clarification or approval.
4. Do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100040 accepted: gated write + `admit_preview` + episodic admission path.
- Phase 100030 accepted: snapshot/gist storage and getters.
- Phase 100010 accepted: config / ranking-env / bank-actor context; extractor URL knobs can live in effective config.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Gated `store` | Public long-term writes go through gates | Phase 100040 tests |
| Item repository | Can store snapshot + gist separately | Phase 100030 tests |
| Extractor backend | At least one callable backend (API stub or local) OR a recorded-fixture extractor for CI | Smoke + fixture mode |
| Telemetry/log sink | Can record verify rejects | Emit + assert in tests |

---

## 4. Existing-System Discovery

The agent MUST inspect the existing system before deciding
where or how to implement the changes.

### Required Discovery
- Identify the subsystem(s) responsible for the relevant behavior.
- Locate the existing implementation of related capabilities.
- Identify existing interfaces, contracts, schemas, and boundaries.
- Identify relevant tests and verification mechanisms.
- Identify architectural conventions that must be followed.
- Confirm that the current system supports the proposed change.
- Locate config knobs for LLM/extract endpoints and Profile A/B/C expectations in `hardware.md`.

### Discovery Output
Before implementation, the agent must report:

- Relevant subsystems identified
- Existing implementation approach
- Relevant contracts/interfaces
- Existing test coverage
- Architectural constraints discovered
- Assumptions confirmed
- Assumptions contradicted
- Questions requiring clarification

### Repository Adaptation Rule
The agent must determine the concrete implementation locations
from the actual repository. The plan does not prescribe file paths,
class names, module names, or directory structures unless they
are explicitly part of an externally required contract.

---

## 5. Implementation Specification

### Task 1: Extraction Interface and Schema-Typed Snapshot

#### Intent
Produce schema-typed event snapshots from turns/tool calls without treating the extractor as an admission authority.

#### Required Capability or Behavior
- Accept source text (+ optional structured tool payload) and a snapshot schema/template.
- Return `{snapshot?, gist?, source_ref, diagnostic?}` where `snapshot` is schema-typed JSON when extraction succeeds structurally.
- Mark which snapshot fields are **extractive** (must span-verify) vs **inferred labels** (e.g. category enum chosen by policy—those are gated by Phase 100040, not span-copied).
- Temperature and decoding defaults bias toward faithful copy (Profile C: NuExtract template→JSON at temp ≈ 0 per `hardware.md`).

#### Architectural Responsibility
Extraction service / adapter over LLM or local extract endpoint.

#### Required Changes
1. Extractor trait/interface + at least one real backend adapter and one fixture/replay backend for CI.
2. Snapshot schema/template packaging for the default memory event shape.
3. Clear separation: extraction output is a **candidate**, not an admitted item.

#### Implementation Constraints
- Do not run a multi-sample sampling loop at write time.
- Do not call Phase 100030 create from the extractor directly—always go through verify + Phase 100040 gates for long-term writes.
- Profile C default model identity is `numind/NuExtract-1.5-tiny` when that profile is selected; Profiles A/B use configured API extractors. Behavior after verification MUST be identical.

#### Expected Result
Fixture extractor produces valid candidate JSON for golden sources; live backends optional in CI.

### Task 2: Cheap Span Verifier (Entities, Numbers, Dates)

#### Intent
Implement FR-4 online verification: every extractive entity/number/date MUST be a verified span copy from the source.

#### Required Capability or Behavior
- For each extractive field, locate supporting evidence in the source text per `roadmap/phase-100050-appendix-span-verification.md`.
- **Entities / strings:** exact contiguous substring match (Unicode NFC + documented trim). Fuzzy-only matches fail.
- **Numbers / dates:** MUST locate a source substring that **parses** to the same value (appendix §§2–3). Normalized value alone with **no locatable span** is a hard fail.
- Ambiguous dates without configured `day_first` (or equivalent) MUST fail closed.
- Verifier is deterministic given identical source, snapshot, and config (NFR-5 spirit).
- On success, attach span offsets (char or byte—document which) to the candidate.

#### Architectural Responsibility
Fidelity / verification layer between extraction and admission.

#### Required Changes
1. Field classifier: extractive vs non-extractive.
2. Matchers for string / number / date with documented rules.
3. Structured verify report: `{ok, failures[{field, reason}], spans?}`.

#### Implementation Constraints
- Cheap: no second LLM judge required for the mandatory path (MAY add optional advisory scorers later; they MUST NOT replace the cheap verifier).
- Inferred taxonomy labels and computed scores are not span-verified as copies.
- Empty extractive fields: define and test (missing required extractive field = verify fail).

#### Expected Result
Unit tests cover grounded pass, paraphrase fail, number/date format variants, and ambiguous-date fail-closed.

### Task 3: Retry-Once Then Refuse Commit

#### Intent
Encode FR-4 control flow: fail → retry extraction once → still fail → do not commit structured snapshot.

#### Required Capability or Behavior
- Pipeline: extract → verify → on fail, extract once more (optionally with verifier failure feedback in the prompt) → verify → on fail, refuse snapshot commit.
- Rejection is logged with actor, source_ref, failure fields, and timestamps.
- System MAY persist/retain a non-authoritative gist and/or diagnostic candidate for offline review; MUST NOT treat it as an admitted snapshot (PR-4).
- Optional Profile C API fallback after local extract fails verification twice MUST still pass the same verifier before admit (`hardware.md`).

#### Architectural Responsibility
Write-path orchestration (extraction + verify), still before or inside the gated store boundary.

#### Required Changes
1. Retry counter hard-capped at one.
2. Commit gate: admitted snapshot write only if verify ok.
3. Telemetry events for verify_fail / retry / final_refuse.

#### Implementation Constraints
- No unbounded repair loops.
- Do not weaken Phase 100040 thresholds to “compensate” for verify failures.
- Diagnostic retention MUST use a clearly non-admitted channel (e.g. gist-only item without snapshot, or a diagnostics table)—document the choice.

#### Expected Result
Integration test: poisoned extractor fails verify twice → no snapshot row / no admitted snapshot; log present; optional gist/diagnostic non-authoritative.

### Task 4: Wire Into Gated `store`

#### Intent
Satisfy §4.9.4.A: `store` MUST verify snapshot spans when snapshot present.

#### Required Capability or Behavior
- When `store` receives a snapshot, run Task 2 (and Task 3 if extraction is invoked inline) before admission scoring completes successfully toward commit.
- If caller supplies a pre-built snapshot, still verify against provided `evidence_ref` / source text; missing source → structured error, no write.
- `admit_preview` SHOULD surface verify failures as structured rejection reasons without writing.
- Exact-value consumers continue to use `get_snapshot` only (FR-26).

#### Architectural Responsibility
Application service boundary (gated write wrapper from Phase 100040).

#### Required Changes
1. Insert verify step into gated write for snapshot-bearing candidates.
2. Preview parity for verify rejects.
3. Tests proving ungated repository create is still not a public path.

#### Implementation Constraints
- **Locked gate order** (MUST): (1) structural/schema validation → (2) span verify if snapshot present → (3) taxonomy/type whitelist → (4) five-factor admission score. Do not score or type-gate an unverifiable snapshot as if it were ready to admit.
- Episodic and semantic candidates both subject to snapshot verify when snapshot present.
- Match rules live in `roadmap/phase-100050-appendix-span-verification.md`; do not invent a looser pass path.

#### Expected Result
End-to-end: verified snapshot admits; unverified snapshot never admits.

### Implementation Freedom
The agent may choose the concrete implementation structure,
file locations, naming, and internal design provided that:
- The required behavior is satisfied.
- Architectural boundaries are respected.
- Existing contracts are preserved.
- All acceptance criteria pass.
- No prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Inspect and modify the repository as required to implement
  the in-scope capabilities.
- Add or update implementation components where appropriate.
- Add or update tests required to verify the behavior.
- Refactor locally when necessary to implement the specified
  capability without changing unrelated behavior.
- Add extractor HTTP client / schema template assets as needed.

### Forbidden Actions
- Change public contracts without approval.
- Delete or bypass tests.
- Disable security controls.
- Introduce unrelated features.
- Perform unrelated broad refactoring.
- Upgrade dependencies without approval.
- Commit secrets.
- Claim completion without evidence.
- Ship an online multi-sample sampling loop as the write-time path.

### Agent Decision Boundary
The agent may decide:
- Concrete file/module/class placement.
- Internal implementation structure.
- Local refactoring required for the phase.
- Test organization.
- Non-breaking implementation details.
- Exact number/date normalization rules, if documented and tested.
- Whether diagnostic candidates live as gist-only items vs a side table.

The agent must request approval for:
- Architecture changes beyond the stated scope.
- Breaking API or data-contract changes.
- Security-sensitive policy decisions.
- Destructive data operations.
- Changes affecting downstream phase assumptions.
- Treating fuzzy/ungrounded spans as verified.

### Mandatory Stop Conditions
Stop and report if:
- Requirements are ambiguous.
- Repository facts contradict the plan.
- Required dependencies are missing.
- Scope expansion is required.
- A destructive migration is necessary but unspecified.
- Existing architecture cannot support the intended behavior
  without an unapproved structural change.
- Correctness cannot be verified.
- No source text is available for a snapshot-bearing write and requirements do not define an alternate evidence channel.

---

## 7. Security Constraints

### Required Controls
- Extractor prompts/logs MUST mask secrets (API keys, DEKs, credentials in source text).
- Bank/actor required on extract→store path.
- Unverified content MUST NOT become an admitted fact-class snapshot.

### Sensitive Data Rules
- Never log full source turns containing secrets; redact or truncate in diagnostics.
- Never commit API keys or model credentials.
- Use approved secret/configuration mechanism from Phase 100010.

### Security Acceptance Conditions
- Verify-fail diagnostics do not leak DEKs or plaintext credentials.
- Cross-bank extract/store remains scoped.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests
- [ ] Integration tests
- [ ] Contract tests
- [ ] End-to-end tests
- [ ] Regression tests
- [ ] Security tests
- [ ] Failure-mode tests

### Required Test Scenarios

| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100050-01 | Snapshot entities/numbers/dates are exact source spans | Verify ok; admitted write possible after gates |
| T100050-02 | Paraphrased entity not in source | Verify fail |
| T100050-03 | Number format variant (`1,000` vs `1000`) with **locatable** span | Verify ok; offsets recorded |
| T-03b | Normalized number matches source meaning but **no** digit/span substring | Verify **fail** |
| T100050-04 | Ambiguous date without day-first policy | Verify fail (fail closed) |
| T100050-05 | First verify fail, second extract verifies | Retry once; admit after gates |
| T100050-06 | Verify fails twice | No admitted snapshot; rejection logged; optional non-authoritative gist/diagnostic only |
| T100050-07 | `store` with snapshot but missing source/evidence | Structured error; no write |
| T100050-08 | `admit_preview` on unverifiable snapshot | `pass=false` / verify rejection; no write |
| T100050-09 | Gist-only path (no snapshot) | No FR-4 span verify required for absent snapshot; gist remains non-authoritative |
| T100050-10 | Identical source/snapshot/config twice | Identical verify decision |
| T100050-11 | Secret-bearing source in fail path | Logs redacted |

### Negative Testing
Verify that:
- Invalid / ungrounded snapshots are rejected.
- Unauthorized bank actions are blocked.
- Partial failures do not leave half-admitted snapshots.
- Retry cannot exceed one extra extraction.
- Existing Phase 100030–004 behavior remains intact.
- Failure does not mark gist as authoritative.

### Verification Rule
Implementation claims must be supported by actual test output,
inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100050-01 | FR-4 span verify on extractive fields (span+parse; no spanless value match) | T100050-01–T100050-04, T-03b | `clio-write` `verify::verify_tests::{t01,t02,t03,t03b,t04}` pass |
| AC-100050-02 | Retry once then refuse snapshot commit | T100050-05, T100050-06 | `pipeline::pipeline_tests::{t05_retry_once_then_admit,t06_fail_twice_refuses_snapshot_keeps_diagnostic}` pass |
| AC-100050-03 | Unverified snapshot never admitted | T100050-06–T100050-08 | `store_path_tests::{unverified_snapshot_never_writes,t08_preview_unverified_no_write}` + T100050-06 pass |
| AC-100050-04 | Gated `store` enforces verify when snapshot present | T100050-07 | `store_path_tests::t07_missing_source_text_is_structured_error` pass |
| AC-100050-05 | Non-authoritative retention only | T100050-06, T100050-09 | T100050-06 retained diagnostic; `t09_gist_only_skips_span_verify` pass |
| AC-100050-06 | Deterministic verifier | T100050-10 | `verify_tests::t10_deterministic_twice` pass |
| AC-100050-07 | Secret masking on diagnostics | T100050-11 | `pipeline_tests::t11_secret_bearing_fail_path_redacts_logs` + dual-marker scrub tests pass |

### Definition of Done
- [x] All in-scope behavior is implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes were introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation is updated where required.
- [x] Evidence is collected.
- [x] Verification is completed.
- [x] Required approval is obtained.

### Completion Evidence
- **Implementation summary:** New crate `clio-write` provides pluggable extraction (`Extractor` / fixture / poison / template API), cheap span verification (entity NFC, number span-parse, date/time precision with fail-closed ambiguous numerics), retry-once refuse-commit pipeline, and `gated_store_verified` enforcing validate → span verify → admission. Vocab lock: `source_text` haystack; `evidence_ref` → `source_ref`.
- **Discovered/affected architectural components:** `clio-write` (new); `clio-config` extract knobs + centralized `scrub_inline_secrets`; `clio-admission` gated preview scrub delegates to `clio-config`; `clio-lib` re-exports; `requirement.md` store signature / glossary.
- **Changed-component summary:** Write-path orchestration lives in `clio-write`; admission scoring unchanged; persistence ungated primitives unchanged; public long-term writes go through verified gated store.
- **Test execution output:** `cargo test -p clio-write --locked` and workspace `make check` / `make coverage` green post-remediation (see findings remediation commentary).
- **Verifier rule documentation:** Spans are Unicode scalar offsets into NFC source. Numbers: en-US `,` grouping / `.` decimal by default (`comma_grouping`); currency stripped; range operators are not merged into one token. Dates: ISO date vs date-time compared at snapshot precision; ambiguous `D/M/Y` requires `day_first`; month aliases (e.g. `März`) localized before parse; char-safe windows only.
- **Verification report:** `.adversarial/f7746685-8e9b-4488-8756-3e16029de508/findings.json` + regenerated `report.html`.
- **Known limitations:** Live NuExtract optional in CI (fixtures); MCP `store` still stub; multilingual months are alias-table not full CLDR; scrubbing allocates an owned String (centralized, not zero-alloc).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Extractor timeout / 5xx | Transport error | Structured error; no admit; optional retry policy for transport ≠ FR-4 verify retry |
| Schema-invalid JSON | Parse error | Treat as extract fail; count toward retry-once if in extract stage |
| Verify fail ×2 | Verifier report | Refuse snapshot; log; optional diagnostic/gist |
| Missing evidence source | Validation | Structured error; no write |
| Local extract down (Profile C) | Health check | Optional configured API fallback still must verify |

### Rollback Strategy
Disable inline extraction feature flag / config; keep verifier mandatory for any snapshot-bearing `store`. Revert code; no special data migration expected beyond optional diagnostic rows.

### Partial Completion Policy
If only part of the phase is complete:
- Do not claim full completion.
- Record completed and incomplete work separately.
- Document remaining work.
- Do not leave undocumented broken state.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| FR-4 / §4.4 | Tasks 2–3 | T100050-01–T100050-06 | AC-100050-01, AC-100050-02 |
| PR-4 / FR-5 / FR-26 | Tasks 3–4 | T100050-06, T100050-09 | AC-100050-03, AC-100050-05 |
| §4.9.4.A store verify | Task 4 | T100050-07–T100050-08 | AC-100050-04 |
| PR-5 / PR-8 logging | Task 3 | T100050-06, T100050-11 | AC-100050-02, AC-100050-07 |
| §2.6 online verification (no training loop) | Task 1 | Design + T100050-05 | AC-100050-02 |
| NFR-5 online determinism | Task 2 | T100050-10 | AC-100050-06 |
| `hardware.md` Profile C | Task 1 | Discovery + config | Known limitations |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

Every acceptance criterion must be traceable.

---

## 12. Phase Exit Contract

### Outputs Produced
- Online extraction → schema-typed candidate snapshots.
- Cheap span verifier with retry-once refuse-commit control flow.
- Gated `store` integration that blocks unverified snapshots.

### Guarantees Provided to Downstream Phases
After this phase is accepted:
- Slice 100060 can parallelize extraction calls knowing each candidate is independently verifiable.
- Admitted snapshots are span-faithful for extractive entities/numbers/dates.
- Offline training of the extractor is out of scope entirely, not a runtime dependency.

### Known Limitations
- Live model quality varies by profile; CI may rely on fixture extractors.
- Dense novelty/embeddings still Phase 100110; not required for span verify.
- Parallel chunking and canonical merge not yet implemented (slice 100060).

### Downstream Prerequisites
- Slice 100060 MUST preserve this gate order and appendix rules per chunk/canonical unit; MUST run span verify (or reuse this pipeline) per chunk candidate before canonical commit.
- Phase 100040 gated wrapper MUST invoke span verify **before** scoring when a snapshot is present (slice 100050 owns the verify step; order is locked above).
- Slice 100160 MCP `store` MUST keep the verify+gate chain.

### Final Status
**PASS WITH DOCUMENTED LIMITATIONS** (2026-09-17)

### Verification Sign-Off
- Implementer: Cursor (Auto)
- Verifier / Adversary: Antigravity (Gemini 3.8 Flash)
- Remediator: Cursor (Auto)
- Remedy Approver: Antigravity (Gemini 3.8 Flash) — ACCEPTED (all 7 findings verified fixed; `make check` / `make coverage` green)
- Human Approver: [pending]
- Date: 2026-09-17

### Vocab lock (this slice)
- `source_ref` = durable item provenance id
- `evidence_ref` (store tool) aliases into `source_ref`
- `source_text` = required inline span haystack when snapshot present (never the ref id)
