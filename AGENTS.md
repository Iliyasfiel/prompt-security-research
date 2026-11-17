# Agent Instructions

## Current State

The first course milestone is complete. Do not repeat the frozen formal experiment unless the user explicitly asks for a new run.

Treat these as the source of truth, in order:

1. `runs/formal/manifest.json`: frozen protocol, model route, cases, jobs, and code hash.
2. `runs/formal/results.jsonl` and `runs/formal/extraction/results.jsonl`: raw result rows.
3. `runs/formal/audit.json`: completeness and isolation checks.
4. `runs/formal/analysis/results.md`: generated statistics.
5. `docs/stage1-analysis.md`: interpretation and limitations.
6. `reports/stage1-midterm-report.md`: reader-facing report.

If these disagree, raw results and audit take precedence over prose.

## Reading Order

For project work, read:

1. `README.md`
2. `docs/stage1-progress.md`
3. `docs/stage1-analysis.md`
4. `docs/stage1-execution.md` when changing protocol or scope
5. `docs/literature.md` when changing claims or related work

The report DOCX and PDF are derived outputs. Do not treat them as editable sources.

## Non-Negotiable Research Rules

- Preserve `runs/formal/`. Never overwrite it in place.
- Put every new experiment in a new directory under `runs/`, with a new manifest and code hash.
- Never select a condition, target, or model after seeing its test result.
- Report model refusal, malformed output, task failure, technical error, and protocol violation separately.
- Keep `attempt_violation`, exact target success, and `executed_violation` distinct.
- A program authorization gate blocking a call is system behavior, not evidence that the model became safe.
- Use local simulated tools only. Do not connect tests to real accounts, credentials, funds, grades, private documents, or external messaging.
- Do not claim statistical significance, generality, novelty, or real-system exploitation beyond the recorded evidence.
- Natural extraction and controlled knowledge disclosure answer different questions. Do not merge them into a single leakage-to-attack curve.

## Repository Layout

- `scripts/`: experiment runner, model bridge, audits, and report builder.
- `analysis/`: deterministic statistics.
- `docs/`: plan, literature, stage records, evidence notes.
- `reports/`: submitted report formats.
- `runs/`: development and frozen experiment outputs.
- `qa/`: ignored internal rendering checks.

## Change Workflow

1. Inspect `git status` and the relevant frozen manifest/results.
2. Make the smallest change that satisfies the request.
3. Keep code and generated results reproducible; avoid hand-editing rate values.
4. Run the narrowest relevant check:
   - `python analysis/analyze.py --input runs/formal/combined-results.jsonl --output runs/formal/analysis`
   - `python scripts/audit_runs.py --run formal`
   - `python -m py_compile scripts/*.py analysis/analyze.py`
5. If claims, paths, or structure change, update `README.md`, `docs/`, or `reports/` as needed.
6. Do not commit or push unless the user asks.

## Avoid Overengineering

- Do not introduce an agent framework, database, CI system, container stack, or web UI without a concrete requirement.
- Prefer standard-library Python and the existing scripts.
- Reuse the existing four domains and frozen artifacts unless a new research question requires otherwise.
- Add one experiment or one report improvement at a time.
- Keep documentation concise and keep one canonical location for each artifact.
- Delete duplicate drafts rather than maintaining parallel prose.

## Model and Environment

The current route is `auto/deepseek-v4.1-flash` through the local Codex App Server. The application prompt uses `baseInstructions` and simulated tools use `dynamicTools`.

Do not request a new API key merely because environment variables are absent. Check the existing configuration first. Never print or commit credentials.

Platform background tools and instructions remain a recorded limitation. The protected object is the application-authored instruction text, not every hidden platform instruction.

## Next Work

No post-midterm experiment is currently authorized. Before extending the study, confirm the research question and resource scope, then create a new versioned run. The strongest existing follow-up is an equal-length irrelevant/wrong-information control, not a larger stack of infrastructure.
