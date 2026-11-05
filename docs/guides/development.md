# 开发指南

## 目录与职责

先读 [目录职责](../architecture/directories.md)，再决定代码写到哪。
不知道该放哪时问一句"这个目录拥有什么、不拥有什么"，答案不清就说明边界要重议。

## 依赖方向

```
qdoctor/static → qdoctor/web（入口）
qdoctor/__main__ → 以下所有
qdoctor/{diagnose,rewrite,review} → qdoctor/{model,rules}（领域）
qdoctor/{history,llm} → qdoctor/{model,rules}（基础设施）
```

领域层不得导入 `history` / `llm` / `web` / `__main__`；基础设施不得导入 `web` / `__main__`；任何模块不得引入第三方依赖。`python tools/check_layers.py` 会拦截违规 import。

## 加一个功能的标准动作

1. 需要新词表/新槽位时，先改 `qdoctor/rules.py`（数据），不要先改检测流程；
2. 在 `diagnose` / `rewrite` / `review` 里写纯函数，不碰 I/O、不碰框架；
3. 在 `tests/` 加一个能失败的测试，再让它通过；
4. 跑 `python -m unittest discover -s tests -t . -v` 和 `python tools/check_layers.py`，贴出真实输出；
5. 更新受影响的文档（就近写在模块的 docs/ 里）。

## 增量开发

```bash
python -m qdoctor serve --port 8765
```

改 `qdoctor/static/` 下的文件刷新浏览器即可；改 Python 文件需要重启进程。本项目没有编译产物，`python -m compileall -q qdoctor` 只做语法检查。

## 长输出

构建/测试输出超过约 100 行时，重定向到 `artifacts/` 再读，不要用管道截断。

## 加依赖的原则

- 本项目只允许标准库；`tools/check_layers.py` 会把第三方 import 判为失败；
- 确实需要第三方库时，先在 ADR 里写清“为什么标准库不够”，再改分层检查的规则；
- 依赖锁文件必须提交。
