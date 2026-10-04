---
name: skill-inventory
slug: skill-inventory
displayName: 技能盘点与效能体检 · Skill Inventory & Health Check
summary: Scan any skills directory and classify skills into used / protected / closeable / manual-review buckets with anti-accidental-close guardrails. 扫描技能目录，按「在用/受保护/可关闭/需人工确认」四档输出瘦身建议，防误关护栏齐全。
description: >-
  Office-agent skill inventory & health check. Scans any skills directory, measures size and
  context-token footprint, detects duplicates, and classifies skills into used / protected /
  closeable / manual-review buckets. Reverse-dependency scanning locks every skill referenced by
  automations, hooks or plugins. Read-only by default: two disclosed, consent-gated write targets —
  `--overrides --apply --yes` (programmatic close on platforms like WorkBuddy; dry-run without
  --yes) and `--set-lang` (saves the report language preference to
  ~/.workbuddy/skill-inventory.json) — plus one disclosed backup artifact: a timestamped
  ~/.workbuddy/settings.json.bak.<ts> safety copy created before the close write, path printed to
  the user. Report language: auto (default; the Agent decides per
  conversation language) / zh / en; one-off override via --lang; JSON output is always
  English-keyed. No network access, no subprocesses. English docs: SKILL.en.md.
  办公型 Agent 通用的技能库盘点与效能体检。扫描任意技能目录，统计数量/体积/上下文 token 占用，
  识别重复与近似技能，并按「有使用记录/受保护/可关闭候选/需人工确认」四档给出保守建议；反向依赖
  扫描会锁定被自动化/Hook/插件引用的技能。默认只读，两处写路径目标均需显式授权：`--overrides
  --apply --yes`（仅 WorkBuddy 等可关平台，缺 --yes 只做预览）与 `--set-lang`（把报告
  语言偏好写入 ~/.workbuddy/skill-inventory.json）；另有一份已披露的备份工件——关闭写入前在
  settings.json 旁生成带时间戳的 settings.json.bak.<ts> 安全副本，路径会打印给用户。语言设置三选一：
  auto（默认，Agent 按对话语言
  决定）/ zh / en；--lang 仅本次运行覆盖；--json 输出恒为英文键。无网络、无子进程。
  英文文档见 SKILL.en.md。
tags: [skill-management, efficiency, token-optimization, inventory, devops]
author: Elisabeth15501
version: 1.3.3
allowed-tools: Bash(python scripts/skill_inventory.py:*), Read, Glob, Grep, Write(~/.workbuddy/settings.json), Edit(~/.workbuddy/settings.json), Write(~/.workbuddy/skill-inventory.json), Edit(~/.workbuddy/skill-inventory.json)
metadata:
  openclaw:
    requires:
      bins: [python3, python]
    permissions:
      network: none
      subprocess: none
      persistence: none
      filesystem:
        read: "skills directories, usage logs, automation/hook/routing/plugin configs"
        write: >-
          DECLARED STATE-CHANGING CAPABILITIES, all consent-gated and disclosed:
          (1) writes ONLY the "skillOverrides" key of ~/.workbuddy/settings.json via
          --overrides --apply --yes, reversible via the host /skills menu.
          This can persistently disable the listed skills and alter agent behavior — that is
          its disclosed purpose; it never runs without explicit user confirmation.
          (2) writes ONLY the report language preference file ~/.workbuddy/skill-inventory.json
          ({"language": "auto|zh|en"}) via the explicit --set-lang flag — a user-controlled
          display preference: not loaded automatically at startup, nothing scheduled or
          registered from it, reversible via --set-lang auto or by deleting the file;
          not a persistence mechanism.
          (3) creates ONE disclosed backup artifact during --apply --yes: a timestamped copy
          ~/.workbuddy/settings.json.bak.<YYYYMMDD-HHMMSS> written beside settings.json before
          it is modified (inert safety copy; its path is printed to the user; never read back).
---

# skill-inventory · 办公型 Agent 通用的技能库盘点与效能体检

> **English docs**：`SKILL.en.md`（本文件中文版）· `README.en.md`。报告与文档语言均可由用户选择，见下方「语言设置」。
> 维护者文档（发布清单 / 触发词归档）保留在 GitHub 仓库的 `references/`，不随平台分发包分发。

办公型 Agent（WorkBuddy、千问办公、百度搭子、天禧AI 等）装得多不等于能力强。
技能清单（name + description）每一轮对话都进模型上下文——装 54 个技能约等于每轮白烧 5,000+ tokens。

## 1. 适用场景

**触发短语示例**（匹配 `description` 自动挂载或显式调用）：

- 「盘点我装了哪些技能」
- 「哪些技能可以关闭/合并」「技能占了多少上下文」
- 「关闭 XX 前先看影响」
- 「把报告语言换成英文/中文」「语言设置改成 auto」

**不触发**：写周报、发邮件、代码生成等与技能库治理无关的任务——本技能只做技能库的
盘点、体检与关闭前评估。

## 2. 语言设置（auto / zh / en）

| 选项 | 说明 |
|------|------|
| `auto`（默认） | 自动——Agent 按用户当前对话语言传 `--lang` 决定；未传参时依次回落：环境变量 `SKILL_INV_LANG` → 系统区域语言 → 中文 |
| `zh` | 报告语言固定为中文（随时可用 `--set-lang` / `--lang` 改回） |
| `en` | 报告语言固定为英文（随时可用 `--set-lang` / `--lang` 改回） |

- **查看**：`--show-lang` 打印当前设置、三个选项及说明、切换方式。
- **保存**：`--set-lang auto|zh|en` 写入偏好文件 `~/.workbuddy/skill-inventory.json`（仅此一处，
  仅在你显式运行该命令时写入），切换后立即对后续运行生效；`--set-lang auto` 或删除该文件即恢复默认。
- **单次覆盖**：`--lang zh|en` 只影响本次运行，不改动已保存设置。
- **优先级**：`--lang`（本次）＞ 已保存设置（zh/en）＞ auto 回落链。
- **auto 不是锁定**：它是「用户尚未表达偏好时的回落」，不是强制——随时可用 `--set-lang` 固定为
  zh/en，或用 `--lang` 单次覆盖；不选语言的用户看到中文报告纯属默认，不是被强制。
- **恒定不变**：四档分类标识恒为英文（used / protected / closeable / manual-review），
  `--json` 输出恒为英文键——程序化消费不受语言设置影响。

## 3. 输入材料

| 输入 | 必需 | 说明 |
|------|------|------|
| 技能目录 | ✅（已知平台可自动探测） | 每个子目录 = 一个技能（含 `SKILL.md` 即可）；其他平台用 `--root <目录>` |
| 用量日志 | 可选 | `--usage-log <路径>`；WorkBuddy 自动探测 `usage-log.json` |
| 反向依赖根 | 可选 | `--refs <路径>`：自动化 / Hook / 路由配置等可能隐式引用技能的文件或目录 |
| 受保护清单 | 可选 | `--protect a,b,c` 或 `--protect-file`；另内置安全/审计类启发式 |

**权限边界**（与脚本头部的机器可读声明一致）：

- **读取**：技能目录、用量日志、自动化/Hook/路由/插件配置
- **写入**（两处目标 + 一份备份工件，均需显式授权）：
  1. `~/.workbuddy/settings.json` 的 `skillOverrides` 键——仅当你显式传 `--apply --yes`（写前自动备份）；
  2. `~/.workbuddy/skill-inventory.json` 的语言偏好——仅当你显式传 `--set-lang`；
  3. 备份工件——执行 `--apply --yes` 时，在 `settings.json` 旁生成 `settings.json.bak.<时间戳>` 安全副本（惰性副本、路径打印给你、不会被回读）。
- **网络**：无　**子进程**：无

纯本地静态分析，零网络依赖、零子进程（沙箱红线天然合规）。

## 4. 输出结果

1. **盘点报告**（默认）：技能总数 / 市场与自建占比 / 清单 token 占用估算 / 逐技能表格，四档分类：
   - **used 有使用记录**：确实用过（可信）。
   - **closeable 可关闭候选**：无使用记录 且 超过 30 天没改过。**仍须人工逐条确认**。
   - **manual-review 需人工确认**：无使用记录但近期改过，或本平台无遥测——别急着关。
   - **protected 受保护**：不会自动建议关闭（本工具自身 / `protected: true` / 安全审计类 / 被引用锁定 / 用户追加）。
2. **影响预览**：每个被引用锁定的技能，列出「关闭将断掉 N 处引用」——`[来源类型] 完整路径` + 命中的技能名；单技能深查 `--impact <名称>`。
3. **重复/跨区提示**：真·多份激活、激活+禁用副本、同名技能。
4. **机器可读 JSON**（`--json`）：四档清单、结构化 `referenced_by`、`telemetry_scope`（`t1-only`/`none`），英文键。

## 5. 执行步骤

| 命令 | 说明 |
|---|---|
| `python scripts/skill_inventory.py` | auto 探测平台，完整报告 |
| `python scripts/skill_inventory.py --agent workbuddy` | WorkBuddy（有用量账本；可起草关闭） |
| `python scripts/skill_inventory.py --agent qwen` | 千问办公（调用记录；关闭走连接器/UI） |
| `python scripts/skill_inventory.py --agent baidu` | 百度搭子（多根探测；无遥测 → 全库需人工确认） |
| `python scripts/skill_inventory.py --agent generic --root <dir>` | 通用档：任意平台/自定义目录 |
| `python scripts/skill_inventory.py --impact <名称>` | 单技能影响深查（关闭前审阅） |
| `python scripts/skill_inventory.py --json` | 机器可读 JSON |
| `python scripts/skill_inventory.py --show-lang` | 查看语言设置与选项说明 |
| `python scripts/skill_inventory.py --set-lang auto\|zh\|en` | 保存语言设置（立即生效） |
| `python scripts/skill_inventory.py --lang zh\|en` | 本次运行的语言覆盖 |

流程：`auto 探测平台 → 失败回落 generic 通用档`。通用档**必须** `--root` 指技能目录；
无用量日志自动降级为「不判任何技能可关闭」；`--refs` 可补充反向依赖扫描根。

## 6. 数据源优先级

1. **平台用量日志**（最高置信）：只覆盖「显式调用」（T1）；自动挂载 / 定时任务 / Hook / 专家内部调用（T2–T6）在日志里不可见——报告会常显这一口径。
2. **反向依赖扫描**（兜底盲区）：扫描自动化 / Hook / 路由状态 / 插件清单等配置里的技能引用，凡被引用即锁定为受保护。
3. **最后修改时间**（最低置信）：仅当无遥测时作参考，**不可单独作为关闭依据**。
4. **用户确认**（最终裁决）：任何「可关闭候选」动刀前必须经用户逐条确认。

## 7. 用户确认点

- **本工具不会自行关闭任何技能。** 关闭写路径需你显式授权——在 WorkBuddy 等可关平台上传入
  `--overrides --apply --yes`：此时先自动备份 `settings.json`，再把候选合并进 `skillOverrides`；
  缺 `--yes` 只做 dry-run 预览；不可关平台直接拒绝 `--apply`。
- **优先引导宿主自带开关**：如 WorkBuddy 的 `/skills` 菜单（按 Esc 才落盘）、千问/百度的客户端启用开关；通用档没有关闭通道，只给候选清单。
- **可关闭候选**：确认前先看「影响预览」（`--impact <名称>`），确认无关键词触发器 / 专家组件 / 自动化依赖。

## 8. 风险边界

- **默认只读，写路径两处目标 + 一份备份工件、均受控**：本工具默认不写任何宿主配置、不调用任何禁用/删除接口。
  它具备两项受控写能力，均需显式授权并在输出中标注：`--overrides --apply --yes`（缺
  `--yes` 即 dry-run、不可关平台拒绝）与 `--set-lang`（只写语言偏好文件）；此外 `--apply --yes`
  落笔前必先生成 settings.json 备份副本（路径打印在输出里，可自行删除）。
- **无持久化机制**：不注册定时任务 / cron、不写启动项、不留守护进程、不自我修改。
  跨会话效果仅两处，均为用户显式授权的公开功能、随时可逆——`skillOverrides` 的 off 项
  （可在宿主 `/skills` 菜单恢复）与语言偏好文件。语言偏好文件只是显示偏好（单个 JSON 键）：
  不基于它注册或排程任何东西，仅在下一次运行时被读取用来挑报告语言；`--set-lang auto`
  或删除该文件即恢复默认——它不属于驻留机制。
- **未显式调用 ≠ 没用**：关键词触发器、专家/连接器组件的间接调用在用量日志里完全无痕——这是结构性盲区，靠反向依赖扫描 + 用户确认双层兜底。
- **遥测缺口不判死**：无用量日志或日志读取失败时，全库落「需人工确认」，不输出可关闭项——宁可少报，不可误杀。
- **受保护技能永不进候选**：本工具自身、`protected: true`、安全/审计类、被引用锁定、用户 `--protect` 追加。
- **重复检测是近似比对**（名称/描述/体积），不是语义级去重；结论仅基于可发现的配置根，T2 自动挂载与描述性关键词引用扫不到。

---

## 附：平台档位一览

| 平台 | 探测 | 用量账本 | 程序化关闭 | 本工具行为 |
|------|---------|---------|-----------|-----------|
| WorkBuddy | `~/.workbuddy/skills` 自动 | ✅ `usage-log.json` | ✅ `skillOverrides`（需 `--apply --yes`，先备份） | 盘点 + 可关闭草稿 |
| 千问办公 QwenWork | `~/.qwenworkcn/skills` 自动 | ✅ `skill-usage.json` | 经连接器/UI（不代执行） | 盘点 + 调用记录 + 客户端确认清单 |
| 百度搭子 Baidu DuMate | 多根自动探测 | ❌ | 经 UI/连接器（不代执行） | 盘点 + 关闭指引；无遥测全库需人工确认 |
| 通用档 Generic（含天禧等沙箱） | `--root` 指定 | 默认无 | ❌ 无关闭通道 | 盘点 + 建议；全库需人工确认 |

> 原则：**能力感知**——平台能不能「程序化关闭」决定工具产出什么。不可关平台不产出关闭动作，
> 只做体检与候选清单，把「动刀」留给宿主与用户。
