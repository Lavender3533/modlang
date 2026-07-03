import json
import zipfile

from modlang.discover import discover


def make_tree(root, namespace="mymod"):
    lang_dir = root / "assets" / namespace / "lang"
    lang_dir.mkdir(parents=True)
    (lang_dir / "en_us.json").write_text(
        json.dumps({"item.mymod.a": "Thing A", "item.mymod.b": "Thing B"}),
        encoding="utf-8",
    )
    (lang_dir / "zh_cn.json").write_text(
        json.dumps({"item.mymod.a": "物品甲"}), encoding="utf-8"
    )
    return lang_dir


def test_discover_dir(tmp_path):
    make_tree(tmp_path)
    sets = discover(tmp_path)
    assert len(sets) == 1
    langset = sets[0]
    assert langset.namespace == "mymod"
    assert langset.codes() == ["en_us", "zh_cn"]
    assert langset.files["en_us"].entries["item.mymod.a"] == "Thing A"
    assert langset.files["zh_cn"].path is not None


def test_discover_lang_dir_directly(tmp_path):
    lang_dir = make_tree(tmp_path)
    sets = discover(lang_dir)
    assert len(sets) == 1
    assert sets[0].namespace == "mymod"


def test_discover_jar(tmp_path):
    jar_path = tmp_path / "mymod-1.0.jar"
    with zipfile.ZipFile(jar_path, "w") as jar:
        jar.writestr("assets/mymod/lang/en_us.json", json.dumps({"k": "Value"}))
        jar.writestr("assets/mymod/lang/zh_cn.json", json.dumps({"k": "值"}))
        jar.writestr("assets/other/lang/en_US.lang", "k=Legacy Value\n")
        jar.writestr("META-INF/MANIFEST.MF", "")
    sets = discover(jar_path)
    assert [s.namespace for s in sets] == ["mymod", "other"]
    assert sets[0].files["zh_cn"].entries == {"k": "值"}
    assert sets[0].files["zh_cn"].path is None  # jars are read-only
    assert sets[1].files["en_us"].fmt == "lang"  # code normalized to lowercase


def test_discover_reports_parse_errors(tmp_path):
    lang_dir = make_tree(tmp_path)
    (lang_dir / "ja_jp.json").write_text("{broken", encoding="utf-8")
    sets = discover(tmp_path)
    assert len(sets[0].parse_errors) == 1
    assert "ja_jp" in sets[0].parse_errors[0]


def test_discover_skips_build_and_hidden_dirs(tmp_path):
    # the real source tree...
    src = tmp_path / "src" / "main" / "resources"
    src.mkdir(parents=True)
    make_tree(src)
    # ...plus copies in places nobody wants scanned
    for junk in ("build/sourcesSets/main", ".claude/worktrees/foo/src/main/resources",
                 "run/resourcepacks/pack", "target/classes"):
        junk_root = tmp_path.joinpath(*junk.split("/"))
        junk_root.mkdir(parents=True)
        make_tree(junk_root)

    sets = discover(tmp_path)
    assert len(sets) == 1
    assert "src" in sets[0].origin

    # explicitly pointing INTO an excluded dir still works
    inside = discover(tmp_path / "build" / "sourcesSets" / "main")
    assert len(inside) == 1
