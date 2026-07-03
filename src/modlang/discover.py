"""Locate language files inside a resources directory or a mod jar."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .parser import LangParseError, format_of, parse_bytes, parse_file

JAR_LANG_RE = re.compile(r"^assets/([^/]+)/lang/([^/]+\.(?:json|lang))$")


@dataclass
class LangFile:
    code: str            # normalized lowercase language code, e.g. "zh_cn"
    fmt: str             # "json" or "lang"
    origin: str          # human-readable location for messages
    entries: Dict[str, str]
    path: Optional[Path] = None  # writable location; None when inside a jar
    rich: Dict[str, object] = field(default_factory=dict)  # NeoForge text components


@dataclass
class LangSet:
    """All language files belonging to one mod namespace."""

    namespace: str
    origin: str
    files: Dict[str, LangFile] = field(default_factory=dict)
    parse_errors: List[str] = field(default_factory=list)

    def codes(self) -> List[str]:
        return sorted(self.files)


def _normalize_code(filename: str) -> str:
    return Path(filename).stem.lower()


def _add_file(langset: LangSet, filename: str, data: bytes, origin: str,
              path: Optional[Path] = None) -> None:
    try:
        fmt = format_of(filename)
        parsed = parse_bytes(data, fmt, origin)
    except LangParseError as exc:
        langset.parse_errors.append(str(exc))
        return
    langset.files[_normalize_code(filename)] = LangFile(
        code=_normalize_code(filename), fmt=fmt, origin=origin,
        entries=parsed.entries, path=path, rich=parsed.rich,
    )


def discover_jar(jar_path: Path) -> List[LangSet]:
    sets: Dict[str, LangSet] = {}
    with zipfile.ZipFile(jar_path) as jar:
        for name in jar.namelist():
            match = JAR_LANG_RE.match(name)
            if not match:
                continue
            namespace, filename = match.groups()
            langset = sets.setdefault(
                namespace,
                LangSet(namespace=namespace, origin=f"{jar_path.name}!assets/{namespace}/lang"),
            )
            _add_file(langset, filename, jar.read(name), f"{jar_path.name}!{name}")
    return [sets[ns] for ns in sorted(sets)]


def discover_dir(root: Path) -> List[LangSet]:
    sets: List[LangSet] = []
    lang_dirs = sorted(
        (d for d in root.rglob("lang") if d.is_dir()),
        key=lambda d: str(d),
    )
    # `root` itself may be a lang directory (e.g. `modlang check assets/mymod/lang`)
    if root.name == "lang" and root.is_dir():
        lang_dirs.insert(0, root)
    for lang_dir in lang_dirs:
        files = [p for p in lang_dir.iterdir()
                 if p.is_file() and p.suffix.lower() in (".json", ".lang")]
        if not files:
            continue
        namespace = lang_dir.parent.name if lang_dir.parent != lang_dir else "?"
        langset = LangSet(namespace=namespace, origin=str(lang_dir))
        for path in sorted(files):
            _add_file(langset, path.name, path.read_bytes(), str(path), path=path)
        sets.append(langset)
    return sets


def discover(path: Path) -> List[LangSet]:
    """Entry point: accepts a directory, a jar/zip, or a single lang file."""
    if path.is_file():
        if path.suffix.lower() in (".jar", ".zip"):
            return discover_jar(path)
        if path.suffix.lower() in (".json", ".lang"):
            langset = LangSet(namespace=path.parent.parent.name or "?",
                              origin=str(path.parent))
            _add_file(langset, path.name, path.read_bytes(), str(path), path=path)
            return [langset]
        raise ValueError(f"unsupported file type: {path}")
    if path.is_dir():
        return discover_dir(path)
    raise FileNotFoundError(path)
