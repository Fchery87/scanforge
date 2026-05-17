# AI Investigation Stage — Design Doc

**Date:** 2026-05-17
**Status:** Approved — implementing
**Slot:** Between `NormalizationStage` and `PersistenceStage` in `apps/worker/app/services/scan_orchestrator.py`

---

## Decisions

| Question | Decision | Rationale |
|---|---|---|
| Model hosting | Both Anthropic API + Ollama, behind `AIProvider` protocol | Lock-in avoidance; local option for compliance postures |
| Granularity | Per-finding calls | Clean failure boundary, cacheable by fingerprint, easy to parallelize |
| Output schema | `AIAnnotation`: explanation, remediation, model_id, token counts, latency | Advisory only; no severity override to prevent prompt-injection side effects |
| Storage target | `FindingInstance.ai_annotation` JSONB (nullable) | Consistent with per-scan evidence model; single non-blocking migration |
| Prompt injection defense | Metadata fields only; no code snippets, no `raw_output`, no `metadata_json` | Scanner output is attacker-controlled; metadata alone yields useful annotations |
| Cost guardrails | `AI_MAX_FINDINGS_PER_SCAN` env var (default 50), severity-sorted | Simple, visible, tunable without a deploy |
| Caching | Redis by `canonical_fingerprint`, 30-day TTL, reusing Upstash | Eliminates repeat calls for same finding across scheduled scans |
| Failure mode | Non-blocking: annotation errors skip the finding, scan completes | Finding persists with NULL `ai_annotation`; `ai_skipped_count` in completion summary |
| Provider selection | `AI_PROVIDER=anthropic|ollama` env var; single active provider | No per-org switching in v1 — belongs to a settings UI |
| Per-org opt-out | `AI_ENABLED=true/false` global kill switch | Per-org DB flag deferred until settings UI exists |
| Scan type filter | Skip `scan.secrets` | Gitleaks raw output contains matched secret values; explicit type filter is auditable |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AI_ENABLED` | `true` | Global kill switch |
| `AI_PROVIDER` | `anthropic` | `anthropic` or `ollama` |
| `AI_MAX_FINDINGS_PER_SCAN` | `50` | Max findings annotated per scan (severity-sorted) |
| `ANTHROPIC_API_KEY` | — | Required when `AI_PROVIDER=anthropic` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name |
| `UPSTASH_REDIS_REST_URL` | — | Reused from queue config; cache disabled if absent |
| `UPSTASH_REDIS_REST_TOKEN` | — | Reused from queue config |

---

## AIAnnotation Schema

```python
@dataclass
class AIAnnotation:
    explanation: str      # 2-4 sentences on why this finding matters
    remediation: str | None  # one-sentence fix suggestion, or None
    model_id: str         # e.g. "claude-haiku-4-5-20251001"
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cached: bool = False  # True when served from Redis cache
```

Stored as JSONB on `finding_instances.ai_annotation`.

---

## Prompt Construction (injection defense)

Only these fields are included in the prompt:

- `severity`, `category`, `title`, `description` — from the normalized finding
- `primary_scanner` — scanner name only (not raw output)
- `package_name`, `installed_version`, `fixed_version` — dependency context
- `references[*].url` or `references[*].value` — capped at 5, URLs only

Explicitly excluded:
- `raw_output` — attacker-controlled scanner stdout
- `metadata_json` — scanner-specific unstructured data
- `code_snippet`, `evidence_json` — repo content
- `instance.path` — file path

The system message contains all instructions. The user message contains only the JSON data object. Claude's role separation ensures the model treats the data section as data, not as instructions.

---

## Pipeline Insertion Point

```text
ScanExecutionStage   — clone, scan, upload
NormalizationStage   — raw → canonical findings
AIInvestigationStage — annotate findings (new, non-blocking)
PersistenceStage     — persist findings + notifications
```

In `scan_orchestrator.py`, between the normalization block and the persistence block:

```python
await self._update_status(context, "ai_investigating")
await self._ai_investigation.run(context, job_type=job.job_type)
```

---

## Database Change

Single non-blocking migration:
```sql
ALTER TABLE finding_instances ADD COLUMN ai_annotation JSONB;
```

No new table, no default value, nullable.

---

## Caching

Redis key: `ai_annotation:{canonical_fingerprint}`
TTL: 30 days (2,592,000 seconds)
Cache hit: `cached=True` in the returned annotation; not counted toward token spend in logs.
Cache miss on error: falls through to provider call (warning logged, not an error).

---

## Deferred

- Per-org `ai_enabled` DB flag (needs settings UI)
- Per-org monthly token budget (needs billing module)
- Model version pinning per org
- Annotation quality feedback loop (thumbs up/down on explanations)
