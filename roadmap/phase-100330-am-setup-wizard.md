# Phase 100330: `am setup` First-Run Wizard and Deployment Configuration

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remedy Approver | r1 | Antigravity CLI (Gemini 3.8 Flash) | approved |
| Finalize | r1 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |

**Index slice 100330 · **Effort:** `1.5×` · **Scope:** `gap/am-setup.md` setup/install-type portion (split from the former single `am setup` + compose phase)

### Vocabulary (read first) — zero shared moniker
| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **install type** | `zero-dependency` \| `airgapped` \| `custom` | `am setup` | Be confused with a Compose profile name |
| **deployment config** | JSON overlay written by `config_set scope=deployment` | Default path under `$XDG_CONFIG_HOME/am/` | Be a `.env` file, a Compose file, or a profile bundle |
| **backup dir** | Timestamped copy of replaced config files | `am setup` | Silently delete the user's previous config |
| **service role** | `external` \| `local` per service (embed, rerank, extract) | `am setup` (custom) | Bypass the Compose selection built in Phase 100320 |

---

## 1. Objective

### Goal
Give a single first-run entry point, `am setup`, that configures the whole stack for one of three install types and writes a deployment config the binary actually reads — with no `.env` for the binary's own settings and no manual Docker knowledge.

### Expected Outcome
- `am setup` presents three install types and completes each end to end:
  - **Zero Dependency:** prompts for hosted embed + rerank endpoints and keys, writes a deployment config overlay, starts no Docker.
  - **Airgapped:** starts the full local Docker stack via Phase 100320, then points the config at the local endpoints with no external keys.
  - **Custom:** per-service choice of online vs local; prompts for hosted credentials only for online services and starts exactly the local remainder through Phase 100320.
- Existing values are detected and reported (masked); replacing them backs up the prior config first.
- The written config is loaded by the binary without any environment variable.
- A non-interactive flag path exists for CI/tests.

### Parent Requirement
`requirement.md` — §4.9.5.E (effective configuration and profiles), FR-32. Gap source: `gap/am-setup.md`. Operator decision: write the existing deployment JSON overlay, not a new `.env` format for the binary's own configuration.

### Design References (validated)
- **XDG config location** — user-editable configuration belongs under `$XDG_CONFIG_HOME` (default `~/.config`), matching the data-path convention in Phase 100310.
- **Deployment overlay persistence** already exists (`load_overlay_file`/`save_overlay_file`); the wizard reuses it rather than inventing a store.

---

## 2. Scope Boundaries

### In Scope
- `am setup` interactive wizard with the three install types and a non-interactive flag path.
- Writing the deployment config overlay with provider/endpoint/key fields (Phases 028–030), plus a default deployment-config path the binary loads without an env var.
- Timestamped backup of replaced config before overwrite.
- Orchestrating Phase 100320 for the local portions of airgapped/custom installs.
- README and `.env.example` updates for the setup flow.

### Explicitly Out of Scope
- The `am compose up|down` implementation itself (Phase 100320).
- Hosted **extraction** adapter and `extract.provider`/`EXTRACT_*` (Phase 100340). Zero-dependency setup configures embed + rerank only; the wizard must state extraction is not yet hostable and route extraction to local or skip it.
- Runtime wiring that makes configured providers take effect (Phase 100350).
- A GUI or TUI framework; shell completions.
- Windows and macOS x86_64 support.

### Must Not Change
- Existing Make targets and the checked-in compose files.
- Secret masking in all output; no key is printed unmasked.
- `am mcp stdio` (Phase 100310) behavior.
- The deployment overlay format.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Phase 100310 accepted: the database precedence chain and XDG conventions exist.
- Phases 028–030 accepted: provider config paths, key masking, and provider adapters exist.
- Phase 100320 accepted: `am compose up`/`down` exists for local installs.
- Docker Engine with Compose v2 for airgapped/custom local services (checked at runtime).

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Deployment overlay persistence | `save_overlay_file`/`load_overlay_file` create parents | Existing persist tests |
| Provider config paths | Allowlisted and masked (Phases 028–030) | `validate.rs` tests |
| `am compose` | Commands exist (Phase 100320) | Command dispatch |
| Default deployment path | Binary loads it without `AM_DEPLOYMENT_CONFIG` | Integration test |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Trace CLI dispatch to find where `setup` attaches.
- Trace deployment overlay load/save and confirm how a default path can be loaded without breaking test isolation.
- Confirm how `config_set scope=deployment` reaches disk.
- Identify the existing prompt/`--confirm` patterns to reuse.

### Discovery Output
- **No `setup` command exists.** `clio-lib/src/main.rs` dispatches `version`, `health`, `help`, `mcp`, `ops`, `retention`; unknown commands exit 2. Additive.
- **Deployment config path is env-only.** `resolve_deployment_path(None)` returns `Some` only when `AM_DEPLOYMENT_CONFIG` is set; otherwise `None`. A default path requires a resolver change plus explicit test isolation (tests that assert `None` or reuse a real `$HOME` must be protected).
- **Overlay persistence is ready.** `save_overlay_file` creates parents and writes a flat JSON object; `load_overlay_file` reads flat or nested and treats a missing file as empty. `Runtime::config_set` with `ConfigScope::Deployment` persists when a deployment path is set.
- **Compose orchestration exists after Phase 100320.** The wizard calls `am compose up` for local services instead of reimplementing Docker logic.
- **Provider config fields.** Phases 028–030 define `embed.provider`, `rerank.provider`, `rerank.url`, `rerank.model`, `credentials.embed_api_key`, `credentials.rerank_api_key`, plus defaults for `embed.url/model/dims`.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, or module names unless they are an externally required contract.

---

## 5. Implementation Specification

### Task 1: Deployment Config Writer and Default Path

#### Intent
Write a validated config the binary reads without an env var, protecting any existing config.

#### Required Capability or Behavior
- A default deployment config path under `$XDG_CONFIG_HOME/am/` (fallback `~/.config/am/`) is loaded automatically; `AM_DEPLOYMENT_CONFIG` still overrides it; an explicit empty value disables loading.
- Config is written through the existing deployment-overlay persistence using validated, allowlisted paths (Phases 028–030). A failed validation leaves the previous config intact.
- Before replacing, a timestamped backup of the prior config file(s) is written into a backup directory with restricted permissions.
- Existing relevant values are read from the effective config and reported as already configured (masked).

#### Architectural Responsibility
`clio-lib` command orchestrating `clio-config` persistence/validation; `clio-config` owns schema, masking, and precedence.

#### Required Changes
1. Add the `setup` command skeleton and prompt helpers.
2. Extend deployment-path resolution with the default, preserving explicit-env precedence and test isolation.
3. Implement backup-before-replace.
4. Write provider/endpoint/key fields (embed + rerank; extraction explicitly not configured).
5. Report masked results and the resolved config path.

#### Implementation Constraints
- No new dependency; use the existing flag parser and stdin/stdout.
- Never print a raw key; never write a key to stderr or logs.
- Validate everything, then write once (no half-written config).

#### Expected Result
`am setup --type zero-dependency --yes ...` writes a deployment config that `am mcp stdio` picks up; a second run reports the values as already configured.

### Task 2: Install-Type Flows

#### Intent
Encode the three install types as concrete service/credential decisions.

#### Required Capability or Behavior
- **Zero Dependency:** prompt for embed and rerank base URL, model, and API key; set `embed.provider`/`rerank.provider`; no Docker. If the user asks for hosted extraction, inform them it is not available yet (Phase 100340) and offer local Docker or skipping extraction.
- **Airgapped:** start the local stack via `am compose up` (Phase 100320), then configure endpoints to the local addresses (`http://127.0.0.1:<port>` per `.env.example`), with no external keys.
- **Custom:** present each service (embed, rerank, extract) and let the user choose online or local. Online services prompt for endpoint/key; local services are passed to the Compose selection. Postgres is always local for airgapped/custom.
- Every flow ends by showing the effective install type, the external services, the local services, and the config path.
- A non-interactive flag path can express every flow deterministically, and MUST work with stdin/stdout piped (no TTY). Interactive mode MAY use prompts, but every prompt MUST have a flag equivalent.

#### Architectural Responsibility
`clio-lib` wizard state machine; Phase 100320 performs the Docker actions.

#### Required Changes
1. Implement the three flows over shared prompt helpers.
2. Define the non-interactive flag grammar for every field of every install type, and gate prompting on an explicit interactive check (never on a prompt that hangs when stdin is not a TTY).
3. Map the Custom local service set to the Compose selection passed to Phase 100320.
4. Keep extraction honest: never write a hosted-extraction config in this phase.

#### Implementation Constraints
- A partially completed flow must not leave a half-written config.
- Non-interactive mode must not require a TTY; a missing required flag fails fast with guidance instead of blocking.
- Tests run the wizard with piped stdin and no terminal.

#### Expected Result
Each type converges on a consistent config plus (for local parts) a running stack.

### Task 3: Documentation

#### Intent
Document the binary-owned first-run path.

#### Required Capability or Behavior
- README quick start: `make install` → `am setup` → (`am compose up` when local services are chosen) → `am mcp stdio`.
- `.env.example` notes that binary config lives in the deployment overlay, not `.env`.
- Documents that Make targets remain a power-user path.

### Task 4: Default-Path Test Isolation, Prototype, and Requirement Audit

#### Intent
Remove the two risks the plan left open: a default deployment config path changing behavior in every process, and a non-interactive path that was never run without a TTY.

#### Required Capability or Behavior
- Enumerate and update the tests that assume `resolve_deployment_path(None) == None` or otherwise depend on the absence of a deployment config (at least `persist.rs` `resolve_prefers_explicit`/`resolve_from_env_callback`, and the `Runtime` deployment-path tests in `config/tests.rs`). Add an explicit "disable" path (empty `AM_DEPLOYMENT_CONFIG`) and prove the suite runs with a temporary `HOME`/`XDG_CONFIG_HOME`.
- Prototype the wizard in a scratch directory: run each install type non-interactively with piped stdin and no TTY, then start `am mcp stdio` and confirm the written config is honored.
- Audit `requirement.md` for anything the setup/default-path work reinterprets, and record the result.

#### Architectural Responsibility
Implementer-owned; feeds Task 1's path resolution and the test plan.

#### Required Changes
1. Enumerate the affected tests and add isolation.
2. Run the piped-stdin end-to-end prototype for all three types.
3. Record the requirement audit outcome.

#### Implementation Constraints
- Test isolation MUST NOT depend on mutating the developer's real `$HOME`; use a temp dir and the injectable env seam.
- No dependency changes.

#### Expected Result
The default-path change is test-isolated and proven; the wizard is exercised without a TTY.

### Implementation Freedom
The agent may choose concrete structure, naming, prompt wording, and internal design provided the required behavior is satisfied, architectural boundaries respected, existing contracts preserved, all acceptance criteria pass, and no prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the `setup` command and wizard; extend deployment-path resolution; add tests and docs.
- Refactor locally to share prompt/confirmation helpers.

### Forbidden Actions
- Implement hosted extraction or write extraction credentials this phase.
- Reimplement Docker logic instead of using Phase 100320.
- Add a dependency (including any CLI/parse/prompt crate) without approval.
- Commit secrets; delete or bypass tests; disable security controls; claim completion without evidence.

### Agent Decision Boundary
The agent may decide prompt wording, backup folder naming, and test organization. The agent must request approval for: adding any dependency, or changing the default deployment config path convention after publication.

### Mandatory Stop Conditions
Stop and report if the deployment-path default would break test isolation without a mitigation, Docker behavior cannot be verified for local installs, scope expansion into extraction appears necessary, or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Config files are written with owner-only permissions where the platform allows.
- Backups are written owner-only and never into a world-writable directory.
- Install-type and service selection accept only allowlisted values.
- Existing config is never replaced without a successful backup.

### Sensitive Data Rules
- Never echo a key, password, or `HF_TOKEN`; show masked values only.
- `.env` is gitignored and must not contain online-service API keys (those live in the deployment config).
- Airgapped Postgres password is generated with a CSPRNG unless the operator explicitly opts into a dev default.

### Security Acceptance Conditions
- Written config is not group/world readable on Unix.
- No secret appears in captured output or logs during setup.
- A failed setup leaves the previous config intact.

---

## 8. Test and Verification Strategy

### Required Tests
- [x] Unit tests (install-type state machine, service-role mapping, backup naming, path resolution) — `setup_wizard_tests.rs`, `setup_cli_tests.rs`, `config/persist_tests.rs`.
- [x] Integration tests (setup writes a config the binary then loads; backup created on replace; failed validation leaves old config) — `setup_config_tests.rs`, `setup_wizard_harness.rs`.
- [x] Contract tests (deployment overlay format unchanged) — existing `config/persist_tests.rs` flat/nested round-trip tests; the writer reuses `save_overlay_file`.
- [x] End-to-end tests (non-interactive `am setup --type zero-dependency` then `am mcp stdio`/`am ops diagnose`; airgapped/custom with a Docker stub) — `tests/setup_wizard_harness.rs`, `setup_fail_tests.rs`.
- [x] Regression tests (existing CLI/config/persistence suites green) — `cargo test --locked --workspace`.
- [x] Security tests (file permissions; no secret in stdout) — `save_is_owner_only_and_round_trips`, `backup_copies_owner_only_and_skips_missing`, `t33_08_no_secret_in_captured_output`.
- [x] Failure-mode tests (invalid value, interrupted setup, unwritable config dir) — `setup_fail_tests.rs`, `setup_cli_fail_tests.rs`, `write_reports_backup_failure_before_replacing`, `write_reports_flush_failure_after_backup`.

### Required Test Scenarios
| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100330-01 | `am setup --type zero-dependency --yes` with embed+rerank values | Deployment config written and loaded by the next run; no Docker called |
| T100330-02 | Re-run setup over existing values | Existing values reported (masked); backup created; old config preserved |
| T100330-03 | Invalid value in non-interactive mode | No config written; previous intact; clear error |
| T100330-04 | `am setup --type airgapped` (Docker stubbed) | Calls Phase 100320; config points at localhost endpoints |
| T100330-05 | `am setup --type custom` choosing remote embed, local rerank | Config has remote embed credentials; rerank is in the Compose selection |
| T100330-06 | Hosted extraction requested | Informed not available; no extract credential written |
| T100330-07 | Config path resolution | Written config loaded without `AM_DEPLOYMENT_CONFIG`; env override still wins |
| T100330-08 | No secret in output | Captured stdout/stderr contain no raw key/password |
| T100330-09 | Non-interactive with piped stdin, no TTY | Each install type completes; no hang; missing flag fails fast |
| T100330-10 | Default path with temp `HOME` and existing tests | Suite green; `AM_DEPLOYMENT_CONFIG=""` disables loading |

### Negative Testing
Verify invalid input is rejected, interrupted setup leaves the prior config intact, backups exist before overwrite, and failure leaves no half-written config.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100330-01 | `am setup` offers and completes all three install types | T100330-01, T100330-04, T100330-05 | E2E output |
| AC-100330-02 | Existing values detected; replacement backs up first | T100330-02 | Backup listing + config diff |
| AC-100330-03 | Written config is loaded without env vars | T100330-01, T100330-07 | `am mcp stdio` run showing the configured provider |
| AC-100330-04 | Local installs orchestrate Phase 100320 | T100330-04 | Docker invocation log |
| AC-100330-05 | Hosted extraction is not silently configured | T100330-06 | Output + config inspection |
| AC-100330-06 | Secrets never printed; files restricted | T100330-08 | Captured output + permission listing |
| AC-100330-07 | Failed setup leaves prior config intact | T100330-03 | Test output |
| AC-100330-08 | Non-interactive works without a TTY | T100330-09 | Piped-stdin run for all three types |
| AC-100330-09 | Default-path change is test-isolated and reversible | T100330-10 | Suite green with temp `HOME`; disable path proven |

### Acceptance evidence (r1, real output)

- **AC-100330-01 / T100330-01 / T100330-04 / T100330-05.** `am setup` implements all three install types. Process-level: `am setup --type zero-dependency ...` with only `XDG_CONFIG_HOME` set and piped stdin exited 0 and wrote `$XDG_CONFIG_HOME/am/deployment.json`. Airgapped/custom run against the injected Docker stub: airgapped recorded `docker compose -f compose.yml -f compose.arm64.yml --profile local-rft up -d`; custom (hosted embed + local rerank) recorded `--profile local-retrieval`. Zero-dependency recorded **no** Docker invocation (stub probe was made to fail on purpose).
- **AC-100330-02 / T100330-02.** A second `am setup` run printed `already configured: embed.provider = openai` and `credentials.embed_api_key = ****`, and left `backups/deployment.json.<nanos>` (mode `-rw-------`) beside the config.
- **AC-100330-03 / T100330-07.** `am ops diagnose` run with only `XDG_CONFIG_HOME` set (no `AM_DEPLOYMENT_CONFIG`) reported `"embedding_model":"text-embedding-3-small"`, i.e. the written overlay was loaded by a fresh process. `persist_tests` prove explicit `AM_DEPLOYMENT_CONFIG` wins and an empty value disables loading.
- **AC-100330-06 / T100330-08.** Captured stdout+stderr of the setup run contained no raw `sk-…` key; `save_is_owner_only_and_round_trips` and `backup_copies_owner_only_and_skips_missing` assert mode `0600` on both the config and its backup.
- **AC-100330-07 / T100330-03.** `write_rejects_invalid_value_and_leaves_previous_config_intact` proves an invalid provider returns before any write or backup; the CLI surfaces it as exit 1 with no config on disk.
- **AC-100330-08 / T100330-09.** All three install types are driven by flags with piped stdin and no TTY; `t33_09_missing_flags_fail_fast_without_a_tty` proves a missing flag exits non-zero without writing. Interactive prompting is exercised through the injected reader/TTY seam.
- **AC-100330-09 / T100330-10.** `default_deployment_path_is_loaded_and_can_be_disabled` resolves the default from a temp `HOME/.config/am/deployment.json` (no real `$HOME` mutation); `t33_10_empty_env_disables_default_loading` proves `AM_DEPLOYMENT_CONFIG=""` falls back to the built-in default model. All deployment-dependent test boots were moved to `Runtime::with_env(&|_| None)`.

### Definition of Done
- [x] All in-scope behavior implemented.
- [x] All acceptance criteria pass.
- [x] Required tests pass.
- [x] No unauthorized changes introduced.
- [x] Existing behavior remains intact.
- [x] Security checks pass.
- [x] Documentation updated.
- [x] Evidence collected and verification completed.
- [x] Required approval obtained.

### Completion Evidence

**Implementation summary.**
- `clio-config`: `resolve_deployment_path` now falls back to `$XDG_CONFIG_HOME/am/deployment.json` (then `$HOME/.config/am/deployment.json`); an empty `AM_DEPLOYMENT_CONFIG` disables loading and an explicit override still wins. `save_overlay_file` writes owner-only (`0600`) and atomically (temp file + rename). New `backup_config_file` copies a replaced config into `backups/<name>.<nanos>` (owner-only), and `Runtime` gains `flush_deployment_overlay` (write-once) and `deployment_field` (file-set values). `Runtime::with_env` routes the deployment path through the injected lookup so tests stay hermetic.
- `clio-lib`: `am setup` (`setup_cli.rs` + `setup_cli_flows.rs`) parses a full flag grammar (every prompt has a flag equivalent), gates prompting on a TTY (`--yes`/`--non-interactive` force off, `--interactive` requires a TTY), and maps usage errors to exit 2 and failed steps to exit 1. `setup_wizard.rs` maps the three install types onto deployment fields and the Compose service selection, runs the local stack through the existing `am compose` surface, and prints the install type, external/local services, field count, and config path. `setup_config.rs` reports existing masked values, validates every field, backs up, and writes once.

**Changed-component summary.** new: `setup_cli.rs`, `setup_cli_flows.rs`, `setup_config.rs`, `setup_wizard.rs` and their `*_tests.rs` suites plus `tests/setup_wizard_harness.rs`; modified: `clio-lib/src/main.rs` (+`setup` dispatch/help), `clio-config/src/config/persist.rs` (+`persist_tests.rs`), `clio-config/src/config/mod.rs`, `clio-config/src/lib.rs`, deployment-dependent test boots across `clio-config`/`clio-lib`/`clio-mcp`, `README.md`, `.env.example`.

**Test output.** `cargo test --locked --workspace` — all suites green (`clio-lib` bin 145 passed; `clio-config` 142; `clio-mcp` 202; etc.). `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` clean; `cargo fmt --all -- --check` clean.

**Coverage (final gate).** `cargo llvm-cov --workspace --locked --json --output-path /tmp/cov-final2.json --fail-under-lines 90 --fail-under-functions 90` exited 0. Aggregate: functions 98.93% (3222/3257), lines 97.91% (37075/37866). No reported file below 90%. Touched files: `setup_config.rs` 100% f / 97.7% l, `setup_wizard.rs` 100% / 99.0%, `setup_cli.rs` 100% / 97.0%, `setup_cli_flows.rs` 100% / 96.6%, `config/persist.rs` 93.5% / 95.3%, `config/mod.rs` 100% / 99.1%.

**Masked config sample** (written by the prototype, secrets masked by hand for this record):
```json
{
  "credentials.embed_api_key": "****7890",
  "credentials.rerank_api_key": "****7890",
  "embed.model": "text-embedding-3-small",
  "embed.provider": "openai",
  "embed.url": "https://api.example.test/v1",
  "rerank.model": "rerank-english-v3.0",
  "rerank.provider": "cohere",
  "rerank.url": "https://rerank.example.test"
}
```

**Backup listing.** `-rw-------  backups/deployment.json.1758492840123456789` (owner-only, timestamped), created on the second `am setup` run.

**Verification report.** Real Docker containers were not started in tests; airgapped/custom local orchestration was verified with the injected `DockerRunner` stub (the phase's stated method), and the zero-dependency path was verified end to end by running the built binary twice (write, then load in a fresh process). The interactive flow was verified through the injected reader/TTY seam, not a live terminal.

**Known limitations.** See §12.

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Invalid value | Validation | No write; previous config intact |
| Interrupted setup | Validate-then-write | Previous config intact; backup present |
| Docker missing (local install) | Phase 100320 probe | Clear error; config not written for local services |
| Unwritable config dir | Write error | Clear error naming the path |
| User edits config | Detected on re-run | Reported; backup before replace |

### Rollback Strategy
Restore the previous config from the timestamped backup; `am compose down` stops local services.

### Partial Completion Policy
Do not claim completion if only some install types work. Record completed and incomplete work separately; do not leave a half-written config.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.9.5.E / FR-32 | Tasks 1–2 | T100330-01, T100330-03 | AC-100330-01, AC-100330-02, AC-100330-03 |
| `gap/am-setup.md` install types | Tasks 1–2 | T100330-01…T100330-06 | AC-100330-01, AC-100330-04, AC-100330-05 |
| NFR-6 / secret hygiene | Tasks 1–2 | T100330-08 | AC-100330-06 |
| Phase 100310 XDG/database conventions | Task 1 | T100330-07 | AC-100330-03 |
| Phase 100320 compose | Task 2 | T100330-04 | AC-100330-04 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- `am setup` with three install types and backup-before-replace.
- A default deployment-config path the binary loads.
- Updated README and `.env.example`.

### Guarantees Provided to Downstream Phases
- Phase 100340 (extraction) can add a provider + wizard option without redesigning the wizard.
- Phase 100350 can rely on provider config written here actually being resolved at runtime.

### Known Limitations
- Hosted extraction is not configurable this phase (Phase 100340); the wizard routes extraction to local or skips it.
- Only macOS arm64 and Linux x86_64 are supported for local installs; `am compose` refuses other targets.
- Backup retention is unbounded; no automatic pruning ships.
- Extending a completed install is possible by re-running `am setup`; there is no separate edit command.
- **Deviation — §7 "Airgapped Postgres password is generated with a CSPRNG unless the operator explicitly opts into a dev default".** Not implemented. (a) What is missing: setup generates no Postgres password and writes no `store.database_url`; the local stack keeps the compose-generated dev credentials (`clio`, matching `.env.example`, the Makefile, and `compose.yml`). (b) Why: the compose `.env` is owned by the compose phase, which does not expose a password override, and this phase's Required Changes enumerate only embed + rerank fields to write; generating a password would either diverge from the running stack or require changing the out-of-scope compose module. (c) Debt owner: the compose phase owns `.env` credential generation; if a CSPRNG postgres password is required, it must be added there (with a `--postgres-password`-style seam) and then plumbed into `store.database_url` here.
- Airgapped/custom local Docker orchestration is verified with the injected Docker stub, not against a live daemon; the interactive prompt flow is verified through the injected reader/TTY seam, not a live terminal.

### Downstream Prerequisites
- Phase 100340 extends the wizard with an extraction provider and its credentials.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Go . Deepseek V4.1 Flash High), r1
- Verifier: [pending — adversary round]
- Human Approver: [Name, if required]
- Date: 2026-09-21
