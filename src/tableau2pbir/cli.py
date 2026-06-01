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


def _cmd_refresh_schemas(args: argparse.Namespace) -> int:
    from tableau2pbir.validate.refresh_schemas import _get_cache_dir, refresh_schemas
    cache_dir = _get_cache_dir(cli_override=getattr(args, "cache_dir", None))
    ok = refresh_schemas(cache_dir=cache_dir)
    return 0 if ok else 1


def _cmd_regression_add(args: argparse.Namespace) -> int:
    import subprocess
    from datetime import date
    from pathlib import Path

    from tableau2pbir.regression.snapshot import RegistrationError, register_workbook

    workbook_path = Path(args.source).resolve()
    corpus_path = Path(args.corpus)
    snapshots_root = Path(args.snapshots_root)
    notes = args.notes or ""

    try:
        added_by = subprocess.check_output(
            ["git", "config", "user.name"], text=True
        ).strip()
    except Exception:
        added_by = "unknown"

    added_on = str(date.today())

    try:
        tmdl_count, json_count = register_workbook(
            workbook_path=workbook_path,
            corpus_path=corpus_path,
            snapshots_root=snapshots_root,
            notes=notes,
            added_by=added_by,
            added_on=added_on,
        )
        print(f"Registered {workbook_path.stem} — {tmdl_count} TMDL files, {json_count} PBIR JSON files snapshotted")
        return 0
    except RegistrationError as exc:
        print(f"[regression-add] ERROR: {exc}", file=sys.stderr)
        return 1


def _cmd_regression_check(args: argparse.Namespace) -> int:
    from pathlib import Path

    from tableau2pbir.regression.check import run_regression_check
    from tableau2pbir.regression.report import format_report

    corpus_path = Path(args.corpus)
    snapshots_root = Path(args.snapshots_root)
    name_filter = getattr(args, "name", None) or None

    result = run_regression_check(
        corpus_path=corpus_path,
        snapshots_root=snapshots_root,
        name_filter=name_filter,
    )
    print(format_report(result))
    return result.exit_code


def _cmd_regression_install_hook(args: argparse.Namespace) -> int:
    from pathlib import Path

    from tableau2pbir.regression.hook import HookInstallError, install_hook

    hook_path = Path(args.hook_path)
    try:
        newly_written = install_hook(hook_path=hook_path)
        if newly_written:
            print(f"Installed regression-check hook at {hook_path}")
        else:
            print(f"Hook already installed at {hook_path} — no changes made")
        return 0
    except HookInstallError as exc:
        print(f"[regression-install-hook] ERROR: {exc}", file=sys.stderr)
        return 1


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

    p_refresh = sub.add_parser(
        "refresh-schemas",
        help="Download latest Microsoft PBI schemas to local cache.",
    )
    p_refresh.add_argument(
        "--cache-dir",
        default=None,
        help="Override schema cache directory (default: ~/.cache/tableau2pbir/schemas/)",
    )
    p_refresh.set_defaults(func=_cmd_refresh_schemas)

    _CORPUS_DEFAULT = "tests/regression/corpus.yaml"
    _SNAPS_DEFAULT = "tests/regression/snapshots"

    p_reg_add = sub.add_parser("regression-add", help="Register a workbook into the regression corpus.")
    p_reg_add.add_argument("source", help="Path to .twb or .twbx to register")
    p_reg_add.add_argument("--notes", default="", help="Optional description")
    p_reg_add.add_argument("--corpus", default=_CORPUS_DEFAULT, help="Path to corpus.yaml")
    p_reg_add.add_argument("--snapshots-root", default=_SNAPS_DEFAULT, dest="snapshots_root",
                           help="Root directory for snapshots")
    p_reg_add.set_defaults(func=_cmd_regression_add)

    p_reg_check = sub.add_parser("regression-check", help="Check registered workbooks against snapshots.")
    p_reg_check.add_argument("name", nargs="?", default=None, help="Optional workbook name to check (default: all)")
    p_reg_check.add_argument("--corpus", default=_CORPUS_DEFAULT, help="Path to corpus.yaml")
    p_reg_check.add_argument("--snapshots-root", default=_SNAPS_DEFAULT, dest="snapshots_root",
                             help="Root directory for snapshots")
    p_reg_check.set_defaults(func=_cmd_regression_check)

    p_reg_hook = sub.add_parser("regression-install-hook", help="Install regression-check as git pre-commit hook.")
    p_reg_hook.add_argument("--hook-path", default=".git/hooks/pre-commit", dest="hook_path",
                            help="Path to pre-commit hook file")
    p_reg_hook.set_defaults(func=_cmd_regression_install_hook)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
