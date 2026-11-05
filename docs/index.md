# prompt 文档

按"你想做什么"选入口，不要按目录树找。

## 上手（5 分钟跑起来）

- [快速开始](guides/getting-started.md) —— 装依赖、跑起来、验证成功
- [环境要求](guides/getting-started.md#环境要求)

## 架构（系统由什么组成）

<!-- blueprint:begin docs/architecture -->
- 入口层：`qdoctor/__main__.py`（CLI）与 `qdoctor/web.py`（本地 HTTP）。
- 领域层：`diagnose` 检测槽位与反模式，`rewrite` 生成七段式改写稿，`review` 生成下一轮追问；全部是纯函数。
- 数据层：`rules.py` 放槽位、词表与权重；校准只改数据，不改检测流程。
- 基础设施：`history.py` 写本地 JSONL（只存元数据），`llm.py` 是可选的 OpenAI 兼容适配器。
- 依赖方向：入口 → 领域/基础设施 → 数据；由 `tools/check_layers.py` 强制。
<!-- blueprint:end docs/architecture -->

每个目录一句话职责见 [目录职责](architecture/directories.md)；依赖方向见 [AGENTS.md](../AGENTS.md)。

## 案例（真实对话复盘）

- [从模糊意图到可验收请求](cases/0001-from-vague-intent-to-a-checkable-request.md) —— 做 qdoctor 这次对话的复盘：哪些动作起了作用，哪里漏了场景
- [指令与素材：为什么 AI 把设计思路印在了页面上](cases/0002-instructions-vs-content.md) —— 长文本里“要求”和“文案”没分开

## 开发（改这类需求要动哪里）

- [开发指南](guides/development.md) —— 改代码、跑增量构建、加依赖
- [决策记录](decisions/README.md) —— 为什么当初这么选

## 测试

- [测试指南](guides/testing.md) —— 怎么加测试、跑哪些、什么算通过

## 发布

- [发布流程](guides/release.md)

---
维护规则：本文件中带 blueprint:begin / blueprint:end 注释标记包裹的部分由 blueprint 工具生成，重跑会覆盖；其余内容手写维护，重跑不会动。
