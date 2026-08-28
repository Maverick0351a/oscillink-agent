# Oscillink Agent

Oscillink Agent is a local-first, open-weight personal agent designed to develop durable, provenance-linked continuity with Maverick and migrate to cloud infrastructure without changing its core contracts.

## Current milestone

The first milestone is a governed continuity kernel:

- append-only execution events;
- reviewed Obsidian knowledge;
- provenance-linked retrieval;
- context manifests for model calls;
- typed capability grants;
- parent-versus-candidate evaluation.

The first implementation gate covers package quality checks, machine-readable schemas, and immutable domain objects. The agent loop comes later.

## Model strategy

- Local baseline: `qwen3:14b` through Ollama at `http://localhost:11434/v1`.
- Local candidate: `gpt-oss-20b`, adopted only after measured VRAM, latency, tool-call and benchmark results.
- Cloud path: the same OpenAI-compatible provider contract targets vLLM or NVIDIA NIM.

Open weights remove per-token provider fees locally; cloud GPU and storage still have operating costs.

## Architecture

```text
Obsidian/Git + append-only events
              ↓
       cited context compiler
              ↓
 local/cloud model provider
              ↓
      typed capability broker
              ↓
   isolated tools + verification
              ↓
 evaluation, promotion, rollback
```

## Development

The project uses Python 3.11, `uv`, pytest, Ruff, mypy, Pydantic v2, SQLite/FTS5 and FastAPI.

The implementation plan is in [`docs/build-plan.md`](docs/build-plan.md).

## Safety boundary

An open or unrestricted model may reason and propose freely, but it does not receive unrestricted credentials, filesystem/network access, memory-promotion authority, governance mutation, self-deployment or shutdown control.
