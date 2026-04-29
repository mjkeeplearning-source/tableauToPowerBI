"""CLI — `tableau2pbir` with `convert` and `resume` subcommands. See spec §4.1.

Batch support in Plan 1 is single-workbook only (convert one .twb/.twbx per
invocation). Multiprocessing batch pool is added in Plan 5 (§4.1)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from tableau2pbir.pipeline import STAGE_SEQUENCE, run_pipeline

load_dotenv()  # loads .env from cwd or any parent directory


def _stage_names() -> list[str]:
    return [name for name, _ in STAGE_SEQUENCE]


def _workbook_id(source_path: Path) -> str:
    return source_path.stem


def _cmd_convert(args: argparse.Namespace) -> int:
    source_path = Path(args.source).resolve()
    out_root = Path(args.out).resolve()
    wb_id = _workbook_id(source_path)
    output_dir = out_root / wb_id
    output_dir.mkdir(parents=True, exist_ok=True)
    result = run_pipeline(
        workbook_id=wb_id,
        source_path=source_path,
        output_dir=output_dir,
        config={},
        gate=args.gate,
        resume_from=None,
    )
    print(
        f"[tableau2pbir] wb={wb_id} stages_run={result.stages_run}"
        f"{' gate=' + result.stopped_at_gate if result.stopped_at_gate else ''}"
    )
    return 0


def _cmd_resume(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    wb_id = output_dir.name
    # Source path is informational only when resuming — stages read their own prior outputs.
    source_path = output_dir / f"{wb_id}.twb"
    result = run_pipeline(
        workbook_id=wb_id,
        source_path=source_path,
        output_dir=output_dir,
        config={},
        gate=args.gate,
        resume_from=args.from_stage,
    )
    print(f"[tableau2pbir] resumed wb={wb_id} stages_run={result.stages_run}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tableau2pbir",
        description="Convert Tableau workbooks (.twb/.twbx) to Power BI (PBIR).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_conv = sub.add_parser("convert", help="Convert one workbook end-to-end.")
    p_conv.add_argument("source", help="Path to .twb or .twbx")
    p_conv.add_argument("--out", required=True, help="Output root directory")
    p_conv.add_argument("--gate", choices=_stage_names(), default=None,
                        help="Pause after the named stage")
    p_conv.set_defaults(func=_cmd_convert)

    p_res = sub.add_parser("resume", help="Resume a previously-gated workbook.")
    p_res.add_argument("output_dir", help="The ./out/<wb>/ directory from a prior run")
    p_res.add_argument("--from", dest="from_stage", required=True,
                       choices=_stage_names(),
                       help="Stage to resume from (runs this one and all subsequent)")
    p_res.add_argument("--gate", choices=_stage_names(), default=None,
                       help="Optional second gate on resume")
    p_res.set_defaults(func=_cmd_resume)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
