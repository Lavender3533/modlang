import json

import pytest

from modlang import translate
from modlang.translate import TranslationResult, _extract_json_object, translate_entries


def test_extract_json_plain():
    assert _extract_json_object('{"a": "b"}') == {"a": "b"}


def test_extract_json_with_fences():
    text = 'Sure! Here you go:\n```json\n{"a": "б"}\n```'
    assert _extract_json_object(text) == {"a": "б"}


def test_extract_json_missing():
    with pytest.raises(translate.TranslateError):
        _extract_json_object("no json here")


def test_translate_entries_validates_placeholders(monkeypatch):
    def fake_chat(api_base, api_key, model, system, user, timeout=120.0):
        batch = json.loads(user)
        answer = {}
        for key, value in batch.items():
            if key == "bad":
                answer[key] = "占位符丢了"          # drops the %s
            elif key == "skip":
                pass                                 # missing from response
            else:
                answer[key] = "翻译:" + value
        return json.dumps(answer, ensure_ascii=False)

    monkeypatch.setattr(translate, "_chat", fake_chat)
    entries = {"good": "Hello %s", "bad": "Give %s", "skip": "Bye"}
    result = translate_entries(
        entries, "zh_cn", api_base="http://x", api_key="k", model="m", batch_size=10
    )
    assert isinstance(result, TranslationResult)
    assert result.translated == {"good": "翻译:Hello %s"}
    assert "placeholder mismatch" in result.failed["bad"]
    assert result.failed["skip"] == "missing from model response"


def test_translate_entries_batching(monkeypatch):
    calls = []

    def fake_chat(api_base, api_key, model, system, user, timeout=120.0):
        batch = json.loads(user)
        calls.append(len(batch))
        return json.dumps({k: "译" + v for k, v in batch.items()}, ensure_ascii=False)

    monkeypatch.setattr(translate, "_chat", fake_chat)
    entries = {f"k{i}": f"Value {i}" for i in range(25)}
    result = translate_entries(
        entries, "zh_cn", api_base="http://x", api_key="k", model="m", batch_size=10
    )
    assert calls == [10, 10, 5]
    assert len(result.translated) == 25
