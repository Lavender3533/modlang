"""Fill in missing translations via any OpenAI-compatible chat API.

Uses only the standard library so modlang stays dependency-free.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List

from .checker import placeholders

# Friendly names help smaller models; anything unlisted falls back to the raw code.
LANGUAGE_NAMES = {
    "zh_cn": "Simplified Chinese (简体中文)",
    "zh_tw": "Traditional Chinese (繁體中文)",
    "ja_jp": "Japanese",
    "ko_kr": "Korean",
    "ru_ru": "Russian",
    "de_de": "German",
    "fr_fr": "French",
    "es_es": "Spanish (Spain)",
    "pt_br": "Portuguese (Brazil)",
    "it_it": "Italian",
    "pl_pl": "Polish",
    "uk_ua": "Ukrainian",
    "vi_vn": "Vietnamese",
    "th_th": "Thai",
    "tr_tr": "Turkish",
    "id_id": "Indonesian",
}

SYSTEM_PROMPT = """\
You translate Minecraft mod language entries from English to {language}.
Rules:
- Keep Java format placeholders exactly as-is: %s, %d, %1$s, %.1f, %% etc.
- Keep Minecraft formatting codes exactly as-is: §a, §l, §r etc.
- Keep line breaks (\\n) where the source has them.
- Use the wording of the official Minecraft {language} localization for \
vanilla item/block/concept names.
- Translate naturally; do not translate proper nouns that have no established translation.
Respond with ONLY a JSON object mapping each input key to its translation. No other text.\
"""


class TranslateError(RuntimeError):
    pass


@dataclass
class TranslationResult:
    translated: Dict[str, str] = field(default_factory=dict)
    failed: Dict[str, str] = field(default_factory=dict)  # key -> reason


def _extract_json_object(text: str) -> dict:
    """Pull the first JSON object out of a model response (tolerates code fences)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise TranslateError(f"model response contains no JSON object: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def _chat(api_base: str, api_key: str, model: str, system: str, user: str,
          timeout: float = 120.0) -> str:
    url = api_base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise TranslateError(f"API returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TranslateError(f"cannot reach {url}: {exc}") from exc
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TranslateError(f"unexpected API response shape: {str(body)[:300]}") from exc


def translate_entries(entries: Dict[str, str], target_code: str, *,
                      api_base: str, api_key: str, model: str,
                      batch_size: int = 40,
                      progress=lambda done, total: None) -> TranslationResult:
    """Translate ``entries`` (key -> English source text) into ``target_code``."""
    language = LANGUAGE_NAMES.get(target_code, target_code)
    system = SYSTEM_PROMPT.format(language=language)
    keys = list(entries)
    result = TranslationResult()

    for offset in range(0, len(keys), batch_size):
        batch = {key: entries[key] for key in keys[offset:offset + batch_size]}
        user = json.dumps(batch, ensure_ascii=False, indent=1)
        try:
            answer = _extract_json_object(_chat(api_base, api_key, model, system, user))
        except (TranslateError, json.JSONDecodeError) as exc:
            for key in batch:
                result.failed[key] = f"batch failed: {exc}"
            progress(min(offset + batch_size, len(keys)), len(keys))
            continue

        for key, source in batch.items():
            value = answer.get(key)
            if not isinstance(value, str) or not value.strip():
                result.failed[key] = "missing from model response"
            elif sorted(placeholders(value)) != sorted(placeholders(source)):
                result.failed[key] = (
                    f"placeholder mismatch: source has {placeholders(source)}, "
                    f"got {placeholders(value)}"
                )
            else:
                result.translated[key] = value
        progress(min(offset + batch_size, len(keys)), len(keys))

    return result
