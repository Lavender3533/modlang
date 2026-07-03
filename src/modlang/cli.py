"""Command line interface for modlang."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__, ui
from .checker import Report, compare
from .discover import LangSet, discover
from .parser import dump_entries
from .translate import TranslateError, translate_entries
from .ui import SYM, accent, bold, dim, err, ok, warn


def _load_sets(path_arg: str, excludes: Optional[List[str]] = None) -> List[LangSet]:
    path = Path(path_arg)
    try:
        sets = discover(path, excludes)
    except FileNotFoundError:
        sys.exit(f"error: path not found: {path}")
    except ValueError as exc:
        sys.exit(f"error: {exc}")
    if not sets:
        sys.exit(f"error: no language files found under {path} "
                 "(expected assets/<namespace>/lang/*.json or *.lang)")
    return sets


def _pick_source(langset: LangSet, source_code: str) -> Optional[str]:
    # codes are normalized lowercase, so en_US.lang is matched by "en_us" too
    return source_code if source_code in langset.files else None


# ---------------------------------------------------------------- list

def cmd_list(args: argparse.Namespace) -> int:
    sets = _load_sets(args.path, args.exclude)
    for index, langset in enumerate(sets):
        if index:
            print()
        print(ui.header(langset.namespace, langset.origin))
        source = langset.files.get(args.source)
        for code in langset.codes():
            file = langset.files[code]
            if source is not None and code == args.source:
                # pad before styling: ANSI codes would count toward the width
                print(f"  {bold(f'{code:<8}')} {len(file.entries):>5} keys  "
                      f"{dim('(source, ' + file.fmt + ')')}")
            elif source is not None and source.entries:
                covered = sum(1 for k in source.entries if k in file.entries)
                fraction = covered / len(source.entries)
                print(f"  {code:<8} {ui.coverage_bar(fraction)}  "
                      f"{dim(f'{covered}/{len(source.entries)} · {file.fmt}')}")
            else:
                print(f"  {code:<8} {len(file.entries):>5} keys  {dim(file.fmt)}")
        for error in langset.parse_errors:
            print(f"  {err(SYM['err'] + ' parse error:')} {error}")
    return 0


# ---------------------------------------------------------------- check

def _print_report(code: str, report: Report, verbose: bool) -> None:
    parts = []
    if report.missing:
        parts.append(err(f"{SYM['err']} {len(report.missing)} missing"))
    if report.empty:
        parts.append(err(f"{SYM['err']} {len(report.empty)} empty"))
    if report.placeholder_mismatch:
        parts.append(err(f"{SYM['err']} {len(report.placeholder_mismatch)} placeholder"))
    if report.untranslated:
        parts.append(warn(f"{SYM['warn']} {len(report.untranslated)} untranslated"))
    if report.extra:
        parts.append(warn(f"{SYM['warn']} {len(report.extra)} extra"))
    status = "  ".join(parts) if parts else ok(f"{SYM['ok']} ok")
    print(f"  {code:<8} {status}")

    def show(label: str, keys: List[str]) -> None:
        limit = None if verbose else 5
        for key in keys[:limit]:
            print(f"      {label} {key}")
        if limit is not None and len(keys) > limit:
            print(dim(f"      {SYM['dot']} {len(keys) - limit} more (use -v to show all)"))

    show(err("missing      "), report.missing)
    show(err("empty        "), report.empty)
    for key, src_ph, tgt_ph in report.placeholder_mismatch[: None if verbose else 5]:
        print(f"      {err('placeholder  ')} {key}  "
              f"{dim('source=')}{src_ph} {dim('target=')}{tgt_ph}")
    if verbose:
        show(warn("untranslated "), report.untranslated)
        show(warn("extra        "), report.extra)


def cmd_check(args: argparse.Namespace) -> int:
    sets = _load_sets(args.path, args.exclude)
    total_errors = total_warnings = languages_checked = 0
    json_out = []

    for index, langset in enumerate(sets):
        source_code = _pick_source(langset, args.source)
        if not args.json:
            if index:
                print()
            print(ui.header(langset.namespace, langset.origin))
        for error in langset.parse_errors:
            total_errors += 1
            if not args.json:
                print(f"  {err(SYM['err'] + ' parse error:')} {error}")
        if source_code is None:
            total_errors += 1
            if args.json:
                json_out.append({"namespace": langset.namespace, "origin": langset.origin,
                                 "error": f"source language {args.source!r} not found"})
            else:
                print(f"  {err(SYM['err'] + ' error:')} source language {args.source!r} "
                      f"not found (available: {', '.join(langset.codes()) or 'none'})")
            continue

        targets = args.lang or [c for c in langset.codes() if c != source_code]
        source_entries = langset.files[source_code].entries
        for code in targets:
            if code not in langset.files:
                total_errors += 1
                if args.json:
                    json_out.append({"namespace": langset.namespace, "lang": code,
                                     "error": "file not found"})
                else:
                    print(f"  {code:<8} {err(SYM['err'] + ' file not found')}")
                continue
            languages_checked += 1
            report = compare(source_entries, langset.files[code].entries)
            total_errors += report.error_count
            total_warnings += report.warning_count
            if args.json:
                json_out.append({"namespace": langset.namespace, "lang": code,
                                 **report.to_dict()})
            else:
                _print_report(code, report, args.verbose)

    if args.json:
        print(json.dumps(json_out, ensure_ascii=False, indent=2))
    else:
        print()
        print(ui.rule())
        if total_errors:
            summary = err(f"{SYM['err']} {total_errors} error(s)")
            if total_warnings:
                summary += "  " + warn(f"{SYM['warn']} {total_warnings} warning(s)")
        elif total_warnings:
            summary = warn(f"{SYM['warn']} {total_warnings} warning(s)")
        else:
            summary = ok(f"{SYM['ok']} all clean")
        print(f"{bold(summary)}  "
              f"{dim(f'{languages_checked} language file(s) checked')}")

    if total_errors:
        return 1
    if total_warnings and args.strict:
        return 1
    return 0


# ---------------------------------------------------------------- translate

def cmd_translate(args: argparse.Namespace) -> int:
    api_base = args.api_base or os.environ.get("MODLANG_API_BASE") \
        or os.environ.get("OPENAI_BASE_URL")
    api_key = args.api_key or os.environ.get("MODLANG_API_KEY") \
        or os.environ.get("OPENAI_API_KEY")
    model = args.model or os.environ.get("MODLANG_MODEL")

    sets = _load_sets(args.path, args.exclude)
    rc = 0
    for index, langset in enumerate(sets):
        if index:
            print()
        print(ui.header(langset.namespace, langset.origin))
        source_code = _pick_source(langset, args.source)
        if source_code is None:
            print(f"  {err(SYM['err'] + ' skip:')} source {args.source!r} not found")
            rc = 1
            continue
        source_file = langset.files[source_code]
        target_file = langset.files.get(args.lang)
        existing = target_file.entries if target_file else {}
        todo = {k: v for k, v in source_file.entries.items()
                if k not in existing and k not in source_file.rich}
        rich_skipped = sum(1 for k in source_file.rich if k not in existing)

        if rich_skipped:
            note = f"{SYM['warn']} {rich_skipped} rich-text key(s) skipped"
            print(f"  {warn(note)} "
                  f"{dim('(NeoForge text components must be translated by hand)')}")
        if not todo:
            print(f"  {ok(SYM['ok'] + ' nothing to translate')} {dim('-')} {args.lang} "
                  f"already has all {len(source_file.entries)} keys")
            continue
        print(f"  {accent(str(len(todo)))} key(s) missing in {bold(args.lang)}")

        if args.dry_run:
            for key, value in list(todo.items())[:20]:
                print(f"    {dim(SYM['dot'])} {key} {dim('=')} {value!r}")
            if len(todo) > 20:
                print(dim(f"    {SYM['dot']} ... {len(todo) - 20} more"))
            continue

        if source_file.path is None:
            print(f"  {err(SYM['err'] + ' error:')} cannot write into a jar - extract it first")
            rc = 1
            continue
        if not (api_base and api_key and model):
            sys.exit("error: --api-base, --api-key and --model are required "
                     "(or set MODLANG_API_BASE / MODLANG_API_KEY / MODLANG_MODEL)")

        def progress(done: int, total: int) -> None:
            if sys.stdout.isatty():
                end = "\n" if done >= total else ""
                print(f"\r  translating {ui.progress_bar(done / total)} {done}/{total} ",
                      end=end, flush=True)
            else:
                print(f"  translating... {done}/{total}", flush=True)

        try:
            result = translate_entries(
                todo, args.lang,
                api_base=api_base, api_key=api_key, model=model,
                batch_size=args.batch_size, progress=progress,
            )
        except TranslateError as exc:
            sys.exit(f"error: {exc}")

        # Rebuild in source key order so diffs stay readable; keep extra keys at the end.
        merged = {}
        for key in source_file.entries:
            if key in existing:
                merged[key] = existing[key]
            elif key in result.translated:
                merged[key] = result.translated[key]
        for key, value in existing.items():
            if key not in merged:
                merged[key] = value

        out_path = (target_file.path if target_file and target_file.path
                    else source_file.path.with_name(args.lang + source_file.path.suffix))
        target_rich = target_file.rich if target_file else {}
        out_path.write_text(dump_entries(merged, source_file.fmt, rich=target_rich),
                            encoding="utf-8")
        print(f"  {ok(SYM['ok'] + ' wrote')} {out_path}  "
              f"{dim(f'+{len(result.translated)} translated, {len(result.failed)} failed')}")
        for key, reason in result.failed.items():
            print(f"    {warn(SYM['warn'] + ' failed:')} {key}  {dim(reason)}")
        if result.failed:
            rc = 1
    return rc


# ---------------------------------------------------------------- main

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="modlang",
        description="Lint, diff and auto-translate Minecraft mod language files.",
    )
    parser.add_argument("--version", action="version", version=f"modlang {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("path", nargs="?", default=".",
                       help="resources directory, mod jar, or single lang file")
        p.add_argument("--exclude", action="append", default=[], metavar="PATTERN",
                       help="skip directories matching this glob (repeatable), "
                            "e.g. --exclude 'epicfight*'")
        p.add_argument("--source", default="en_us",
                       help="source language (default: en_us)")

    p_list = sub.add_parser("list", help="list language files with coverage bars")
    common_args(p_list)
    p_list.set_defaults(func=cmd_list)

    p_check = sub.add_parser("check", help="check translations against the source language")
    common_args(p_check)
    p_check.add_argument("--lang", action="append",
                         help="target language(s) to check (default: all found)")
    p_check.add_argument("--json", action="store_true", help="machine-readable output")
    p_check.add_argument("--strict", action="store_true",
                         help="exit non-zero on warnings too")
    p_check.add_argument("-v", "--verbose", action="store_true",
                         help="show every affected key")
    p_check.set_defaults(func=cmd_check)

    p_tr = sub.add_parser("translate",
                          help="fill missing keys using an OpenAI-compatible API")
    common_args(p_tr)
    p_tr.add_argument("--lang", required=True, help="target language, e.g. zh_cn")
    p_tr.add_argument("--api-base", help="e.g. https://api.openai.com/v1 "
                                         "(env: MODLANG_API_BASE / OPENAI_BASE_URL)")
    p_tr.add_argument("--api-key", help="env: MODLANG_API_KEY / OPENAI_API_KEY")
    p_tr.add_argument("--model", help="env: MODLANG_MODEL")
    p_tr.add_argument("--batch-size", type=int, default=40)
    p_tr.add_argument("--dry-run", action="store_true",
                      help="only show what would be translated")
    p_tr.set_defaults(func=cmd_translate)

    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
