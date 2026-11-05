"""校验 qdoctor 的依赖方向与第三方依赖。

规则：
- domain（model/rules/diagnose/rewrite/review）只能依赖 domain；
- infra（history/llm）只能依赖 domain 和 infra；
- entry（web/__main__）可以依赖任何本包模块；
- 除标准库外不允许第三方 import。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "qdoctor"

LAYERS = {
    "model": "domain",
    "rules": "domain",
    "diagnose": "domain",
    "rewrite": "domain",
    "review": "domain",
    "history": "infra",
    "llm": "infra",
    "web": "entry",
    "__main__": "entry",
    "__init__": "entry",
}

ALLOWED = {
    "domain": {"domain"},
    "infra": {"domain", "infra"},
    "entry": {"domain", "infra", "entry"},
}

STDLIB = set(sys.stdlib_module_names) | {"__future__"}


def main() -> int:
    if not PACKAGE.is_dir():
        print(f"ERROR: 找不到包目录 {PACKAGE}")
        return 1

    problems: list[str] = []
    scanned = 0
    for path in sorted(PACKAGE.glob("*.py")):
        scanned += 1
        layer = LAYERS.get(path.stem)
        if layer is None:
            problems.append(f"{path.name}: 未在 LAYERS 中登记")
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            problems.append(f"{path.name}: 语法错误：{exc}")
            continue

        for node in ast.walk(tree):
            for target in _targets(node):
                problem = _check(target, layer, path.name)
                if problem:
                    problems.append(problem)

    if problems:
        for problem in problems:
            print("ERROR:", problem)
        print(f"\n依赖检查失败：{len(problems)} 处")
        return 1

    print(f"依赖检查通过：扫描 {scanned} 个模块，方向与第三方依赖均合法。")
    return 0


def _targets(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        base = node.module or ""
        if node.level:
            base = "." * node.level + base
        if base.strip(".") == "":
            return [base + alias.name for alias in node.names]
        return [base]
    return []


def _check(target: str, layer: str, filename: str) -> str | None:
    if target.startswith("."):
        module = target.lstrip(".").split(".")[0]
        if not module:
            return None
        return _check_package_module(module, layer, filename)

    if target.startswith("qdoctor."):
        parts = target.split(".")
        return _check_package_module(parts[1], layer, filename)

    top = target.split(".")[0]
    if top == "qdoctor" or top in STDLIB:
        return None
    return f"{filename} 引入了第三方依赖 {top}（本项目只允许标准库）"


def _check_package_module(module: str, layer: str, filename: str) -> str | None:
    target_layer = LAYERS.get(module)
    if target_layer is None:
        # from . import __version__ 这类包属性，不是模块。
        return None
    if target_layer not in ALLOWED[layer]:
        return f"{filename}（{layer}）不能依赖 {module}（{target_layer}）"
    return None


if __name__ == "__main__":
    raise SystemExit(main())
