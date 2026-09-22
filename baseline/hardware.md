# Clio — Hardware & Deployment Profiles

**Document status:** Planning · **Version:** 1.3 · **Companion to:** `requirement.md` v1.6

This document defines three supported deployment profiles for the Clio Rust CLI (by Agent Memoir). Profiles differ by what runs locally versus via API. Behavioral requirements in `requirement.md` are identical across profiles; only the inference and storage placement changes.

**Normative language:** MUST / SHOULD / MAY follow the same conventions as `requirement.md`.

---

## Shared assumptions (all profiles)

| Component | Placement |
|---|---|
| Clio CLI | Source in this repo (Rust binary you build); not a Compose service |
| Persistence | **PostgreSQL with `pgvector`** (Compose sidecar by default; external Postgres MAY be used) |
| SQLite | Supported as a zero-Docker alternative; not the Compose default |
| Embed / rerank / extract | Compose sidecars only when the profile includes them — **not** host-installed model servers |

The CLI talks to embed, rerank, and LLM endpoints through configurable base URLs. Switching a profile is configuration only; it MUST NOT fork product behavior.

Local sidecars can be replaced by hosted providers: the transport accepts `https://` endpoints with certificate verification always on, and the config carries `embed.provider` (`tei`|`openai`) / `rerank.provider` (`tei`|`cohere`) plus per-service API keys (`EMBED_API_KEY` / `RERANK_API_KEY`, masked in `config_get`). The embed adapters are wired: `tei` posts `{embed.url}/embed`, `openai` posts `{embed.url}/v1/embeddings` at the configured `embed.dims`. Rerank adapters are wired and attached at runtime: a configured `rerank.url` makes `retrieve`/`compose_context` report `reranked: true`, and leaving it unset keeps retrieval unchanged. The local sidecar setups below remain the default.

Extraction is opt-in between local and hosted: `extract.provider = "template"` (the default) keeps the Compose NuExtract sidecar; `extract.provider = "openai"` switches to a hosted OpenAI-compatible `/v1/chat/completions` adapter (`EXTRACT_URL` = API base URL, `EXTRACT_MODEL` = chat model id, `EXTRACT_API_KEY` = required bearer key, all masked in `config_get`). **Egress note:** with `extract.provider = "openai"`, source text leaves the process for a third party (inline `key: secret` pairs are scrubbed first; there is no per-field redaction). Prompt-based extraction is expected to be less reliable than the fine-tuned NuExtract model — the span verifier rejects ungrounded snapshots, so recall may drop before precision does. For airgapped deployments, stay on `template`.

**Index pipeline placement.** The runtime drains the durable `index_pending` outbox in bounded background batches (a post-write nudge plus a periodic sweep), so a stored item becomes retrievable without `clio ops reindex` and the write response never waits on the embed/rerank endpoint. Both profiles support a **lexical-only** fallback: with no `embed.url`, lexical indexing still drains and `maintenance_status.index.dense_available` reports `false`, so retrieval is never silently empty. Profile A (hosted embeddings) and Profiles B/C (local embed sidecar) differ only in where the dense vectors come from; the drain contract is identical.

### Switching the embedding model

The default space is unchanged: `BAAI/bge-small-en-v1.5` at 384 dimensions, and an existing 384 database opens without a rebuild. To adopt a different model, set `embed.model` + `embed.dims` together, opt in with `embed.switch_space = true`, and run `clio ops reindex --target dense --confirm`. Only derived vectors are dropped and rebuilt; item content and every non-vector table are untouched. Without the opt-in, opening with a mismatched space fails closed.

Widths are bounded by the storage engine. Postgres/pgvector: up to 2000 dims uses a plain `vector` HNSW index; 2001–4000 uses a `halfvec` expression index (pgvector ≥ 0.7.0, checked at open); 4001–16000 falls back to exact scan; above 16000 is rejected. SQLite/`sqlite-vec` always serves exact KNN. `clio ops diagnose` reports the active `embedding_model`, `embedding_dims`, and `index_mode`. Example widths: OpenAI `text-embedding-3-small` = 1536 (plain `vector`), a 3072-dim model = `halfvec` index, Qwen3-Embedding-8B = 4096 (exact scan).

**Compose default data plane:** when `docker compose up -d` is used, prefer **pgvector in Docker**, not SQLite.

---

## Profile A — CLI + local pgvector + API inference

**Name:** `api-inference`  
**Target:** any machine that can run Docker (or an external Postgres) and reach LLM / embed / rerank APIs.

### Runs locally

| Service | Notes |
|---|---|
| Clio CLI | Rust binary |
| PostgreSQL + `pgvector` | Compose sidecar or external managed Postgres |

### Runs via API keys

| Capability | Notes |
|---|---|
| LLM (extraction, gist, failure lessons, host agent) | Provider API (OpenAI / Anthropic / Gemini / compatible) |
| Embeddings | Provider embedding API |
| Reranker | Provider rerank API (or omit if hybrid retrieve uses dense+lexical only) |

### Minimum hardware

| Resource | Guidance |
|---|---|
| vCPU | 1+ |
| RAM | 2 GB+ free for CLI + slim Postgres (`shared_buffers` capped) |
| Disk | Postgres volume + binary |

### When to use

- Lowest local footprint
- Best extraction / answer quality (frontier APIs)
- Laptops and CI that should not load ONNX models

### Compose sketch

```text
services: postgres (pgvector)
env: DATABASE_URL, LLM_API_*, EMBED_API_*, RERANK_API_*
```

---

## Profile B — Local retrieve stack + API LLM

**Name:** `local-retrieval`  
**Target:** **2 vCPU · 8 GB RAM** (or better).

### Runs locally

| Service | Model / image | Approx. RAM |
|---|---|---|
| Clio CLI | Rust binary | ~0.2–0.4 GB |
| PostgreSQL + `pgvector` | slim Compose Postgres | ~0.2–0.4 GB (capped) |
| Embedder | `BAAI/bge-small-en-v1.5` · **dim 384** | ~0.25–0.3 GB |
| Reranker | `Alibaba-NLP/gte-multilingual-reranker-base` (~306M); Compose TEI serves **`onnx-community/gte-multilingual-reranker-base`** (same model + ONNX for TEI CPU/ORT) | ~0.6–0.9 GB |

### Runs via API keys

| Capability | Notes |
|---|---|
| LLM | Required — extraction, gist, lessons, host agent stay on provider APIs |

### Hardware budget (2 vCPU · 8 GB)

| Piece | Approx. |
|---|---|
| OS + Docker | ~1–1.5 GB |
| CLI + pgvector + embed + rerank | ~1.5–2.5 GB |
| Headroom | ~3–4 GB |

**2 vCPU note:** embed and rerank share cores. Cap rerank candidates (e.g. top 30–50) and token lengths so p95 stays acceptable. Compose MUST set TEI `--max-batch-tokens` well below the default `16384` (we use `2048`) or CPU ORT warmup OOMs — see TEI issues #819 / #280.

### When to use

- Offline or private retrieval / ranking
- Still want frontier LLM quality for extraction and answers
- Default recommended laptop profile for coding agents

### Compose sketch

```text
services: postgres (pgvector), embed (bge-small-en-v1.5), rerank (gte-multilingual-reranker-base)
env: DATABASE_URL, EMBED_URL, RERANK_URL, LLM_API_*
```

---

## Profile C — Local retrieve stack + local NuExtract extractor

**Name:** `local-rft`  
**Target:** **4 vCPU · 12 GB RAM** (or better).

### Runs locally

| Service | Model / image | Approx. RAM |
|---|---|---|
| Clio CLI | Rust binary | ~0.2–0.4 GB |
| PostgreSQL + `pgvector` | slim Compose Postgres | ~0.2–0.4 GB (capped) |
| Embedder | `BAAI/bge-small-en-v1.5` · **dim 384** | ~0.25–0.3 GB |
| Reranker | `Alibaba-NLP/gte-multilingual-reranker-base` (~306M); Compose TEI serves **`onnx-community/gte-multilingual-reranker-base`** (same model + ONNX for TEI CPU/ORT) | ~0.6–0.9 GB |
| Local extractor | **`numind/NuExtract-1.5-tiny`** (Qwen2.5-0.5B fine-tune for template→JSON extraction) | **~0.6–1.0 GB** (Q4_K_M GGUF ≈ 0.3 GB on disk) |

### Optional via API keys

| Capability | Notes |
|---|---|
| Host companion / coding agent LLM | MAY remain on API for answer quality while extraction stays local |
| Fallback extractor | MAY fall back to API if local extract fails verification twice (`requirement.md` FR-4) |

### Hardware budget (4 vCPU · 12 GB)

| Piece | Approx. |
|---|---|
| OS + Docker | ~1–1.5 GB |
| CLI + pgvector + embed + rerank | ~1.5–2.5 GB |
| `NuExtract-1.5-tiny` | ~0.6–1.0 GB |
| Headroom | **~6–8 GB** |

**4 vCPU note:** pin extractor threads (e.g. leave 1 core free for Postgres/embed) so the host stays responsive. Keep context short (e.g. 2k–4k). Structural maintenance stays background (PR-9).

### Extractor constraints (normative intent)

- **Default local extractor is `numind/NuExtract-1.5-tiny`.** Runs as the Compose `extract` service (`ghcr.io/ggml-org/llama.cpp:server` + GGUF Q4_K_M in `./models/`). Use **temperature ≈ 0**. Pass a JSON **template** describing the snapshot schema; NuExtract is trained for template-guided extraction with span-faithful bias. Do **not** run a separate host-side Ollama/llama.cpp for this role.
- Online write path MUST still run the **cheap span verifier** (`requirement.md` §4.4 / FR-4). Unverified snapshots MUST NOT commit.
- Larger local LLMs (1.5B–3B+) MAY be used for experiments but are **not** the Profile C default. 7B+ co-resident with embed + rerank + Postgres is out of scope for the 12 GB default.

### When to use

- Air-gapped or low-egress environments for memory writes
- Lower per-token cost on high write volume
- Comfortable RAM headroom on 12 GB while keeping retrieval fully local

### Compose sketch

```text
services: postgres (pgvector), embed (bge-small-en-v1.5), rerank (gte-multilingual-reranker-base), extract (NuExtract-1.5-tiny via Compose llama.cpp server)
profiles: local-rft
env: DATABASE_URL, EMBED_URL, RERANK_URL, EXTRACT_URL (Compose NuExtract), optional LLM_API_* for host-agent / fallback
# Hosted alternative (egress!): EXTRACT_PROVIDER=openai, EXTRACT_URL=https://<api base>,
# EXTRACT_MODEL=<chat model>, EXTRACT_API_KEY=<key> replaces the Compose extract sidecar.
```

---

## Profile comparison

| | **A · api-inference** | **B · local-retrieval** | **C · local-rft** |
|---|---|---|---|
| Min CPU / RAM | 1 vCPU / 2 GB+ | **2 vCPU / 8 GB** | **4 vCPU / 12 GB** |
| pgvector | Local (Compose) | Local (Compose) | Local (Compose) |
| Embed | API | `bge-small-en-v1.5` (384d) | `bge-small-en-v1.5` (384d) |
| Rerank | API (optional) | `gte-multilingual-reranker-base` | `gte-multilingual-reranker-base` |
| LLM / extractor | API | API | **`numind/NuExtract-1.5-tiny`** (API optional fallback) |
| Best for | Quality, simplicity | Private retrieve + cloud LLM | Private write path |

---

## Non-goals for these profiles

- Shipping a frontier-class local LLM as the default answer model on 8–12 GB
- Co-running `bge-reranker-v2-m3` FP16 plus a 7B LLM on the same 12 GB host as the default
- Using LightMem’s `Llama-3.2-1B` as the default snapshot extractor (different role: control-plane rewrite/write, not span-verified JSON extract)
- Requiring GPU; all three profiles are **CPU-first** (GPU MAY accelerate Profile C)

---

## Related documents

- `requirement.md` — behavior, tool catalog, backends (Postgres/`pgvector` and SQLite)
- `compose.yml` — sidecars for profiles below; SQL in `schema/`
- `.env.example` — `DATABASE_URL` / `EMBED_URL` / `RERANK_URL` / `EXTRACT_URL`

### Compose commands

### Compose commands

The binary owns the Docker lifecycle (arch detection and service selection included):

```bash
clio compose up    # asks which services; --services postgres|local-retrieval|local-rft skips the prompt
clio compose down  # stops and removes what `clio compose up` started; safe to re-run
```

`clio compose up` detects the OS/arch (macOS arm64, Linux x86_64; anything else fails closed), maps the selection onto the same Compose profiles and arch overlays as the table below, materializes the compose files plus their bind-mount sources into the working directory (`--dir DIR` overrides), generates `.env` there, and shells out to the `docker` CLI.

One stack per machine: the Compose project name (`clio`) and host ports (34310–34313) are fixed, so `clio compose down` in any directory tears down the same containers. To run a second stack in parallel, set `COMPOSE_PROJECT_NAME` and override the `*_PORT` variables in the generated `.env`.

Make remains a power-user path (arch is a flag; default profile is `local-rft`):

```bash
make compose up mac      # arm64 → compose.arm64.yml
make compose up linux    # amd64 → compose.amd64.yml
```

Override profile: `make compose up mac PROFILE=local-retrieval` or `PROFILE=` (postgres only).

Or call Compose directly — always pass an arch file (`-f compose.amd64.yml` or `-f compose.arm64.yml`). TEI CPU images differ by architecture; `llama.cpp:server` is multi-arch but is platform-pinned the same way.

| Profile | amd64 | arm64 |
|---|---|---|
| A · `api-inference` | `docker compose -f compose.yml -f compose.amd64.yml up -d` | `docker compose -f compose.yml -f compose.arm64.yml up -d` |
| B · `local-retrieval` | `docker compose -f compose.yml -f compose.amd64.yml --profile local-retrieval up -d` | `docker compose -f compose.yml -f compose.arm64.yml --profile local-retrieval up -d` |
| C · `local-rft` | `docker compose -f compose.yml -f compose.amd64.yml --profile local-rft up -d` | `docker compose -f compose.yml -f compose.arm64.yml --profile local-rft up -d` |

Profile C also needs `./models/NuExtract-tiny-v1.5-Q4_K_M.gguf` before `extract` will stay healthy.

Schema: `schema/001_core.sql` is portable. Compose applies `002_vectors_postgres.sql` on first Postgres init. SQLite path: apply `001_core.sql` then `002_vectors_sqlite.sql`.

**Document status:** Planning · **Version:** 1.3

---

*End of document.*
