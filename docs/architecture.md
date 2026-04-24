# tableau2pbir — Architecture

Full design in `docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md`.
This file is an entry point for new contributors.

## Entry point

- `tableau2pbir.cli:main` → `argparse` dispatcher for `convert` / `resume`.
- `tableau2pbir.pipeline.run_pipeline` → sequences 8 stages from `STAGE_SEQUENCE`.

## Package layout (Plan-1 scope)

```
src/tableau2pbir/
├── cli.py                  # argparse CLI
├── pipeline.py             # runner + StageResult / StageError / StageContext
├── ir/                     # pydantic IR + JSON Schema autogen (§5)
├── llm/                    # LLMClient + cache + snapshots + per-prompt folders (§7)
└── stages/                 # 8 stub modules, one per pipeline stage
```

Plans 2–5 add the `translators/`, `classify/`, `emit/`, `validate/`, and
`util/` packages per spec §10.

## Running the pipeline

```bash
tableau2pbir convert path/to/workbook.twbx --out ./out/
tableau2pbir convert path/to/workbook.twbx --out ./out/ --gate canonicalize
tableau2pbir resume ./out/<workbook>/ --from translate_calcs
```
