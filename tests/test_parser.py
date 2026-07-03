import pytest

from modlang.parser import LangParseError, dump_entries, format_of, parse_bytes


def test_format_of():
    assert format_of("en_us.json") == "json"
    assert format_of("en_US.lang") == "lang"
    with pytest.raises(LangParseError):
        format_of("readme.txt")


def test_parse_json_preserves_order():
    data = b'{"b.key": "Second", "a.key": "First %s"}'
    entries = parse_bytes(data, "json")
    assert list(entries) == ["b.key", "a.key"]
    assert entries["a.key"] == "First %s"


def test_parse_json_rejects_non_string_values():
    with pytest.raises(LangParseError):
        parse_bytes(b'{"key": 42}', "json")
    with pytest.raises(LangParseError):
        parse_bytes(b'["not", "a", "dict"]', "json")


def test_parse_json_with_bom():
    entries = parse_bytes("﻿{\"k\": \"v\"}".encode("utf-8"), "json")
    assert entries == {"k": "v"}


def test_parse_legacy_lang():
    data = (
        b"# comment line\n"
        b"\n"
        b"item.mod.thing.name=A Thing\n"
        b"tile.mod.block=Block with = sign\n"
    )
    entries = parse_bytes(data, "lang")
    assert entries == {
        "item.mod.thing.name": "A Thing",
        "tile.mod.block": "Block with = sign",
    }


def test_parse_legacy_lang_bad_line():
    with pytest.raises(LangParseError):
        parse_bytes(b"no separator here\n", "lang")


def test_dump_roundtrip():
    entries = {"a": "中文 %s", "b": "line\nbreak"}
    assert parse_bytes(dump_entries(entries, "json").encode(), "json") == entries
    flat = {"a": "value", "b": "x=y"}
    assert parse_bytes(dump_entries(flat, "lang").encode(), "lang") == flat
