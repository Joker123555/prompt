# 目录职责

每行格式固定为：**目录 —— 拥有什么 + 不拥有什么**。后半句比前半句重要。

<!-- blueprint:begin docs/architecture/directories -->
| `qdoctor/` | 诊断、改写、复盘、历史、LLM 与入口；不含第三方依赖和构建产物 |
| `qdoctor/static/` | 单页界面（HTML/CSS/JS）；不含业务规则 |
| `tests/` | 与被测模块对应的单元/接口测试；不含生产逻辑 |
| `tools/` | 仓库校验脚本；不含产品代码 |
| `docs/` | 文档入口与指南；不含代码 |
| `artifacts/` | 长命令输出；不进版本库 |
<!-- blueprint:end docs/architecture/directories -->

## 分层与依赖方向

```
qdoctor/static → qdoctor/web（入口）
qdoctor/__main__ → 以下所有
qdoctor/{diagnose,rewrite,review} → qdoctor/{model,rules}（领域）
qdoctor/{history,llm} → qdoctor/{model,rules}（基础设施）
```

领域层不得导入 `history` / `llm` / `web` / `__main__`；基础设施不得导入 `web` / `__main__`；任何模块不得引入第三方依赖。以上由 `tools/check_layers.py` 用 AST 检查。

## 反例

以下目录名一旦出现，说明边界没想清楚，它们会稳定吸走本该归位的代码：
`utils` / `common` / `helpers` / `misc` / `temp` / `legacy` / `new` / `core`（除非它真是中枢）。

需要共享能力时用能力名代替：`crypto` / `validation` / `formatting`。
