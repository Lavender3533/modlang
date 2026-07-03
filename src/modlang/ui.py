"""Terminal styling: colors, symbols and bars.

Degrades gracefully: honors NO_COLOR, falls back to ASCII symbols when the
terminal encoding is not UTF-8, and stays plain when piped to a file.
Only common Unicode glyphs are used (no Nerd Font required).
"""

from __future__ import annotations

import os
import sys

if os.name == "nt":
    os.system("")  # enables ANSI escape processing in legacy Windows consoles


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty() or bool(os.environ.get("FORCE_COLOR"))


def _supports_unicode() -> bool:
    return "utf" in (getattr(sys.stdout, "encoding", "") or "").lower()


COLOR = _supports_color()
UNICODE = _supports_unicode()

SYM = {
    "header": "▍" if UNICODE else "|",
    "ok": "✓" if UNICODE else "+",
    "err": "✗" if UNICODE else "x",
    "warn": "⚠" if UNICODE else "!",
    "dot": "·" if UNICODE else "-",
    "bar_full": "█" if UNICODE else "#",
    "bar_empty": "░" if UNICODE else ".",
    "rule": "─" if UNICODE else "-",
}


def style(text: str, *codes: int) -> str:
    if not COLOR or not codes:
        return text
    return f"\033[{';'.join(str(c) for c in codes)}m{text}\033[0m"


def accent(t: str) -> str: return style(t, 96)   # bright cyan
def ok(t: str) -> str:     return style(t, 92)
def warn(t: str) -> str:   return style(t, 93)
def err(t: str) -> str:    return style(t, 91)
def bold(t: str) -> str:   return style(t, 1)
def dim(t: str) -> str:    return style(t, 2)


def header(title: str, subtitle: str = "") -> str:
    """Colored section header:  ▍title  subtitle"""
    line = f"{accent(SYM['header'])} {style(title, 1, 96)}"
    if subtitle:
        line += f"  {dim(subtitle)}"
    return line


def _bar(fraction: float, width: int) -> str:
    fraction = max(0.0, min(1.0, fraction))
    filled = round(fraction * width)
    return SYM["bar_full"] * filled + SYM["bar_empty"] * (width - filled)


def coverage_bar(fraction: float, width: int = 20) -> str:
    """Bar colored by how healthy the coverage is (green/yellow/red)."""
    paint = ok if fraction >= 0.95 else warn if fraction >= 0.7 else err
    return f"{paint(_bar(fraction, width))} {bold(paint(f'{fraction * 100:3.0f}%'))}"


def progress_bar(fraction: float, width: int = 24) -> str:
    """Neutral (accent-colored) bar for in-flight progress."""
    return accent(_bar(fraction, width))


def rule(width: int = 44) -> str:
    return dim(SYM["rule"] * width)
