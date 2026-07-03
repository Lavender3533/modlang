from modlang.checker import compare, placeholders


def test_placeholders():
    assert placeholders("Gives %s to %d players") == ["%s", "%d"]
    assert placeholders("Slot %1$s of %2$s") == ["%1$s", "%2$s"]
    assert placeholders("Damage: %.1f") == ["%.1f"]
    assert placeholders("100%% done") == []
    assert placeholders("no placeholders") == []


def test_compare_missing_and_extra():
    report = compare({"a": "A", "b": "B"}, {"b": "乙", "c": "丙"})
    assert report.missing == ["a"]
    assert report.extra == ["c"]
    assert report.error_count == 1
    assert report.warning_count == 1


def test_compare_empty_value():
    report = compare({"a": "Text"}, {"a": "   "})
    assert report.empty == ["a"]


def test_compare_placeholder_mismatch():
    report = compare({"a": "Give %s %d items"}, {"a": "给 %s 个物品"})
    assert len(report.placeholder_mismatch) == 1
    key, src, tgt = report.placeholder_mismatch[0]
    assert key == "a" and src == ["%s", "%d"] and tgt == ["%s"]


def test_compare_placeholder_reorder_is_ok():
    # word order legitimately changes across languages
    report = compare({"a": "%1$s gave %2$s"}, {"a": "%2$s 收到了 %1$s"})
    assert report.placeholder_mismatch == []


def test_compare_untranslated():
    report = compare(
        {"a": "Iron Sword", "brand": "Botania", "num": "%s"},
        {"a": "Iron Sword", "brand": "Botania", "num": "%s"},
    )
    # identical translatable text is flagged; proper-noun-ish and bare
    # placeholders are not distinguishable, so both letter-bearing values flag
    assert "a" in report.untranslated
    assert "num" not in report.untranslated


def test_compare_clean():
    report = compare({"a": "Sword %s"}, {"a": "剑 %s"})
    assert report.clean
