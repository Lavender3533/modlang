import json

import pytest

from modlang.parser import LangParseError, dump_entries, format_of, parse_bytes


def test_format_of():
    assert format_of("en_us.json") == "json"
    assert format_of("en_US.lang") == "lang"
    with pytest.raises(LangParseError):
        format_of("readme.txt")


def test_parse_json_preserves_order():
    data = b'{"b.key": "Second", "a.key": "First %s"}'
    parsed = parse_bytes(data, "json")
    assert list(parsed.entries) == ["b.key", "a.key"]
    assert parsed.entries["a.key"] == "First %s"
    assert parsed.rich == {}


def test_parse_json_rejects_non_object():
    with pytest.raises(LangParseError):
        parse_bytes(b'["not", "a", "dict"]', "json")


def test_parse_json_neoforge_rich_values():
    # NeoForge allows JSON text components as values (seen in neoforge-21.x)
    component = [{"text": "Settings are server-controlled.", "color": "red"}]
    data = json.dumps({"ui.notonline": component, "plain": "Hello"}).encode()
    parsed = parse_bytes(data, "json")
    assert parsed.rich == {"ui.notonline": component}
    assert parsed.entries["ui.notonline"] == json.dumps(component, ensure_ascii=False)
    assert parsed.entries["plain"] == "Hello"


def test_dump_restores_rich_values():
    component = [{"index": 0}, {"text": " > ", "bold": True}]
    data = json.dumps({"breadcrumb": component, "plain": "Hi"}).encode()
    parsed = parse_bytes(data, "json")
    out = dump_entries(parsed.entries, "json", rich=parsed.rich)
    assert json.loads(out) == {"breadcrumb": component, "plain": "Hi"}


def test_parse_json_with_bom():
    parsed = parse_bytes("﻿{\"k\": \"v\"}".encode("utf-8"), "json")
    assert parsed.entries == {"k": "v"}


def test_parse_legacy_lang():
    data = (
        b"# comment line\n"
        b"\n"
        b"item.mod.thing.name=A Thing\n"
        b"tile.mod.block=Block with = sign\n"
    )
    parsed = parse_bytes(data, "lang")
    assert parsed.entries == {
        "item.mod.thing.name": "A Thing",
        "tile.mod.block": "Block with = sign",
    }


def test_parse_legacy_lang_bad_line():
    with pytest.raises(LangParseError):
        parse_bytes(b"no separator here\n", "lang")


def test_dump_roundtrip():
    entries = {"a": "中文 %s", "b": "line\nbreak"}
    assert parse_bytes(dump_entries(entries, "json").encode(), "json").entries == entries
    flat = {"a": "value", "b": "x=y"}
    assert parse_bytes(dump_entries(flat, "lang").encode(), "lang").entries == flat
