# 多平台发布差异清单 · Multi-platform publishing checklist（skill-inventory）

> **Language / 语言**：本文档为维护者内部发布备忘，中英双语概要 + 中文细则。
> This maintainer checklist is bilingual: an English TL;DR below, details in Chinese.
> 报告与文档的用户可自选语言（`--lang en|zh` 或环境变量 `SKILL_INV_LANG`）/ end users choose
> their report language via `--lang en|zh` or the `SKILL_INV_LANG` env var.

> 本技能同时发布到 SkillHub 与 ClawHub，两平台规则相反，清理清单互不通用。
> 每次发布前对照本清单执行，别凭记忆。

## English TL;DR

- Two publishing targets with **opposite rules**: SkillHub (slug `skill-inventory`, requires a
  clean `git archive` copy with `.gitignore` / `LICENSE` / `.clawhubignore` / `references/.gitkeep`
  removed) vs ClawHub (slug `agent-skill-inventory`, packages the workspace directly, honors
  `.clawhubignore` which excludes `LICENSE` and `config.yaml`).
- Keep `version` in SKILL.md frontmatter in sync with the `--version` flag of both CLIs.
- **Pin the clawhub CLI version** (`npx clawhub@0.23.3`), never `@latest` — unpinned remote code
  in a publishing workflow is a supply-chain risk (and is flagged by SkillSpector Rp1).

## 平台对照

| 项 | SkillHub（skillhub.cn） | ClawHub（clawhub.ai） |
|---|---|---|
| slug | `skill-inventory`（命名空间隔离 `@user_c5278a31/…`） | `agent-skill-inventory`（**全局唯一**，原名已被占） |
| 打包方式 | `git archive HEAD` 导出干净副本（自动排除 ignored） | 直接对工作区打包（CLI 自动跳点号路径段 + 读 `.gitignore`/`.clawhubignore`） |
| 发布前必删 | `.gitignore`、`LICENSE`、`.clawhubignore`、`references/.gitkeep`（封禁清单动态，报错写哪个删哪个） | 无需手删（`LICENSE` 走 `.clawhubignore`；点号文件自动排除） |
| 审核机制 | 三线并行（内容合规关键词 + 漏洞扫描 + AI 语义） | 安全扫描三层（静态 + VirusTotal + LLM），不挑关键词 |
| 许可证 | 无强制 | **强制 MIT-0**，仓库 MIT LICENSE 与之冲突故排除 |
| 版本号 | SKILL.md frontmatter `version` | `--version` 显式传，与 frontmatter 保持一致 |

## 发布命令备忘

```bash
# SkillHub（干净副本流程）
git archive HEAD | tar -x -C "$PUB_TMP" && cd "$PUB_TMP"
rm -f .gitignore LICENSE .clawhubignore references/.gitkeep
skillhub publish "$PUB_TMP" --version X.Y.Z --changelog "..." --json
# 成功标志：ok=true + reviewStatus/contentAuditStatus/securityScanStatus 均 pending

# ClawHub（工作区直发）
# ⚠️ 钉版本，不用 @latest（未钉版=发布链路里执行未审远程代码，SkillSpector Rp1 会抓）。
#    升级前先 `npm view clawhub version` 核对目标版本再手动改。
npx clawhub@0.23.3 skill publish . \
  --slug agent-skill-inventory --name "技能盘点与效能体检" --version X.Y.Z \
  --topics "..." --source-repo Elisabeth15501/skill-inventory \
  --source-commit "$(git rev-parse HEAD)" --changelog "..."
# 成功后 npx clawhub@0.23.3 inspect agent-skill-inventory 看 Moderate 是否 CLEAN
```

## 注意事项

- **改版本号时两平台共用同一份 SKILL.md frontmatter**，一次改动两边生效，`--version` 显式传保持一致。
- **为 ClawHub 做的调整不要顺手动 SkillHub 产物**，反之亦然（`.clawhubignore` 只对 ClawHub 有意义，SkillHub 副本里必须删）。
- SkillHub v1.0.0 发布响应曾返回 `source: "clawhub"`（个人发布预期为 `community`）——待审核通过后核对实际命名空间，若异常需联系平台（skillhub@tencent.com / GitHub issues）。
- ClawHub 的 `--categories` 首次发布不传（未知 slug 会失败），发布后到网页端设置页改分类。
