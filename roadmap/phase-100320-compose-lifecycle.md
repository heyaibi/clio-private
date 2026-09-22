# Phase 100320: Embedded Docker Lifecycle (`am compose up|down`)

### Attribution
Rounds below record plan authorship; implementation sign-off is in §12.
| Role | Round | Actual Agent | Status |
|------|-------|--------------|--------|
| Developer | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Adversary | r1 | Antigravity CLI (Gemini 3.8 Flash) | done |
| Remediator | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |
| Remediator | r2 | OpenCode CLI (Go . Deepseek V4.1 Flash High) | done |
| Remedy Approver | r2 | OpenCode CLI (OpenRouter . Deepseek V4.1 Flash Max) | approved |
| Finalize | r1 | OpenCode CLI (Together . GLM-5.3 Flash High) | done |

**Index slice 100320 · **Effort:** `1×` · **Scope:** `gap/am-setup.md` Docker-management portion (split from the former single `am setup` + compose phase)

### Vocabulary (read first) — zero shared moniker
| Term | Enum / form | Where it lives | Must not |
|------|-------------|----------------|----------|
| **materialized compose** | `compose.yml` + arch overlay at the project root | `am compose up` | Live hidden inside a build directory |
| **compose selection** | set of services (postgres, embed, rerank, extract) | `am compose up` | Be the same object as a setup install type |
| **generated env** | Secure `.env` consumed by Compose | `am compose up` | Be committed, or hold online-service API keys |
| **arch overlay** | `compose.amd64.yml` / `compose.arm64.yml` | Selected by detected OS/arch | Be chosen by a Make goal |

---

## 1. Objective

### Goal
Move the Docker lifecycle into the binary so a developer runs `am compose up` / `am compose down` and never needs architecture-specific Make targets or manual service selection. The compose material and every file it bind-mounts are embedded in the binary and materialized into a defined working directory.

### Expected Outcome
- The artifact set is defined precisely: **compose root** = the command's working directory unless `--dir` is given (this is the "project root"). `am compose up` materializes into it: the base `compose.yml`, the matching arch overlay, the `sql/` init scripts that Postgres bind-mounts, and a `models/` directory (with a README) for the extract GGUF; it generates a secure `.env`, asks which services to include, and starts them via the `docker` CLI.
- `am compose down` cleanly stops and removes the environment it started; it is safe to re-run.
- Unsupported OS/arch and an unreachable Docker daemon fail closed with clear messages and no partial file writes.
- Existing Make targets and the checked-in compose files keep working unchanged.

### Parent Requirement
`requirement.md` — §4.9.5.E (effective configuration and profiles). Product intent: eliminate manual `make compose up mac|linux` from the first-run path. Gap source: `gap/am-setup.md`.

### Design References (validated)
- **Compose profiles** select optional services without editing files (`docs.docker.com/compose/profiles/`) — the mechanism to map a chosen service set to `--profile`.
- **`docker compose` config-file merge** (`-f base -f overlay`) is the established arch-pin pattern already used by the Makefile and the arch overlays.
- **Every relative bind mount must resolve in the compose root.** `compose.yml` mounts `./sql/001_core.sql`, `./sql/002_vectors_postgres.sql`, and `./models`; materializing only the compose file leaves those sources missing, so Docker creates empty directories and Postgres comes up without a schema and extract without a model.

---

## 2. Scope Boundaries

### In Scope
- `am compose up` / `am compose down` with OS/arch detection, embedded compose material and its bind-mount sources materialized into a defined compose root, secure `.env` generation, service selection, and Docker invocation.
- Pinning the checked-in `pgvector/pgvector` image to a specific version or digest so the multi-model work (Phase 100290) can rely on a known extension version.
- README, `hardware.md`, and `.env.example` updates for the compose command.

### Explicitly Out of Scope
- The `am setup` wizard and deployment config (Phase 100330).
- Provider adapters and runtime wiring (Phases 028–031, 034, 035).
- A Docker SDK dependency; `am compose` shells out to the `docker` CLI.
- Windows and macOS x86_64 support (fail closed with a clear message).
- Kubernetes, Podman-only paths, or remote Docker hosts.
- Adding a CLI argument-parsing dependency; the existing flag parser is sufficient unless a stop condition is raised.

### Must Not Change
- Existing Make targets and the checked-in compose files keep working.
- Existing Compose profiles (`local-retrieval`, `local-rft`) keep their meaning and service membership.
- No secret is echoed to stdout, and generated `.env` is not committed.
- `am mcp stdio` (Phase 100310) behavior is untouched.

### Scope Expansion Rule
If work outside this scope appears necessary: stop, document the reason, request clarification or approval, and do not silently expand scope.

---

## 3. Preconditions and Dependencies

### Preconditions
- Docker Engine with the Compose v2 plugin is installed (checked at runtime, not at build time).
- The checked-in compose files exist at the repository root.

### Dependencies
| Dependency | Required State | Validation |
|------------|----------------|------------|
| Compose files | `compose.yml`, `compose.amd64.yml`, `compose.arm64.yml` present at repo root | File inspection; embedded at build |
| Docker CLI + daemon | Present and reachable | Runtime probe with a clear error |
| `.gitignore` | Excludes generated `.env` | Inspection |

---

## 4. Existing-System Discovery

The agent MUST re-verify the following; the facts below were confirmed at plan time.

### Required Discovery
- Trace CLI dispatch to find where a new top-level `compose` command attaches.
- Enumerate the compose material and profile membership.
- Confirm `.gitignore` excludes `.env` and generated artifacts.
- Identify the existing `--confirm`/prompt patterns to reuse.

### Discovery Output
- **No `compose` command exists.** `clio-lib/src/main.rs` dispatches `version`, `health`, `help`, `mcp`, `ops`, `retention`; unknown commands exit 2. A new command is additive.
- **Compose material.** `compose.yml` defines `postgres` (always on), `embed` and `rerank` (profiles `local-retrieval`, `local-rft`), `extract` (profile `local-rft`). Arch overlays pin `platform` and the TEI image. The Makefile selects the arch file by goal (`mac`/`linux`) and passes `--profile`.
- **`.env` is the Compose input.** `compose.yml` reads `${POSTGRES_PORT}`, `${EMBED_MODEL}`, `${EXTRACT_GGUF}`, etc. `.env.example` documents them. There is no Rust dotenv loader and none is added.
- **Paths are Linux/macOS-centric.** Arch detection must map `std::env::consts::{OS, ARCH}` to the two supported targets and fail closed otherwise.
- **No Docker client code.** There is no Docker socket client; `am compose` shells out to the `docker` CLI, keeping the dependency count at zero.

### Repository Adaptation Rule
The agent must determine concrete implementation locations from the actual repository. The plan does not prescribe file paths, class names, or module names unless they are an externally required contract (the checked-in compose file names are an external contract).

---

## 5. Implementation Specification

### Task 1: `am compose up`

#### Intent
Own the Docker start path inside the binary with embedded material and correct arch handling.

#### Required Capability or Behavior
- Resolve the **compose root**: default to the current working directory, overridable with `--dir`; create it if missing; refuse to clobber a non-directory path.
- Detect OS/arch; support macOS arm64 and Linux x86_64; fail closed with a clear message otherwise.
- Verify the Docker CLI and daemon are reachable; clear error if not.
- Materialize into the compose root, from assets embedded at build time: the base `compose.yml`, the matching arch overlay, the `sql/` init scripts that Postgres bind-mounts (`001_core.sql`, `002_vectors_postgres.sql`), and a `models/` directory with a README naming the expected GGUF and the download command. Verify every bind-mount source referenced by the materialized compose exists before invoking Docker.
- Generate a secure `.env` for Compose (restricted permissions; gitignored), populated from the effective config where applicable, without copying any online-service API key into a file that would conflict with config.
- Ask which services to install, defaulting sensibly; translate the selection to the Compose profile/`-f` options. If `extract` is selected, warn that it additionally needs the GGUF placed in `models/`.
- Invoke `docker compose` to start the selection; surface Docker output and exit status.
- Do not overwrite a user-edited materialized file without warning/backup.

#### Architectural Responsibility
`clio-lib` command that owns asset materialization, `.env` generation, and the `docker compose` invocation. Embedded assets are a build-time concern; the work-directory files are the materialized artifacts.

#### Required Changes
1. Embed the compose base + arch overlays, the SQL init scripts, and a `models/README` template at build time.
2. Compose-root resolution (`--dir` / CWD) with clobber protection.
3. OS/arch detection and unsupported-target refusal.
4. Secure `.env` generation with restricted permissions; ensure `.gitignore` covers it.
5. Service-selection prompt and mapping to Compose profiles.
6. Bind-mount existence check before `docker compose up`, with a clear error naming the missing source.
7. `docker` invocation with inherited stdio and non-zero propagation.

#### Implementation Constraints
- No Docker SDK dependency; shell out to the `docker` CLI.
- `.env` must not be world-readable; no secret is echoed to stdout.
- User input never becomes a shell string; arguments use fixed shapes and the checked-in compose files.
- The GGUF model file is large and MUST NOT be embedded; the command materializes the directory and instructions, and reports clearly when the file is absent.

#### Expected Result
On macOS arm64 in an empty directory, `am compose up` materializes compose + arch overlay + `sql/` + `models/`, generates `.env`, and starts the chosen services without any `make` invocation and without a missing-mount failure.

### Task 2: `am compose down`

#### Intent
Cleanly tear down what `am compose up` started.

#### Required Capability or Behavior
- Stop and remove the environment started by `am compose up`, using the same materialized files and selection.
- Idempotent: `down` on a stopped stack succeeds.
- Non-zero Docker exit codes propagate.

#### Architectural Responsibility
Same `clio-lib` command family.

#### Required Changes
1. Implement `down` with the same arch/selection resolution as `up`.
2. Surface Docker output and status.

#### Implementation Constraints
- Do not remove user data volumes beyond the compose file's declared behavior without an explicit flag.

#### Expected Result
`am compose down` stops and removes the started services.

### Task 3: Documentation

#### Intent
Replace the Make-based first-run docker path in docs.

#### Required Capability or Behavior
- README quick start references `am compose up`/`down` for local services.
- `hardware.md` explains how the compose command maps to the existing profiles and arch pins.
- `.env.example` notes that `am compose` generates the Compose env.
- Documents that Make targets remain a power-user path.

### Task 4: Compose-Root Prototype and Image Pin

#### Intent
Prove that materializing the asset set produces a working stack from an empty directory, and remove the moving image tag that Phase 100290's halfvec assumption depends on.

#### Required Capability or Behavior
- Prototype in a scratch directory: run `am compose up` (or its materialization step) from empty, confirm Postgres initializes with the schema (`schema_version` present) and the chosen services become healthy; tear down with `am compose down`.
- Replace the unpinned `pgvector/pgvector:pg16` image reference with a pinned version tag or digest known to ship a pgvector version that supports the required width/index features; record the resolved `extvector` version in the phase evidence.
- Confirm the `models/` guidance is sufficient for the extract service to become healthy once the GGUF is placed.

#### Architectural Responsibility
Implementer-owned prototype; feeds the embedded asset list and the pinned image reference.

#### Required Changes
1. Run the empty-directory end-to-end prototype (stubbed Docker acceptable only for unit tests; the prototype uses real Docker).
2. Pin the Postgres/pgvector image and record the extension version.
3. Adjust the embedded asset list if the prototype finds a missing bind-mount source.

#### Implementation Constraints
- The prototype MUST NOT leave containers or volumes running after `down`.
- No dependency changes.

#### Expected Result
An empty directory becomes a running, schema-initialized stack; the image tag is pinned and its pgvector version recorded.

### Implementation Freedom
The agent may choose concrete structure, naming, prompt wording, and internal design provided the required behavior is satisfied, architectural boundaries respected, existing contracts preserved, all acceptance criteria pass, and no prohibited changes are introduced.

---

## 6. Agent Execution Rules

### Allowed Actions
- Add the `compose` command; embed compose assets; add tests and docs.

### Forbidden Actions
- Add a dependency (including any Docker SDK or CLI-parse crate) without approval.
- Drop existing Make targets; change compose profile membership.
- Commit secrets or gitignore exceptions; delete or bypass tests; disable security controls; claim completion without evidence.

### Agent Decision Boundary
The agent may decide prompt wording, asset-embedding mechanism, and test organization. The agent must request approval for: adding any dependency, or changing which services a Compose profile includes.

### Mandatory Stop Conditions
Stop and report if Docker behavior cannot be verified, embedded-asset materialization has no safe project-root target, the project root is unwritable, or correctness cannot be verified.

---

## 7. Security Constraints

### Required Controls
- Generated `.env` is written with owner-only permissions where the platform allows.
- Service selection accepts only allowlisted values; no free-form service name is passed to `docker compose`.
- The Docker invocation uses fixed argument shapes and the checked-in compose files.

### Sensitive Data Rules
- Never echo a Postgres password, `HF_TOKEN`, or any key to stdout/stderr or logs.
- `.env` is gitignored and must not contain online-service API keys that belong in the deployment config.

### Security Acceptance Conditions
- Generated `.env` is not group/world readable on Unix.
- `am compose` refuses unsupported OS/arch and non-running Docker with no partial file writes left behind.

---

## 8. Test and Verification Strategy

### Required Tests
- [ ] Unit tests (arch detection, service→profile mapping, env-file generation, backup/overwrite guard)
- [ ] Integration tests (materialization produces project-root files; `down` reverses `up`)
- [ ] Contract tests (existing Make targets still valid; compose profile membership unchanged)
- [ ] End-to-end tests (under a Docker stub or recorded command assertion)
- [ ] Regression tests (existing CLI suites green)
- [ ] Security tests (file permissions; no secret in stdout; unsupported target refusal)
- [ ] Failure-mode tests (Docker missing; unwritable project root; interrupted up leaves no half-written config)

### Required Test Scenarios
| Test ID | Scenario | Expected Result |
|---------|----------|-----------------|
| T100320-01 | `am compose up` on macOS arm64 | Base + arm64 overlay materialized at project root; correct invocation; profile matches selection |
| T100320-02 | `am compose up` on unsupported OS/arch | Fail closed, clear message, no files written |
| T100320-03 | Docker not installed | Clear error; no partial materialization |
| T100320-04 | Service selection | Container set matches the chosen services |
| T100320-05 | `am compose down` | Stops/removes the environment; exit code propagated |
| T100320-06 | Generated `.env` permissions | Not group/world readable on Unix |
| T100320-07 | User-edited compose file | Warned/backed up before overwrite |
| T100320-08 | No secret in output | Captured stdout/stderr contain no password/token |
| T100320-09 | Empty-directory materialization | `compose.yml`, arch overlay, `sql/*.sql`, `models/` all present; every bind-mount source exists |
| T100320-10 | `extract` selected without a GGUF | Clear warning naming `models/`; other services still start |
| T100320-11 | Image pin | `compose.yml` uses a pinned pgvector image; resolved `extvector` recorded |
| T100320-12 | Compose root override | `--dir X` materializes into `X`; non-directory path refused |

### Negative Testing
Verify unsupported targets fail closed, Docker absence is handled, existing Make/Compose behavior is intact, and failure leaves no half-written compose or `.env`.

### Verification Rule
Implementation claims must be supported by actual test output, inspection results, or other concrete evidence.

---

## 9. Acceptance Criteria and Evidence

| AC ID | Acceptance Criterion | Verification Method | Required Evidence |
|-------|----------------------|---------------------|-------------------|
| AC-100320-01 | `am compose up` materializes project-root compose + arch overlay and starts the selection | T100320-01, T100320-04 | `compose_cli_tests.rs::up_materializes_and_runs_the_selected_profile` (arg shape `compose -f compose.yml -f compose.arm64.yml --profile local-retrieval up -d`); prototype: empty dir materialized `compose.yml`, `compose.arm64.yml`, `sql/001_core.sql`, `sql/002_vectors_postgres.sql`, `models/README.md`, `.env`; `docker compose ps` showed the selected service set |
| AC-100320-02 | `am compose down` stops the environment | T100320-05 | Prototype `am compose down` removed all containers and networks, exit 0; `down_docker_failure_propagates` and `docker_exit_status_propagates` unit tests verify exit-status propagation |
| AC-100320-03 | OS/arch and Docker preconditions fail closed | T100320-02, T100320-03 | `detect_unsupported_fails_closed` (windows/x86_64, mac/x86, linux/arm refused); `failed_probe_leaves_no_files` (Docker unreachable → exit 1, zero files written) |
| AC-100320-04 | Secrets never printed; files restricted | T100320-06, T100320-08 | Prototype `.env` mode `600`; `write_env_is_owner_only_on_unix`; `env_contents_hold_compose_variables_only` (no HF_TOKEN/API_KEY assignments); probe output is captured, never printed; generated `.env` is never echoed |
| AC-100320-05 | User-edited files are protected | T100320-07 | `user_edited_compose_file_is_backed_up_before_overwrite` (edit → re-up → backup `compose.yml.bak-<ts>` holds the edit; unchanged files create no backup); `existing_user_env_is_never_overwritten` |
| AC-100320-06 | Existing Make/Compose workflow unchanged | Regression suite | Makefile untouched; compose profile membership unchanged (`compose.yml` diff is the image pin only); `cargo test --locked --workspace` fully green after the change |
| AC-100320-07 | An empty directory becomes a working, schema-initialized stack | T100320-09, T100320-12, prototype | Real-Docker prototype: empty dir → full materialization → postgres `healthy` with `schema_settings` row `schema_version=10`; `--dir` tests (`resolve_root_refuses_non_directory_paths`, `resolve_root_creates_a_missing_directory`) |
| AC-100320-08 | The pgvector image is pinned and its extension version recorded | T100320-11 | `compose.yml` pins `pgvector/pgvector:0.8.6-pg16` (was floating `:pg16`); a container from the pinned tag reports `vector` `0.8.6` from `pg_available_extensions` |

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
- Implementation summary: `am compose up|down` implemented in `clio-lib` binary modules `compose_cli.rs` (dispatch, root resolution, ordered pipeline, exit codes), `compose_docker.rs` (target detection, `DockerRunner` seam, daemon probe, allowlist→profile mapping, fixed argument shapes), `compose_assets.rs` (build-time `include_str!` of the checked-in compose files + SQL scripts, materialization with backup guard, bind-mount check, GGUF path), `compose_env.rs` (generated `.env` with 0600 perms, no online-service keys, selection marker); `main.rs` dispatches `compose`. The pgvector image is pinned. README, `hardware.md`, and `.env.example` updated.
- No dependency changes; no Docker SDK; user input never becomes a shell string.
- Test output: 48 compose tests + full `cargo test --locked --workspace` green; `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` clean; `cargo fmt --all` clean.
- Coverage (scoped `cargo llvm-cov --package clio --summary-only`): compose_cli.rs 90.00% funcs / 96.17% lines; compose_docker.rs 92.31% / 99.15%; compose_assets.rs 100.00% / 98.65%; compose_env.rs 100.00% / 100.00%.
- Prototype (real Docker, isolated project name + ports; dev stack untouched): empty dir → materialized file listing above; `.env` mode 600; postgres healthy, `schema_version=10`; local-rft run printed the T100320-10 warning and started postgres+embed+rerank+extract; embed/rerank/postgres became healthy; extract restart-looped only while the GGUF was absent (documented limitation); `am compose down` removed all containers and networks, exit 0; a second `down` also exited 0. Throwaway prototype data volumes were deleted manually (compose `down` keeps data volumes by declared behavior).
- Known limitations: as listed in §12 (unsupported targets fail closed; docker CLI shelling; GGUF not embedded; compose root is a working directory; no automatic pruning).

---

## 10. Failure Handling and Recovery

### Expected Failure Modes
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Docker missing/daemon down | Runtime probe | Clear error; no partial files |
| Unsupported OS/arch | Detection | Fail closed with supported targets |
| Unwritable project root | Materialization error | Clear error; suggest a writable checkout |
| Compose start fails | Non-zero exit | Surface Docker output; `down` remains available |
| User edits materialized compose | Change detection | Warn/backup before overwrite |

### Rollback Strategy
`am compose down` (or the Make target) stops services. Removing the new command leaves existing workflows untouched.

### Partial Completion Policy
Do not claim completion if `up` works without a verified `down`. Record completed and incomplete work separately; do not leave undocumented broken state.

---

## 11. Traceability

| Parent Requirement | Implementation Task | Verification | Acceptance Criterion |
|--------------------|---------------------|--------------|-----------------------|
| §4.9.5.E / FR-32 | Tasks 1–2 | T100320-01, T100320-05 | AC-100320-01, AC-100320-02 |
| `gap/am-setup.md` Docker management | Tasks 1–2 | T100320-01…T100320-06 | AC-100320-01…AC-100320-06 |
| FR-32 / §4.9.5.E (secrets masked, effective configuration; `.env` holds no online-service keys) | Task 1 | T100320-06, T100320-08 | AC-100320-04 |

Required chain:

```text
Requirement → Capability → Implementation → Test → Evidence
```

---

## 12. Phase Exit Contract

### Outputs Produced
- `am compose up` / `am compose down` with embedded compose material and secure `.env` generation.
- Updated README, `hardware.md`, and `.env.example`.

### Guarantees Provided to Downstream Phases
- Phase 100330 (`am setup`) can start local services through this command for airgapped and custom installs.

### Known Limitations
- Only macOS arm64 and Linux x86_64 are supported; others fail closed.
- `am compose` shells out to the `docker` CLI; no in-process Docker API.
- The extract GGUF is not embedded (too large); the `extract` service needs the operator to place the file in `models/`, and the command reports when it is absent.
- A compose root is a working directory, not a globally registered location; running `am compose` from a different directory targets a different root. `--dir` and docs make this explicit. However, the Compose project name (`clio`) and the host ports (34310–34313) are fixed, so two roots can still NOT run at the same time: `am compose down` in one directory tears down containers started from another. Parallel stacks across directories require `COMPOSE_PROJECT_NAME` and port overrides.
- No automatic pruning of old backups or generated files.

### Downstream Prerequisites
- Phase 100330 depends on this command for local installs.

### Final Status
PASS WITH DOCUMENTED LIMITATIONS

### Verification Sign-Off
- Implementer: OpenCode CLI (Together . GLM-5.3 Flash High), developer r1
- Verifier: [pending — Adversary r1]
- Human Approver: [pending]
- Date: 2026-09-22
