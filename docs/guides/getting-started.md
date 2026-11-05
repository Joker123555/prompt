# 快速开始

## 环境要求

- 未指定
- 具体版本：见 blueprint.yaml

## 装依赖

<!-- blueprint:begin guides/getting-started/install -->
```bash
（未指定技术栈，请手工填写）
```
<!-- blueprint:end guides/getting-started/install -->

## 跑起来

```bash
（未指定技术栈，请手工填写）
```

## 确认装对了

```bash
（未指定技术栈，请手工填写）
```

看到测试全绿就算成功。若失败，先看本文末尾的"常见问题"，不要去改脚本绕过。

## 常见问题

- **命令找不到**：多半是依赖没装或没激活环境，回到上面第 2 步。
- **端口被占用**：换一个端口，不要改默认值。
- **构建产物很旧**：删掉构建目录重来；增量构建在改了 blueprint.yaml 或锁文件后不可靠。
