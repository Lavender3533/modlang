# modlang

> Lint, diff and auto-translate Minecraft mod language files — straight from a resources folder or a mod jar.

[![CI](https://github.com/Lavender3533/modlang/actions/workflows/ci.yml/badge.svg)](https://github.com/Lavender3533/modlang/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)

[English](#english) | [简体中文](#简体中文)

---

## English

Keeping `zh_cn.json` in sync with `en_us.json` by hand is miserable. **modlang** does it for you:

- **Check** translations against the source language: missing keys, empty values, keys left untranslated, extra/orphaned keys, and **Java format placeholder mismatches** (`%s`, `%1$s`, `%.1f`) that crash the game at runtime.
- **Scan anything**: a `src/main/resources` folder, an extracted resource pack, a single lang file — or a **mod jar directly**, no unzipping needed. Build outputs and hidden folders (`build/`, `target/`, `run/`, `.git`, `.gradle`...) are skipped automatically.
- **Both formats**: modern `.json` (1.13+) and legacy `.lang` (≤1.12), including NeoForge rich-text component values.
- **Auto-translate** missing keys through any **OpenAI-compatible API** (OpenAI, DeepSeek, Ollama, one-api/new-api gateways...), with placeholder and `§` formatting-code protection built in.
- **Zero dependencies.** Pure Python standard library. `pip install` and go.
- **CI-friendly**: `--json` output and meaningful exit codes.

### Install

```bash
pip install modlang        # from PyPI (soon)
pip install git+https://github.com/Lavender3533/modlang
```

### Check translations

```bash
modlang check ./src/main/resources            # a dev workspace
modlang check mymod-1.2.3.jar                 # a built jar, directly
modlang check . --lang zh_cn --lang ja_jp     # only specific languages
```

Real output against [Botania](https://github.com/VazkiiMods/Botania)'s resources:

```
botania  D:\Botania\Xplat\src\main\resources\assets\botania\lang
  zh_cn    45 missing, 74 untranslated, 2 extra
      missing: botaniamisc.sextantMode.circle_x
      missing: botaniamisc.catalyst_not_consumed
      missing: tag.botania.shimmering_mushrooms
      ... 40 more (use -v to show all)
45 error(s), 76 warning(s)
```

Exit code is `1` when there are errors (missing / empty / placeholder mismatch), `0` otherwise.
Add `--strict` to fail on warnings too, `--json` for machine-readable output.

### Auto-translate missing keys

```bash
export MODLANG_API_BASE=https://api.deepseek.com/v1   # any OpenAI-compatible endpoint
export MODLANG_API_KEY=sk-...
export MODLANG_MODEL=deepseek-chat

modlang translate ./src/main/resources --lang zh_cn --dry-run   # preview first
modlang translate ./src/main/resources --lang zh_cn             # write zh_cn.json
```

Existing translations are never overwritten — only missing keys are filled in, and the
output keeps `en_us.json`'s key order so diffs stay reviewable. Any entry where the model
mangled a placeholder is rejected and reported instead of written.

### Use in GitHub Actions

```yaml
- run: pip install git+https://github.com/Lavender3533/modlang
- run: modlang check ./src/main/resources --lang zh_cn
```

### All commands

| Command | What it does |
|---|---|
| `modlang list [PATH]` | list every language file found, with key counts |
| `modlang check [PATH]` | compare translations against `--source` (default `en_us`) |
| `modlang translate [PATH] --lang CODE` | fill missing keys via an LLM |

---

## 简体中文

手动维护 `zh_cn.json` 和 `en_us.json` 的同步非常痛苦。**modlang** 帮你解决：

- **检查**翻译文件：缺失的键、空值、忘了翻的条目、多余的孤儿键，以及会导致游戏运行时报错的 **Java 占位符不匹配**（`%s`、`%1$s`、`%.1f`）。
- **什么都能扫**：`src/main/resources` 目录、解包后的资源包、单个语言文件，甚至**直接扫 mod 的 jar 包**，不用解压。
- **两种格式都支持**：新版 `.json`（1.13+）和老版 `.lang`（1.12 及以前）。
- **自动补翻**：通过任意 **OpenAI 兼容 API**（OpenAI、DeepSeek、Ollama、one-api/new-api 中转站……）翻译缺失条目，内置占位符和 `§` 格式代码保护。
- **零依赖**，纯标准库实现，装上就能用。
- **适合 CI**：支持 `--json` 输出和规范的退出码。

### 安装

```bash
pip install git+https://github.com/Lavender3533/modlang
```

### 检查翻译

```bash
modlang check ./src/main/resources          # 开发目录
modlang check mymod-1.2.3.jar               # 直接检查 jar 包
modlang check . --lang zh_cn                # 只检查中文
```

有错误（缺失/空值/占位符不匹配）时退出码为 `1`，可以直接接进 CI。
`--strict` 把警告也算作失败；`--json` 输出机器可读结果；`-v` 显示全部问题键。

### 自动补翻缺失条目

```bash
set MODLANG_API_BASE=https://api.deepseek.com/v1
set MODLANG_API_KEY=sk-...
set MODLANG_MODEL=deepseek-chat

modlang translate ./src/main/resources --lang zh_cn --dry-run   # 先预览
modlang translate ./src/main/resources --lang zh_cn             # 写入 zh_cn.json
```

已有的翻译**永远不会被覆盖**，只补缺失的键；输出保持 `en_us.json` 的键顺序，方便 review。
模型弄丢占位符的条目会被拒绝并报告，不会写进文件。

### 汉化组工作流建议

1. `modlang check mod.jar --lang zh_cn -v` —— 摸清还差多少
2. `modlang translate ... --dry-run` —— 看看要翻哪些
3. `modlang translate ... --lang zh_cn` —— LLM 出初稿
4. 人工校对 `same as source` 和机翻条目
5. 把 `modlang check --strict` 挂进 CI，从此不再漏翻

---

## Support / 赞助与定制

If modlang saves you time, consider starring the repo ⭐

有定制需求（私有 mod 工具链、汉化流水线搭建等）或者想请我喝杯咖啡：
- 爱发电：*coming soon*
- 或直接开 [issue](https://github.com/Lavender3533/modlang/issues) 聊

## License

[MIT](LICENSE)
