# prompt · qdoctor

一个本地小工具：在把问题发给 AI 之前，先检查它缺了什么。

它不替你写提示词，也不判断答案对错。它做三件事：

- **体检**：指出目标、背景、约束、期望输出、验收标准、受众、示例里缺了哪几块，给出追问清单和可直接粘贴的改写稿。
- **复盘**：上一轮答非所问时，选一个“哪里不对”，生成下一轮追问。
- **统计**：本地记录分数与缺口，看看你最常漏掉什么。

规则驱动、零第三方依赖、默认不联网；LLM 润色可选。

## 快速开始

<!-- blueprint:begin readme/quickstart -->
```bash
python -m qdoctor check "帮我优化一下"
python -m qdoctor serve --port 8765 --open
```
<!-- blueprint:end readme/quickstart -->

需要 Python 3.11+（当前环境 3.12.10），无需安装依赖。更多用法：

```bash
python -m qdoctor check --file question.txt --json
python -m qdoctor check "..." --llm
python -m qdoctor review -q "原问题" -a "AI 的回答" -p too_general
python -m qdoctor stats --last 30
```

## 验证

```bash
python -m unittest discover -s tests -t . -v
python tools/check_layers.py
python tools/blueprint_verify.py
```

## 可选 LLM

默认关闭。配置后加 `--llm`（CLI）或勾选网页开关：

```bash
export QDOCTOR_LLM_BASE_URL=https://api.deepseek.com/v1
export QDOCTOR_LLM_API_KEY=...
export QDOCTOR_LLM_MODEL=deepseek-chat
```

任何 OpenAI 兼容的 chat completions 端点都行。开启后只发送当前问题（复盘时加上一轮回答），不发送历史记录；历史文件里也不存问题原文。

## 仓库

主仓库在 GitHub：`https://github.com/Joker123555/prompt.git`（`Joker123555`）。公司 Gitea `https://git.zxyuanyu.com/lijin/prompt.git` 保留为 `origin` 镜像。

```bash
git clone https://github.com/Joker123555/prompt.git
```

本机直连 github.com 不通，需为 git 配置系统代理 `http://127.0.0.1:7890`。

## 进一步阅读

- [AGENTS.md](AGENTS.md) —— 工程约定与 AI agent 操作规程（**改代码前先读**）
- [docs/index.md](docs/index.md) —— 文档入口
- [真实对话案例复盘](docs/cases/README.md) —— 怎么把模糊意图问成可执行请求；为什么 AI 会把设计思路印到页面上
- [blueprint.yaml](blueprint.yaml) —— 项目声明（入口命令、模块清单）
- [OWNERS.yaml](OWNERS.yaml) —— 归属与评审
- [docs/decisions/0001-rule-first-question-diagnosis.md](docs/decisions/0001-rule-first-question-diagnosis.md) —— 为什么规则优先、LLM 可选

## 仓库结构

```
qdoctor/         诊断、改写、复盘、历史、LLM 与入口
qdoctor/static/  单页界面
tests/           与模块对应的测试
tools/           仓库校验脚本
docs/            文档
artifacts/       长命令输出（不进版本库）
```
