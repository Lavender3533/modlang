"""Read and write Minecraft language files.

Two on-disk formats exist:

* ``.json`` - flat string-to-string JSON object, used since 1.13.
* ``.lang`` - legacy ``key=value`` lines with ``#`` comments, used up to 1.12.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


class LangParseError(ValueError):
    def __init__(self, origin: str, message: str):
        super().__init__(f"{origin}: {message}")
        self.origin = origin


def format_of(filename: str) -> str:
    """Return ``"json"`` or ``"lang"`` based on the file extension."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".lang":
        return "lang"
    raise LangParseError(filename, "not a .json or .lang file")


def parse_bytes(data: bytes, fmt: str, origin: str = "<bytes>") -> Dict[str, str]:
    """Parse raw file content into an ordered ``{key: value}`` dict."""
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
        entries: Dict[str, str] = {}
        for key, value in obj.items():
            if not isinstance(value, str):
                raise LangParseError(origin, f"value of {key!r} is not a string")
            entries[key] = value
        return entries

    if fmt == "lang":
        entries = {}
        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if "=" not in line:
                raise LangParseError(origin, f"line {lineno} has no '=' separator: {line!r}")
            key, _, value = line.partition("=")
            entries[key.strip()] = value
        return entries

    raise LangParseError(origin, f"unknown format {fmt!r}")


def parse_file(path: Path) -> Dict[str, str]:
    return parse_bytes(path.read_bytes(), format_of(path.name), str(path))


def dump_entries(entries: Dict[str, str], fmt: str) -> str:
    """Serialize entries back to file content (trailing newline included)."""
    if fmt == "json":
        return json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    if fmt == "lang":
        return "".join(f"{key}={value}\n" for key, value in entries.items())
    raise ValueError(f"unknown format {fmt!r}")
