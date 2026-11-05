#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blueprint_verify.py —— 契约校验器。

它只做一件事：让"写了但没生效"的配置当场失败，而不是三个月后由某个人发现。

四条门禁：
  1. 结构     blueprint.yaml / AGENTS.md / 文档入口 / 模块目录 存在
  2. 入口     entrypoints 里每条命令都能被解析到（工具存在 + 脚本/目标存在）
  3. 文档     docs 里的链接与行内代码路径，指向真实存在的文件
  4. 声明     MODULE.yaml / OWNERS.yaml 的每条 glob 至少命中 1 个文件（命中 0 = 死配置）

退出码：0 全过；1 有错误；2 配置本身读不了。

用法：
  python tools/blueprint_verify.py
  python tools/blueprint_verify.py --json
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "dist", "build", "target",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "artifacts",
    ".blueprint", ".idea", ".vscode", "vendor", "third_party",
}

PATH_EXT = (
    ".md", ".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".toml", ".yaml", ".yml",
    ".json", ".sh", ".cmd", ".ps1", ".txt", ".cfg", ".ini", ".html", ".css",
)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passed: list[str] = []

    def error(self, check: str, msg: str) -> None:
        self.errors.append(check + " | " + msg)

    def warn(self, check: str, msg: str) -> None:
        self.warnings.append(check + " | " + msg)

    def ok(self, check: str, msg: str) -> None:
        self.passed.append(check + " | " + msg)


try:
    import yaml  # type: ignore
    HAVE_YAML = True
except Exception:
    HAVE_YAML = False


def _split_inline(text: str) -> list[str]:
    parts, buf, depth, quote = [], [], 0, ""
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _scalar(text: str):
    t = text.strip()
    if not t:
        return None
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    low = t.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    if re.fullmatch(r"-?\d+\.\d+", t):
        return float(t)
    if t.startswith("[") and t.endswith("]"):
        inner = t[1:-1].strip()
        return [] if not inner else [_scalar(x) for x in _split_inline(inner)]
    return t


def _lines(text: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        expanded = raw.expandtabs(2)
        indent = len(expanded) - len(expanded.lstrip(" "))
        body = expanded.strip()
        cut = body.find(" #")
        if cut >= 0:
            body = body[:cut].rstrip()
        if not body:
            continue
        rows.append((indent, body))
    return rows


def _mini_yaml(text: str):
    rows = _lines(text)

    def parse(i: int, indent: int):
        if i >= len(rows):
            return None, i
        if rows[i][1].startswith("- "):
            seq = []
            while i < len(rows) and rows[i][0] == indent and rows[i][1].startswith("- "):
                body = rows[i][1][2:].strip()
                i += 1
                if re.match(r"^[A-Za-z0-9_.-]+\s*:", body):
                    key, _, rest = body.partition(":")
                    item: dict = {}
                    if rest.strip():
                        item[key.strip()] = _scalar(rest)
                    if i < len(rows) and rows[i][0] > indent:
                        deeper, i = parse(i, rows[i][0])
                        if isinstance(deeper, dict):
                            item.update(deeper)
                    seq.append(item)
                else:
                    seq.append(_scalar(body))
            return seq, i
        mapping: dict = {}
        while i < len(rows) and rows[i][0] == indent and not rows[i][1].startswith("- "):
            body = rows[i][1]
            if ":" not in body:
                i += 1
                continue
            key, _, rest = body.partition(":")
            key = key.strip()
            i += 1
            if rest.strip():
                mapping[key] = _scalar(rest)
            elif i < len(rows) and rows[i][0] > indent:
                value, i = parse(i, rows[i][0])
                mapping[key] = value
            else:
                mapping[key] = None
        return mapping, i

    if not rows:
        return {}
    value, _ = parse(0, rows[0][0])
    return value if isinstance(value, dict) else {}


def load_yaml(path: Path, rep: Report, label: str) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        rep.error("yaml", label + ": 读不了（" + str(exc) + "）")
        return {}
    if HAVE_YAML and not os.environ.get("BLUEPRINT_NO_YAML"):
        try:
            data = yaml.safe_load(text)  # type: ignore[name-defined]
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            rep.error("yaml", label + ": YAML 解析失败（" + str(exc) + "）")
            return {}
    try:
        return _mini_yaml(text)
    except Exception as exc:
        rep.error("yaml", label + ": 内置解析器失败（" + str(exc) + "）")
        return {}


def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
        for name in filenames:
            yield (Path(dirpath) / name).relative_to(root).as_posix()


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [x for x in value if x is not None]
    return [value]


def as_globs(value) -> list[str]:
    out: list[str] = []
    for item in as_list(value):
        if isinstance(item, dict):
            out.extend(as_globs(item.get("include")))
        elif isinstance(item, str):
            out.append(item.strip().strip('"').strip("'"))
    return [g for g in out if g]


def glob_hits(pattern: str, files: list[str]) -> list[str]:
    pat = pattern.replace("\\", "/")
    while pat.startswith("./"):
        pat = pat[2:]
    hits = [f for f in files if fnmatch.fnmatchcase(f, pat)]
    if not hits and pat.endswith("/**"):
        prefix = pat[:-3]
        hits = [f for f in files if f == prefix or f.startswith(prefix + "/")]
    return hits


def check_structure(cfg: dict, root: Path, rep: Report) -> None:
    required = ["blueprint.yaml", "AGENTS.md"]
    docs = cfg.get("docs") or {}
    if isinstance(docs, dict) and docs.get("entry"):
        required.append(str(docs["entry"]))
    for name in required:
        if (root / name).exists():
            rep.ok("结构", name + " 存在")
        else:
            rep.error("结构", "缺少 " + name)

    modules = as_list(cfg.get("modules"))
    if not modules:
        rep.warn("结构", "blueprint.yaml 未声明 modules（S 档可接受，M/L 档应声明）")
    for item in modules:
        path = str(item)
        if not (root / path).is_dir():
            rep.error("结构", "modules 里的 " + path + " 不是目录")
            continue
        if cfg.get("tier") in ("M", "L") and not (root / path / "MODULE.yaml").exists():
            rep.error("结构", path + " 缺少 MODULE.yaml（M/L 档必须声明）")


def _package_scripts(root: Path) -> dict:
    path = root / "package.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("scripts") or {}
    except Exception:
        return {}


def _make_targets(root: Path) -> set:
    for name in ("Makefile", "makefile", "justfile", "Justfile"):
        path = root / name
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            return set(re.findall(r"^([A-Za-z0-9_.-]+)\s*:", text, re.M))
    return set()


def _missing(exe: str) -> str:
    """命令的可执行文件不在 PATH 里：多半是工具链没装，而不是配置写错。"""
    return "找不到可执行文件 " + exe + "（工具链未安装，或不在 PATH）"


def command_resolvable(cmd: str, root: Path):
    try:
        tokens = shlex.split(cmd, posix=False)
    except ValueError:
        return "命令无法解析"
    tokens = [t.strip('"').strip("'") for t in tokens if t.strip()]
    if not tokens:
        return "空命令"
    exe = tokens[0]
    pm = {"npm", "pnpm", "yarn", "bun"}
    if exe in pm:
        if len(tokens) >= 2 and tokens[1] == "run":
            script = tokens[2] if len(tokens) > 2 else ""
            if script and script in _package_scripts(root):
                return None
            return "package.json 里没有脚本 " + (script or "(空)")
        if len(tokens) >= 2 and tokens[1] in {"test", "start", "install", "i"}:
            return None if shutil.which(exe) else _missing(exe)
        return None if shutil.which(exe) else _missing(exe)
    if exe in {"make", "just"}:
        target = tokens[1] if len(tokens) > 1 and not tokens[1].startswith("-") else ""
        targets = _make_targets(root)
        if not targets:
            return "找不到 Makefile/justfile"
        if target and target not in targets:
            return "Makefile/justfile 里没有目标 " + target
        return None if shutil.which(exe) else _missing(exe)
    if exe in {"python", "python3", "py"}:
        found = shutil.which(exe) or shutil.which("python") or shutil.which("python3")
        return None if found else "找不到 python"
    return None if shutil.which(exe) else _missing(exe)


def check_entrypoints(cfg: dict, root: Path, rep: Report) -> None:
    points = cfg.get("entrypoints") or {}
    if not isinstance(points, dict) or not points:
        rep.warn("入口", "未声明 entrypoints（校验跳过）")
        return
    for name, cmd in points.items():
        text = str(cmd).strip()
        if not text or "TODO" in text.upper():
            rep.error("入口", name + " 未填写（当前为 " + repr(text) + "）")
            continue
        problem = command_resolvable(text, root)
        if problem:
            rep.error("入口", name + " = " + repr(text) + " -> " + problem)
        else:
            rep.ok("入口", name + " 可解析：" + text)


BT = chr(96)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
CODE_RE = re.compile(BT + r"([^" + BT + r"\n]+)" + BT)


def _looks_like_path(token: str) -> bool:
    t = token.strip()
    if not t or " " in t:
        return False
    low = t.lower()
    if low.startswith(("http://", "https://", "mailto:", "ftp:")):
        return False
    if any(ch in t for ch in "*?<>|$"):
        return False
    if t.startswith(("#", "-", "<!--", "{{", "~/")):
        return False
    if "/" not in t and not low.endswith(PATH_EXT):
        return False
    if "/" not in t and re.fullmatch(r"[A-Za-z0-9_.-]+", t):
        return False
    return True


def check_docs(root: Path, cfg: dict, rep: Report) -> None:
    docs = cfg.get("docs") or {}
    docs_root = str(docs.get("root", "docs")) if isinstance(docs, dict) else "docs"
    allow = []
    if isinstance(cfg.get("verify"), dict):
        allow = [str(x) for x in as_list(cfg["verify"].get("allow_missing"))]
    targets = [root / docs_root]
    for extra in ("AGENTS.md", "README.md"):
        if (root / extra).exists():
            targets.append(root / extra)
    files = []
    for target in targets:
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            files.extend(sorted(target.rglob("*.md")))
    if not files:
        rep.warn("文档", "没找到 Markdown 文档（跳过链接检查）")
        return
    missing = 0
    checked = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(root).as_posix()
        candidates = []
        for raw in LINK_RE.findall(text):
            target = raw.split("#")[0].strip()
            if target and not target.lower().startswith(("http", "mailto", "ftp")):
                candidates.append(target)
        for raw in CODE_RE.findall(text):
            if _looks_like_path(raw):
                candidates.append(raw.strip())
        for target in candidates:
            if any(a and a in target for a in allow):
                continue
            checked += 1
            if not ((root / target).exists() or (path.parent / target).exists()):
                missing += 1
                rep.error("文档", rel + " 引用的 " + target + " 不存在")
    if missing == 0:
        rep.ok("文档", str(checked) + " 个路径引用全部存在")


def check_modules(cfg: dict, root: Path, rep: Report) -> None:
    files = list(walk(root))
    seen: dict = {}
    total_globs = 0
    dead = 0
    for item in as_list(cfg.get("modules")):
        mod_dir = root / str(item)
        manifest = mod_dir / "MODULE.yaml"
        if not manifest.exists():
            continue
        data = load_yaml(manifest, rep, str(item) + "/MODULE.yaml")
        globs = as_globs(data.get("includes"))
        if not globs:
            rep.error("声明", str(item) + "/MODULE.yaml 没有 includes，模块边界未定义")
            continue
        allow_empty = bool(data.get("allow_empty"))
        for pattern in globs:
            total_globs += 1
            hits = glob_hits(pattern, files)
            if not hits and not allow_empty:
                dead += 1
                rep.error("声明", str(item) + "/MODULE.yaml 的 glob " + repr(pattern) + " 命中 0 个文件（死配置）")
                continue
            for hit in hits:
                if hit in seen and seen[hit] != str(item):
                    rep.error("声明", hit + " 同时被 " + seen[hit] + " 与 " + str(item) + " 声明（归属重叠）")
                seen[hit] = str(item)
    if total_globs and dead == 0:
        rep.ok("声明", str(total_globs) + " 条模块 glob 均有命中，且无重叠")


def check_owners(root: Path, rep: Report) -> None:
    manifest = root / "OWNERS.yaml"
    if not manifest.exists():
        rep.warn("归属", "没有 OWNERS.yaml（计算评审人时只能靠猜）")
        return
    data = load_yaml(manifest, rep, "OWNERS.yaml")
    groups = data.get("groups") or {}
    files = list(walk(root))
    patterns = []
    for entry in as_list(data.get("modules")):
        if isinstance(entry, dict):
            patterns.append(str(entry.get("path", "")))
        else:
            patterns.append(str(entry))
    bad = 0
    for pattern in patterns:
        if not pattern:
            bad += 1
            rep.error("归属", "OWNERS.yaml 有一条规则缺 path")
            continue
        if not glob_hits(pattern, files):
            bad += 1
            rep.error("归属", "OWNERS.yaml 的 glob " + repr(pattern) + " 命中 0 个文件（死配置）")
    for entry in as_list(data.get("modules")):
        if isinstance(entry, dict):
            owner = str(entry.get("owner", ""))
            if owner and isinstance(groups, dict) and owner not in groups:
                bad += 1
                rep.error("归属", "规则 " + repr(entry.get("path")) + " 的 owner " + repr(owner) + " 未在 groups 中定义")
    covered = set()
    for pattern in patterns:
        if pattern:
            covered.update(glob_hits(pattern, files))
    orphans = [f for f in files if f not in covered and (f.startswith("src/") or f.startswith("app/"))]
    if orphans:
        rep.warn("归属", str(len(orphans)) + " 个源文件没有归属 glob，例如 " + orphans[0])
    if bad == 0 and patterns:
        rep.ok("归属", str(len(patterns)) + " 条归属规则全部命中且 owner 均已定义")


def check_markers(root: Path, rep: Report) -> None:
    begin = re.compile(r"<!--\s*blueprint:begin\s+([^>]*?)\s*-->")
    end = re.compile(r"<!--\s*blueprint:end\s+([^>]*?)\s*-->")
    targets = ["AGENTS.md", "README.md"]
    docs = root / "docs"
    if docs.exists():
        targets += [p.relative_to(root).as_posix() for p in sorted(docs.rglob("*.md"))]
    bad = 0
    for name in targets:
        path = root / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        opens = begin.findall(text)
        closes = end.findall(text)
        for tag in opens:
            if tag not in closes:
                bad += 1
                rep.error("标记", name + " 的区块 " + repr(tag) + " 有 begin 却没有 end")
    if bad == 0:
        rep.ok("标记", "marker 区块成对出现")


BANNED_HOSTS = ("gitee.com", "gitlab.com", "bitbucket.org", "codeberg.org")


def _declared_git_hosts(cfg: dict) -> list[str]:
    """从 blueprint.yaml 读允许的托管主机；兼容旧的单主机写法。"""
    declared = cfg.get("git") or {}
    if not isinstance(declared, dict):
        return ["git.zxyuanyu.com"]
    entries = declared.get("hosts")
    if isinstance(entries, list):
        hosts = [str(e.get("host") or "").strip().lower() for e in entries if isinstance(e, dict)]
        hosts = [h for h in hosts if h]
        if hosts:
            return hosts
    host = str(declared.get("host") or "").strip().lower()
    return [host] if host else ["git.zxyuanyu.com"]


def check_git(cfg: dict, root: Path, rep: Report) -> None:
    """托管红线：远端只允许 blueprint.yaml 声明的主机。"""
    allowed = _declared_git_hosts(cfg)
    gitdir = root / ".git"
    if not gitdir.exists():
        rep.warn("托管", "没有 .git：先 git init 并把 origin 设成 https://" + allowed[0] + "/<owner>/<repo>.git")
        return
    conf = gitdir / "config"
    if not conf.is_file():
        rep.warn("托管", ".git/config 不存在，跳过远端检查")
        return
    text = conf.read_text(encoding="utf-8", errors="replace")
    urls = re.findall(r"^\s*url\s*=\s*(\S+)", text, re.M)
    if not urls:
        rep.warn("托管", "没有配置任何 remote（至少要有一个 remote）")
        return
    bad = 0
    for url in urls:
        low = url.lower()
        hit = [h for h in BANNED_HOSTS if h in low]
        if hit:
            bad += 1
            rep.error("托管", "远端指向外部托管 " + hit[0] + "：" + url + "（只允许 " + " / ".join(allowed) + "）")
        elif not any(h in low for h in allowed):
            bad += 1
            rep.error("托管", "远端主机不在声明列表（" + " / ".join(allowed) + "）：" + url)
    if bad == 0:
        rep.ok("托管", str(len(urls)) + " 个远端全部指向声明主机（" + " / ".join(allowed) + "）")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="校验 blueprint 契约：结构 / 入口 / 文档 / 声明")
    parser.add_argument("--root", default=".", help="项目根目录，默认当前目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--quiet", action="store_true", help="只打印问题")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    rep = Report()
    cfg_path = root / "blueprint.yaml"
    if not cfg_path.exists():
        print("[FAIL] 找不到 " + str(cfg_path) + "（先用 blueprint 生成骨架）")
        return 2

    cfg = load_yaml(cfg_path, rep, "blueprint.yaml")
    if not cfg:
        print("[FAIL] blueprint.yaml 内容为空或无法解析")
        return 2

    check_structure(cfg, root, rep)
    check_entrypoints(cfg, root, rep)
    check_docs(root, cfg, rep)
    check_modules(cfg, root, rep)
    check_owners(root, rep)
    check_markers(root, rep)
    check_git(cfg, root, rep)

    if args.json:
        print(json.dumps({
            "ok": not rep.errors,
            "errors": rep.errors,
            "warnings": rep.warnings,
            "passed": rep.passed,
        }, ensure_ascii=False, indent=2))
        return 0 if not rep.errors else 1

    if not args.quiet:
        for line in rep.passed:
            print("[ OK ] " + line)
    for line in rep.warnings:
        print("[WARN] " + line)
    for line in rep.errors:
        print("[FAIL] " + line)

    print("")
    if rep.errors:
        print("结论：" + str(len(rep.errors)) + " 个错误，" + str(len(rep.warnings)) + " 个警告。契约未通过，修掉错误再继续。")
        return 1
    print("结论：契约通过（" + str(len(rep.passed)) + " 项检查，" + str(len(rep.warnings)) + " 个警告）。")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
