# tableau2pbir

Deterministic converter from Tableau workbooks (`.twb` / `.twbx`) to Power BI projects in PBIR format.
Design spec: `docs/superpowers/specs/2026-04-23-tableau-to-pbir-design.md`.

## Install (dev)

```bash
python -m venv .venv
source .venv/Scripts/activate    # bash on Windows
# or: .venv\Scripts\activate       # PowerShell
pip install -e ".[dev]"
```

## Run

```bash
tableau2pbir convert path/to/workbook.twbx --out ./out/
```

## Test

```bash
make test          # v1 scope
make test-v1.1     # v1 + v1.1-preview features
```
