# 目录职责

每行格式固定为：**目录 —— 拥有什么 + 不拥有什么**。后半句比前半句重要。

<!-- blueprint:begin docs/architecture/directories -->
| docs/ | 文档入口与指南；不含代码 |
| artifacts/ | 长命令输出；不进版本库 |
<!-- blueprint:end docs/architecture/directories -->

## 分层与依赖方向

（按实际架构填写：谁可以依赖谁，哪些方向禁止）

## 反例

以下目录名一旦出现，说明边界没想清楚，它们会稳定吸走本该归位的代码：
`utils` / `common` / `helpers` / `misc` / `temp` / `legacy` / `new` / `core`（除非它真是中枢）。

需要共享能力时用能力名代替：`crypto` / `validation` / `formatting`。
