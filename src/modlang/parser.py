"""Read and write Minecraft language files.

Two on-disk formats exist:

* ``.json`` - flat string-to-string JSON object, used since 1.13. NeoForge
  additionally allows JSON text components (arrays/objects) as values.
* ``.lang`` - legacy ``key=value`` lines with ``#`` comments, used up to 1.12.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


class LangParseError(ValueError):
    def __init__(self, origin: str, message: str):
        super().__init__(f"{origin}: {message}")
        self.origin = origin


@dataclass
class ParsedLang:
    """Parsed language file.

    ``entries`` maps every key to a string. Non-string values (NeoForge rich
    text components) are stored in ``entries`` as their compact JSON text so
    they take part in key comparison, with the original value kept in ``rich``
    so files can be written back without corruption.
    """

    entries: Dict[str, str]
    rich: Dict[str, object] = field(default_factory=dict)


def format_of(filename: str) -> str:
    """Return ``"json"`` or ``"lang"`` based on the file extension."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".lang":
        return "lang"
    raise LangParseError(filename, "not a .json or .lang file")


def parse_bytes(data: bytes, fmt: str, origin: str = "<bytes>") -> ParsedLang:
    """Parse raw file content, preserving key order."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LangParseError(origin, f"not valid UTF-8: {exc}") from exc

    if fmt == "json":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LangParseError(origin, f"invalid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise LangParseError(origin, "top-level JSON value must be an object")
        parsed = ParsedLang(entries={})
        for key, value in obj.items():
            if isinstance(value, str):
                parsed.entries[key] = value
            else:
                parsed.entries[key] = json.dumps(value, ensure_ascii=False)
                parsed.rich[key] = value
        return parsed

    if fmt == "lang":
        entries: Dict[str, str] = {}
        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if "=" not in line:
                raise LangParseError(origin, f"line {lineno} has no '=' separator: {line!r}")
            key, _, value = line.partition("=")
            entries[key.strip()] = value
        return ParsedLang(entries=entries)

    raise LangParseError(origin, f"unknown format {fmt!r}")


def parse_file(path: Path) -> ParsedLang:
    return parse_bytes(path.read_bytes(), format_of(path.name), str(path))


def dump_entries(entries: Dict[str, str], fmt: str,
                 rich: Dict[str, object] = None) -> str:
    """Serialize entries back to file content (trailing newline included).

    ``rich`` restores original non-string values for keys that were parsed
    from NeoForge text components, so round-tripping never corrupts them.
    """
    if fmt == "json":
        rich = rich or {}
        out = {key: rich[key] if key in rich else value
               for key, value in entries.items()}
        return json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if fmt == "lang":
        return "".join(f"{key}={value}\n" for key, value in entries.items())
    raise ValueError(f"unknown format {fmt!r}")
