"""End-to-end smoke tests running the CLI in-process (also guards cli.py
against syntax that older supported Pythons reject, since nothing else
imports it)."""

import json

import pytest

from modlang import cli


def make_tree(root):
    lang = root / "assets" / "mymod" / "lang"
    lang.mkdir(parents=True)
    (lang / "en_us.json").write_text(
        json.dumps({"a": "Thing %s", "b": "Other"}), encoding="utf-8"
    )
    (lang / "zh_cn.json").write_text(
        json.dumps({"a": "物品 %s"}), encoding="utf-8"
    )


def run(argv):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)
    return excinfo.value.code


def test_list_shows_coverage(tmp_path, capsys):
    make_tree(tmp_path)
    assert run(["list", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "mymod" in out
    assert "en_us" in out and "(source" in out
    assert "50%" in out  # zh_cn covers 1 of 2 source keys


def test_check_finds_missing_and_exit_code(tmp_path, capsys):
    make_tree(tmp_path)
    assert run(["check", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "missing" in out and "b" in out


def test_check_json_mode(tmp_path, capsys):
    make_tree(tmp_path)
    assert run(["check", str(tmp_path), "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data[0]["lang"] == "zh_cn"
    assert data[0]["missing"] == ["b"]


def test_check_clean_exit_zero(tmp_path, capsys):
    lang = tmp_path / "assets" / "m" / "lang"
    lang.mkdir(parents=True)
    (lang / "en_us.json").write_text(json.dumps({"a": "Hi %s"}), encoding="utf-8")
    (lang / "zh_cn.json").write_text(json.dumps({"a": "你好 %s"}), encoding="utf-8")
    assert run(["check", str(tmp_path)]) == 0
    assert "all clean" in capsys.readouterr().out


def test_translate_dry_run(tmp_path, capsys):
    make_tree(tmp_path)
    assert run(["translate", str(tmp_path), "--lang", "zh_cn", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "1" in out and "missing" in out and "'Other'" in out


def test_exclude_flag(tmp_path, capsys):
    make_tree(tmp_path)
    vendor = tmp_path / "vendor-mod"
    vendor.mkdir()
    make_tree(vendor)
    assert run(["list", str(tmp_path), "--exclude", "vendor*"]) == 0
    out = capsys.readouterr().out
    assert "vendor-mod" not in out
    assert "mymod" in out
