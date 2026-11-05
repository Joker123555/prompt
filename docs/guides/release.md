# 发布流程

> 当前项目可能还没有发布流程。这一页写清"第一步做什么"，比留空更有用。

## 版本号

语义化版本：不兼容改动升主版本，新功能升次版本，修 bug 升补丁版本。

## 步骤

1. 确认 `python -m unittest discover -s tests -t . -v` 与 `python tools/check_layers.py` 全绿；
2. 更新 `CHANGELOG`（写"用户能感知的变化"，不写"重构了内部函数"）；没有就新建；
3. 把 `qdoctor/__init__.py` 的 `__version__` 改成新版本；
4. 打 tag：`vX.Y.Z`；
5. 本项目无构建产物；如需分发，打源码包落 `dist/`（不进版本库）；
6. 发布后回填一行：发布日期 + 版本 + 一句变更摘要。

## 推送与托管

两个远端，GitHub 为主，公司 Gitea 为镜像：

| 远程名 | 地址 | 用途 |
|---|---|---|
| `github` | `https://github.com/Joker123555/prompt.git` | 主仓库，已设为 `remote.pushDefault` |
| `origin` | `https://git.zxyuanyu.com/lijin/prompt.git` | 公司侧留档 |

除这两处外，禁止推送到 gitee.com、gitlab.com 等其他外部托管。

每次发布：

1. 跑测试与依赖检查，全绿；
2. `git push github main`（`git push` 默认即推这里）；
3. 需要公司侧同步时再 `git push origin main`。

首次推送（远端还没有这个仓库时）：

1. 人类在 `https://github.com/Joker123555/prompt` 建同名仓库（不要勾初始化 README，否则要处理分叉历史）；
2. 本地执行 `git push -u github main`；
3. 推送前需人工批准（见 AGENTS.md 铁律 4）。

凭据怎么来：

- **GitHub**：`gh auth login` 后由 `gh auth git-credential` 提供，本仓库已配置 `credential.<url>.helper`，令牌不落盘；直连超时，本仓库已用 `http.<url>.proxy` 指向 `http://127.0.0.1:7890`。
- **Gitea 一次性令牌 URL**（适合 agent / 无人值守）：`git push https://<owner>:<令牌>@git.zxyuanyu.com/<owner>/<repo>.git main`，令牌只在这一次命令里，不落盘。
- **Windows 凭据管理器**（适合人）：先 `git config --global credential.helper wincred`，再 `git push -u origin main` 输一次用户名与令牌，之后不再问。
- **明文存储**（最后手段）：`git config --global credential.helper store` 会把令牌明文写进 `~/.git-credentials`，多人机器不要用。

Gitea 的 HTTPS 密码栏填的是**个人访问令牌**，不是你登录网页的密码。

## 回滚

上一版必须能重新部署出来。做不到时，先把"怎么退回上一版"写清楚再发。
