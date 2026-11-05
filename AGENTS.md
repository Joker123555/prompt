# AGENTS.md —— prompt

本文件是给 AI agent 与人共同看的操作规程，不是项目介绍。项目介绍在 README.md。
**根文件只写全局约束**；子系统有特殊规矩时，在该目录放自己的 AGENTS.md，内容只写差异。

## 1. 这是什么

`prompt` 是提问体检工具 `qdoctor`：在把问题发给 AI 前，指出缺失的要素、给出追问清单与改写稿；支持复盘答非所问的对话、统计本地缺口。它不替用户写提示词，也不判断答案对错。

技术栈：Python 3.12 标准库，零第三方依赖。分档：S（S = 小仓，只靠目录与本文档；M = 加声明层与文档站；L = 全量治理）。

## 2. 入口命令（唯一入口，别自己发明）

<!-- blueprint:begin agents/entrypoints -->
| 目的 | 命令 |
|---|---|
| 装依赖 | `python -c "import qdoctor"`（零依赖，验证包可导入） |
| 全量构建 | `python -m compileall -q qdoctor`（无编译产物，做语法编译检查） |
| 增量开发 | `python -m qdoctor serve` |
| 跑测试 | `python -m unittest discover -s tests -t . -v` |
| 格式化/静态检查 | `python tools/check_layers.py`（依赖方向与第三方依赖） |
<!-- blueprint:end agents/entrypoints -->

以上命令全部经过实测（实测于 2026-11-05）。命令不存在时先怀疑环境，不要去改脚本绕过。

## 3. 目录与职责

<!-- blueprint:begin agents/directories -->
| `qdoctor/` | 诊断、改写、复盘、历史、LLM 与入口；不含第三方依赖和构建产物 |
| `qdoctor/static/` | 单页界面（HTML/CSS/JS）；不含业务规则 |
| `tests/` | 与被测模块对应的单元/接口测试；不含生产逻辑 |
| `tools/` | 仓库校验脚本；不含产品代码 |
| `docs/` | 文档入口与指南；不含代码 |
| `artifacts/` | 长命令输出；不进版本库 |
<!-- blueprint:end agents/directories -->

每个目录一句话：**拥有什么 + 不拥有什么**。想放代码时先回答"它属于哪个目录的职责"，答案不清楚说明该目录的边界需要重新讨论，不要把代码塞进最近的目录。

## 4. 依赖方向（硬约束）

```
qdoctor/static → qdoctor/web（入口）
qdoctor/__main__ → 以下所有
qdoctor/{diagnose,rewrite,review} → qdoctor/{model,rules}（领域）
qdoctor/{history,llm} → qdoctor/{model,rules}（基础设施）
```

- 领域层（`model` / `rules` / `diagnose` / `rewrite` / `review`）不得导入 `history` / `llm` / `web` / `__main__`。
- 基础设施（`history` / `llm`）不得导入 `web` / `__main__`。
- 任何 `qdoctor/` 模块不得引入第三方依赖。
- `tools/check_layers.py` 用 AST 检查以上三条；违反即 lint 失败。

违反方向的 import 不接受，即使它"现在能跑"。

## 5. 铁律

1. **先看目录和声明文件，再搜索。** 不要一上来就全仓正则；先读 `docs/index.md`、相关目录的 MODULE.yaml、以及目标目录的文件清单。全库搜索只在确认范围后使用。
2. **引用名字，不引用位置。** 说明某段逻辑时写函数名/符号名。确需行号时，必须给出带 commit sha 的永久链接，例如 `https://host/prompt/blob/<sha>/<path>#L10-L20`；不要写 `<path>:120` 这种一旦重构就腐烂的形式。
3. **长输出落文件。** 构建、测试、抓取等超过约 100 行的输出，重定向到 `artifacts/` 下的文件再按需读取，不要用管道 tail/grep 截断在一次性的终端里。
4. **不可自动跨越的动作。** 提交、推送、发布、删除远端资源、改生产配置——必须先得到人的明确同意，然后才执行。拿不到同意就停下来问。
5. **不完全理解就不改。** 你是最后一道评审；看不懂的代码不要"顺手优化"。补丁小而聚焦，不夹带无关重构。
6. **远端只有公司 Gitea。** 本仓库托管在 `https://git.zxyuanyu.com/lijin/prompt.git`（`git.zxyuanyu.com` / `lijin`）。禁止把代码推到 github.com、gitee.com、gitlab.com 等任何外部托管；`git remote` 里出现外部地址视为配置事故，先改回公司地址再做事。
   - **首次推送**：人类已在 `https://git.zxyuanyu.com/repo/create` 建好同名私有仓库后，执行 `git push -u origin main`；远端已存在则跳过此步。
   - **无人值守推送**（环境里有 `GITEA_TOKEN` 时，agent 可直接用）：`git push https://lijin:$GITEA_TOKEN@git.zxyuanyu.com/lijin/prompt.git main`。令牌只用于这一次 URL，**禁止写进 `.git/config`、文档或提交**；推送后 `git remote -v` 必须仍是不带令牌的地址。
   - 推送仍受铁律 4 约束：先提交、先跑测试、拿到人的明确同意，再推。

## 6. 测试

- 改动必须带证据：跑 `python -m unittest discover -s tests -t . -v` 和 `python tools/check_layers.py`，贴出实际输出，再说"通过"。
- 修 bug 时先写一个能复现的失败测试，再修。
- 测试放在 `tests/`，与被测模块同名：`qdoctor/diagnose.py` 对应 `tests/test_diagnose.py`。

## 7. 文档

- 文档入口 `docs/index.md`；模块文档就近放在模块目录的 docs/ 下。
- 任何"表格型事实"（命令清单、模块清单、责任人）以声明文件为准；文档里的表格若与声明文件不一致，以声明文件为准并修文档。
- 不要新引入第二种文档标记语言。

## 8. 归属与评审

归属以 `OWNERS.yaml` 为准。改动了某模块时，按其中的 path glob 找到 owner 组，组必须在评审里出现。
关键模块带 `blocking: true`：没有该组批准不得合并。

## 9. 已知陷阱

- **Windows 控制台编码**：入口已统一 UTF-8；自己写脚本读文件时仍要显式 `encoding="utf-8"`，否则 cp936 会炸。
- **端口占用**：`serve` 默认 8765；冲突时用 `--port 0` 自动选端口，或换一个端口，不要偷偷改默认值。
- **LLM 默认关闭**：不设环境变量时 `--llm` 退出码是 1，但规则结果仍会完整输出；不要把 1 当成整个命令失败。
- **历史不存原文**：`~/.qdoctor/history.jsonl` 只有分数、缺口和字符数；调试时不要断言"记录里能查到问题文本"。

## 10. 保持本文档有效

本文件中被下列标记包裹的区块由 `blueprint` 工具生成，重跑会覆盖；标记之外的内容不会被改动：

```
<!-- blueprint:begin <区块名> -->
...
<!-- blueprint:end <区块名> -->
```

手工内容请写在标记之外。需要新增命令时，先加到 `blueprint.yaml` 再重跑，而不是只改这张表。
