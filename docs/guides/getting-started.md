# 快速开始

## 环境要求

- Python 3.11+（实测 3.12.10）
- 无第三方依赖；不需要虚拟环境也能跑

## 装依赖

<!-- blueprint:begin guides/getting-started/install -->
```bash
python -c "import qdoctor"
```
<!-- blueprint:end guides/getting-started/install -->

这条命令没有输出就说明包可导入。本项目不装任何第三方包。

## 跑起来

```bash
python -m qdoctor check "帮我优化一下"
```

会输出分数、七个要素的诊断、追问清单和可直接粘贴的改写稿。

网页版：

```bash
python -m qdoctor serve --port 8765 --open
```

默认只监听 `127.0.0.1`，数据不出机器。端口被占用时用 `--port 0` 自动选端口。

## 确认装对了

```bash
python -m unittest discover -s tests -t . -v
python tools/check_layers.py
```

看到 `OK` 和“依赖检查通过”就算成功。若失败，先看下面的“常见问题”，不要去改脚本绕过。

## 常见问题

- **`No module named qdoctor`**：确认当前目录是仓库根目录，或把仓库根目录加进 `PYTHONPATH`。
- **端口被占用**：用 `--port 0` 或换一个端口，不要改默认值。
- **`--llm` 返回 1**：说明没配 `QDOCTOR_LLM_BASE_URL` / `QDOCTOR_LLM_API_KEY` / `QDOCTOR_LLM_MODEL`；规则结果仍然会输出。
- **终端中文乱码**：入口已统一 UTF-8；旧版 Windows 控制台建议改用 Windows Terminal。
