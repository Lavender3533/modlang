"""Command line interface for modlang."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .checker import Report, compare
from .discover import LangSet, discover
from .parser import dump_entries
from .translate import TranslateError, translate_entries

_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def red(t: str) -> str:    return _c("31", t)
def green(t: str) -> str:  return _c("32", t)
def yellow(t: str) -> str: return _c("33", t)
def bold(t: str) -> str:   return _c("1", t)
def dim(t: str) -> str:    return _c("2", t)


def _load_sets(path_arg: str) -> List[LangSet]:
    path = Path(path_arg)
    try:
        sets = discover(path)
    except FileNotFoundError:
        sys.exit(f"error: path not found: {path}")
    except ValueError as exc:
        sys.exit(f"error: {exc}")
    if not sets:
        sys.exit(f"error: no language files found under {path} "
                 "(expected assets/<namespace>/lang/*.json or *.lang)")
    return sets


def _pick_source(langset: LangSet, source_code: str) -> Optional[str]:
    if source_code in langset.files:
        return source_code
    # legacy files were often named en_US.lang; codes are normalized lowercase already
    return None


# ---------------------------------------------------------------- list

def cmd_list(args: argparse.Namespace) -> int:
    for langset in _load_sets(args.path):
        print(f"{bold(langset.namespace)}  {dim(langset.origin)}")
        for code in langset.codes():
            file = langset.files[code]
            print(f"  {code:<8} {file.fmt:<4} {len(file.entries):>5} keys")
        for error in langset.parse_errors:
            print(f"  {red('parse error:')} {error}")
    return 0


# ---------------------------------------------------------------- check

def _print_report(code: str, report: Report, verbose: bool) -> None:
    parts = []
    if report.missing:
        parts.append(red(f"{len(report.missing)} missing"))
    if report.empty:
        parts.append(red(f"{len(report.empty)} empty"))
    if report.placeholder_mismatch:
        parts.append(red(f"{len(report.placeholder_mismatch)} placeholder mismatch"))
    if report.untranslated:
        parts.append(yellow(f"{len(report.untranslated)} untranslated"))
    if report.extra:
        parts.append(yellow(f"{len(report.extra)} extra"))
    status = ", ".join(parts) if parts else green("ok")
    print(f"  {code:<8} {status}")

    def show(label: str, keys: List[str]) -> None:
        limit = None if verbose else 5
        for key in keys[:limit]:
            print(f"      {label} {key}")
        if limit is not None and len(keys) > limit:
            print(dim(f"      ... {len(keys) - limit} more (use -v to show all)"))

    show(red("missing:"), report.missing)
    show(red("empty:  "), report.empty)
    for key, src_ph, tgt_ph in report.placeholder_mismatch[: None if verbose else 5]:
        print(f"      {red('placeholder:')} {key}  source={src_ph} target={tgt_ph}")
    if verbose:
        show(yellow("same as source:"), report.untranslated)
        show(yellow("extra:  "), report.extra)


def cmd_check(args: argparse.Namespace) -> int:
    sets = _load_sets(args.path)
    total_errors = total_warnings = 0
    json_out = []

    for langset in sets:
        source_code = _pick_source(langset, args.source)
        if not args.json:
            print(f"{bold(langset.namespace)}  {dim(langset.origin)}")
        for error in langset.parse_errors:
            total_errors += 1
            if not args.json:
                print(f"  {red('parse error:')} {error}")
        if source_code is None:
            total_errors += 1
            if args.json:
                json_out.append({"namespace": langset.namespace, "origin": langset.origin,
                                 "error": f"source language {args.source!r} not found"})
            else:
                print(f"  {red('error:')} source language {args.source!r} not found "
                      f"(available: {', '.join(langset.codes()) or 'none'})")
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
                    print(f"  {code:<8} {red('file not found')}")
                continue
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
        summary = f"{total_errors} error(s), {total_warnings} warning(s)"
        print(bold(red(summary) if total_errors else
                   (yellow(summary) if total_warnings else green(summary))))

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

    sets = _load_sets(args.path)
    rc = 0
    for langset in sets:
        source_code = _pick_source(langset, args.source)
        if source_code is None:
            print(f"{bold(langset.namespace)}: {red('skip')} - source {args.source!r} not found")
            rc = 1
            continue
        source_file = langset.files[source_code]
        target_file = langset.files.get(args.lang)
        existing = target_file.entries if target_file else {}
        todo = {k: v for k, v in source_file.entries.items()
                if k not in existing and k not in source_file.rich}
        rich_skipped = sum(1 for k in source_file.rich if k not in existing)

        print(f"{bold(langset.namespace)}  {dim(langset.origin)}")
        if rich_skipped:
            print(f"  {yellow(f'{rich_skipped} rich-text key(s) skipped')} "
                  f"{dim('(NeoForge text components must be translated by hand)')}")
        if not todo:
            print(f"  {green('nothing to translate')} - {args.lang} already has all "
                  f"{len(source_file.entries)} keys")
            continue
        print(f"  {len(todo)} key(s) missing in {args.lang}")

        if args.dry_run:
            for key, value in list(todo.items())[:20]:
                print(f"    {key} = {value!r}")
            if len(todo) > 20:
                print(dim(f"    ... {len(todo) - 20} more"))
            continue

        if source_file.path is None:
            print(f"  {red('error:')} cannot write into a jar - extract it first")
            rc = 1
            continue
        if not (api_base and api_key and model):
            sys.exit("error: --api-base, --api-key and --model are required "
                     "(or set MODLANG_API_BASE / MODLANG_API_KEY / MODLANG_MODEL)")

        def progress(done: int, total: int) -> None:
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
        print(f"  {green('wrote')} {out_path}  "
              f"(+{len(result.translated)} translated, {len(result.failed)} failed)")
        for key, reason in result.failed.items():
            print(f"    {yellow('failed:')} {key}  {dim(reason)}")
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

    p_list = sub.add_parser("list", help="list language files found in a path or jar")
    p_list.add_argument("path", nargs="?", default=".")
    p_list.set_defaults(func=cmd_list)

    p_check = sub.add_parser("check", help="check translations against the source language")
    p_check.add_argument("path", nargs="?", default=".",
                         help="resources directory, mod jar, or single lang file")
    p_check.add_argument("--source", default="en_us", help="source language (default: en_us)")
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
    p_tr.add_argument("path", nargs="?", default=".")
    p_tr.add_argument("--lang", required=True, help="target language, e.g. zh_cn")
    p_tr.add_argument("--source", default="en_us")
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
