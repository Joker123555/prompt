# prompt 文档

按"你想做什么"选入口，不要按目录树找。

## 上手（5 分钟跑起来）

- [快速开始](guides/getting-started.md) —— 装依赖、跑起来、验证成功
- [环境要求](guides/getting-started.md#环境要求)

## 架构（系统由什么组成）

<!-- blueprint:begin docs/architecture -->
（生成后请用 5 行以内说清：系统由哪几层组成、每层的职责、依赖方向。写不出来说明架构还没定型，先别写长文。）
<!-- blueprint:end docs/architecture -->

每个目录一句话职责见 [目录职责](architecture/directories.md)；依赖方向见 [AGENTS.md](../AGENTS.md)。

## 开发（改这类需求要动哪里）

- [开发指南](guides/development.md) —— 改代码、跑增量构建、加依赖
- [决策记录](decisions/README.md) —— 为什么当初这么选

## 测试

- [测试指南](guides/testing.md) —— 怎么加测试、跑哪些、什么算通过

## 发布

- [发布流程](guides/release.md)

---
维护规则：本文件中带 blueprint:begin / blueprint:end 注释标记包裹的部分由 blueprint 工具生成，重跑会覆盖；其余内容手写维护，重跑不会动。
