"""Compare a translation against its source language and report problems."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# Java String.format placeholders as used by Minecraft: %s, %d, %1$s, %.1f, %%
PLACEHOLDER_RE = re.compile(r"%(?:\d+\$)?(?:\.\d+)?[sdfeExXob]|%%")


def placeholders(text: str) -> List[str]:
    """Extract format placeholders in order of appearance (%% excluded)."""
    return [m for m in PLACEHOLDER_RE.findall(text) if m != "%%"]


@dataclass
class Report:
    """Result of comparing one target language file against the source."""

    missing: List[str] = field(default_factory=list)
    extra: List[str] = field(default_factory=list)
    empty: List[str] = field(default_factory=list)
    placeholder_mismatch: List[Tuple[str, List[str], List[str]]] = field(default_factory=list)
    untranslated: List[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.missing) + len(self.empty) + len(self.placeholder_mismatch)

    @property
    def warning_count(self) -> int:
        return len(self.extra) + len(self.untranslated)

    @property
    def clean(self) -> bool:
        return self.error_count == 0 and self.warning_count == 0

    def to_dict(self) -> dict:
        return {
            "missing": self.missing,
            "extra": self.extra,
            "empty": self.empty,
            "placeholder_mismatch": [
                {"key": key, "source": src, "target": tgt}
                for key, src, tgt in self.placeholder_mismatch
            ],
            "untranslated": self.untranslated,
            "errors": self.error_count,
            "warnings": self.warning_count,
        }


def _looks_translatable(text: str) -> bool:
    """Heuristic: values with no letters (numbers, symbols, bare placeholders)
    are expected to be identical across languages and are not flagged."""
    stripped = PLACEHOLDER_RE.sub("", text)
    return any(ch.isalpha() for ch in stripped) and len(stripped.strip()) > 1


def compare(source: Dict[str, str], target: Dict[str, str]) -> Report:
    report = Report()
    for key, src_value in source.items():
        if key not in target:
            report.missing.append(key)
            continue
        tgt_value = target[key]
        if tgt_value.strip() == "" and src_value.strip() != "":
            report.empty.append(key)
            continue
        src_ph, tgt_ph = placeholders(src_value), placeholders(tgt_value)
        if sorted(src_ph) != sorted(tgt_ph):
            report.placeholder_mismatch.append((key, src_ph, tgt_ph))
        if tgt_value == src_value and _looks_translatable(src_value):
            report.untranslated.append(key)
    for key in target:
        if key not in source:
            report.extra.append(key)
    return report
