from modlang import ui


def test_style_disabled(monkeypatch):
    monkeypatch.setattr(ui, "COLOR", False)
    assert ui.style("hi", 1, 96) == "hi"
    assert ui.err("bad") == "bad"


def test_style_enabled(monkeypatch):
    monkeypatch.setattr(ui, "COLOR", True)
    assert ui.style("hi", 1, 96) == "\033[1;96mhi\033[0m"


def test_coverage_bar_fill(monkeypatch):
    monkeypatch.setattr(ui, "COLOR", False)
    bar = ui.coverage_bar(0.5, width=10)
    assert bar.count(ui.SYM["bar_full"]) == 5
    assert bar.count(ui.SYM["bar_empty"]) == 5
    assert "50%" in bar


def test_coverage_bar_clamps(monkeypatch):
    monkeypatch.setattr(ui, "COLOR", False)
    assert ui.coverage_bar(1.5, width=10).count(ui.SYM["bar_empty"]) == 0
    assert ui.coverage_bar(-0.2, width=10).count(ui.SYM["bar_full"]) == 0


def test_header_contains_title(monkeypatch):
    monkeypatch.setattr(ui, "COLOR", False)
    line = ui.header("botania", "some/path")
    assert "botania" in line and "some/path" in line
