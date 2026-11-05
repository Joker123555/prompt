# 发布流程

> 当前项目可能还没有发布流程。这一页写清"第一步做什么"，比留空更有用。

## 版本号

语义化版本：不兼容改动升主版本，新功能升次版本，修 bug 升补丁版本。

## 步骤

1. 确认 （未指定技术栈，请手工填写） 全绿；
2. 更新 CHANGELOG（写"用户能感知的变化"，不写"重构了内部函数"）；
3. 打 tag：`vX.Y.Z`；
4. 产物落 `dist/`（不进版本库）；
5. 发布后回填一行：发布日期 + 版本 + 一句变更摘要。

## 推送与托管

远端只有一个：公司 Gitea `https://git.zxyuanyu.com/lijin/prompt.git`（`git.zxyuanyu.com` / `lijin`）。**禁止推到 github.com / gitee.com 等外部托管。**

首次推送（服务器端还没有这个仓库时）：

1. 人类在 `https://git.zxyuanyu.com/repo/create` 建同名 **Private** 仓库（不要勾初始化 README，否则要处理分叉历史）；
2. 本地执行 `git push -u origin main`；
3. 推送前需人工批准（见 AGENTS.md 铁律 4）。

凭据怎么来（三选一）：

- **一次性令牌 URL**（适合 agent / 无人值守）：`git push https://<owner>:<令牌>@git.zxyuanyu.com/<owner>/<repo>.git main`，令牌只在这一次命令里，不落盘。
- **Windows 凭据管理器**（适合人）：先 `git config --global credential.helper wincred`，再 `git push -u origin main` 输一次用户名与令牌，之后不再问。
- **明文存储**（最后手段）：`git config --global credential.helper store` 会把令牌明文写进 `~/.git-credentials`，多人机器不要用。

Gitea 的 HTTPS 密码栏填的是**个人访问令牌**，不是你登录网页的密码。

## 回滚

上一版必须能重新部署出来。做不到时，先把"怎么退回上一版"写清楚再发。
