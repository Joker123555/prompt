# 测试指南

## 跑测试

```bash
python -m unittest discover -s tests -t . -v
```

## 什么算通过

命令退出码为 0，且你**看到**了 `OK` 与通过数。没看到输出的"应该没问题"不算通过。

## 写测试的要求

- 修 bug：先写一个能复现的失败测试，再修；
- 新功能：至少一个正常路径 + 一个边界；
- 测试名说清行为（`test_missing_acceptance_is_flagged`），不要写 `test1`；
- 测试不依赖网络、不依赖当前时间、不依赖执行顺序；
- 网页测试用 `web.make_server(..., 0)` 选临时端口；
- LLM 测试注入 `transport`，不要真的发请求。

## 测试放哪

`tests/`，与被测模块同名：`qdoctor/diagnose.py` 对应 `tests/test_diagnose.py`。领域层测试是纯函数测试，不需要启动任何东西。
