---
name: skill-inventory
slug: skill-inventory
displayName: 技能盘点与效能体检 · Skill Inventory & Health Check
summary: Scan any skills directory and classify skills into used / protected / closeable / manual-review buckets with anti-accidental-close guardrails. 扫描技能目录，按「在用/受保护/可关闭/需人工确认」四档输出瘦身建议，防误关护栏齐全。
description: >-
  Office-agent skill inventory & health check. Scans any skills directory, measures size and
  context-token footprint, detects duplicates, and classifies skills into used / protected /
  closeable / manual-review buckets. Reverse-dependency scanning locks every skill referenced by
  automations, hooks or plugins. Read-only by default: its single, consent-gated write path is
  `--overrides --apply --yes` on platforms with a programmatic close channel (e.g. WorkBuddy),
  which automatically backs up settings.json first and merges "off" entries into skillOverrides
  after your explicit confirmation; without --yes it is a dry-run preview. No network access,
  no subprocesses. Reports default to Chinese (`--lang en` for English); JSON output is always
  English-keyed.
  办公型 Agent 通用的技能库盘点与效能体检。扫描任意技能目录，统计数量/体积/上下文 token 占用，
  识别重复与近似技能，并按「有使用记录/受保护/可关闭候选/需人工确认」四档给出保守建议；反向依赖
  扫描会锁定被自动化/Hook/插件引用的技能。默认只读：写路径仅限 `--overrides --apply --yes`
  （仅 WorkBuddy 等可关平台），先自动备份 settings.json 再合并 off 项，缺 --yes 只做预览；
  无网络、无子进程。报告默认中文（--lang en 切英文）；--json 输出恒为英文键。
tags: [skill-management, efficiency, token-optimization, inventory, devops]
author: Elisabeth15501
version: 1.1.0
allowed-tools: Bash(python scripts/skill_inventory.py:*), Read, Glob, Grep
metadata:
  openclaw:
    requires:
      bins: [python3, python]
    permissions:
      network: none
      subprocess: none
      filesystem:
        read: "skills directories, usage logs, automation/hook/routing/plugin configs"
        write: "~/.workbuddy/settings.json skillOverrides only (requires --apply --yes, auto-backup first)"
---

# skill-inventory · 办公型 Agent 通用的技能库盘点与效能体检

> **Language / 语言**：本文档中英双语。报告输出默认简体中文，`--lang en` 切换英文；
> 四档分类恒用英文标识（used / protected / closeable / manual-review），`--json` 输出恒为英文键，
> 程序化消费不受语言影响。
> This document is bilingual. Reports default to Simplified Chinese; pass `--lang en` for English.
> Bucket names are always English identifiers (used / protected / closeable / manual-review), and
> `--json` output is always English-keyed, so programmatic consumption is language-independent.

## 1. 适用场景 / When to use

办公型 Agent（WorkBuddy、千问办公、百度搭子、天禧AI 等）装得多不等于能力强。
技能清单（name + description）每一轮对话都进模型上下文——装 54 个技能约等于每轮白烧 5,000+ tokens。

**触发短语示例 / Trigger phrase examples**（匹配 `description` 自动挂载或显式调用）：

- 「盘点我装了哪些技能」/ "inventory my installed skills"
- 「哪些技能可以关闭/合并」「技能占了多少上下文」/ "which skills can I close", "how much context do my skills cost"
- 「关闭 XX 前先看影响」/ "show the impact of closing <skill> before I do it"

**不触发 / Not for**：写周报、发邮件、代码生成等与技能库治理无关的任务——本技能只做技能库的
盘点、体检与关闭前评估。/ This skill only inventories and assesses skill libraries; it does not
handle unrelated tasks.

## 2. 输入材料 / Inputs

| 输入 Input | 必需 Required | 说明 Notes |
|------|------|------|
| 技能目录 Skills dir | ✅（已知平台可自动探测 / auto-detected for known platforms） | 每个子目录 = 一个技能（含 `SKILL.md` 即可）；其他平台用 `--root <目录>` / each subdirectory with a `SKILL.md` counts as one skill |
| 用量日志 Usage log | 可选 Optional | `--usage-log <路径>`；WorkBuddy 自动探测 `usage-log.json` |
| 反向依赖根 Ref roots | 可选 Optional | `--refs <路径>`：自动化 / Hook / 路由配置等可能隐式引用技能的文件或目录 |
| 受保护清单 Protect list | 可选 Optional | `--protect a,b,c` 或 `--protect-file`；另内置安全/审计类启发式 |

**权限边界 / Permission scope**（权限声明 / permission declaration）：

- **读取 Read**：技能目录、用量日志、自动化/Hook/路由/插件配置 / skills directories, usage logs,
  automation/hook/routing/plugin configs
- **写入 Write**：仅 `~/.workbuddy/settings.json` 的 `skillOverrides` 键，且仅当你显式传
  `--apply --yes`（写前自动备份）/ only the `skillOverrides` key of settings.json, only via your
  explicit `--apply --yes` (auto-backup first)
- **网络 Network**：无 / none　**子进程 Subprocess**：无 / none

纯本地静态分析，零网络依赖、零子进程（沙箱红线天然合规）。
Pure local static analysis — no network, no subprocesses (sandbox red-line compliant).

## 3. 输出结果 / Outputs

1. **盘点报告 Inventory report**（默认）：技能总数 / 市场与自建占比 / 清单 token 占用估算 / 逐技能表格，四档分类：
   - **used 有使用记录**：确实用过（可信）。
   - **closeable 可关闭候选**：无使用记录 且 超过 30 天没改过。**仍须人工逐条确认**。
   - **manual-review 需人工确认**：无使用记录但近期改过，或本平台无遥测——别急着关。
   - **protected 受保护**：不会自动建议关闭（本工具自身 / `protected: true` / 安全审计类 / 被引用锁定 / 用户追加）。
2. **影响预览 Impact preview**：每个被引用锁定的技能，列出「关闭将断掉 N 处引用」——`[来源类型] 完整路径` + 命中的技能名；单技能深查 `--impact <名称>`。
3. **重复/跨区提示 Duplicate hints**：真·多份激活、激活+禁用副本、同名技能。
4. **机器可读 JSON**（`--json`）：四档清单、结构化 `referenced_by`、`telemetry_scope`（`t1-only`/`none`），英文键。

## 4. 执行步骤 / How to run

| 命令 Command | 说明 Purpose |
|---|---|
| `python scripts/skill_inventory.py` | auto 探测平台，完整报告 / auto-detect platform, full report |
| `python scripts/skill_inventory.py --agent workbuddy` | WorkBuddy（有用量账本；可起草关闭） |
| `python scripts/skill_inventory.py --agent qwen` | 千问办公（调用记录；关闭走连接器/UI） |
| `python scripts/skill_inventory.py --agent baidu` | 百度搭子（多根探测；无遥测 → 全库需人工确认） |
| `python scripts/skill_inventory.py --agent generic --root <dir>` | 通用档：任意平台/自定义目录 |
| `python scripts/skill_inventory.py --impact <name>` | 单技能影响深查（关闭前审阅） |
| `python scripts/skill_inventory.py --json` | 机器可读 JSON |
| `python scripts/skill_inventory.py --lang en` | English report |

流程：`auto 探测平台 → 失败回落 generic 通用档`。通用档**必须** `--root` 指技能目录；
无用量日志自动降级为「不判任何技能可关闭」；`--refs` 可补充反向依赖扫描根。

## 5. 数据源优先级 / Data-source precedence

1. **平台用量日志 Usage log**（最高置信 highest confidence）：只覆盖「显式调用」（T1）；自动挂载 / 定时任务 / Hook / 专家内部调用（T2–T6）在日志里不可见——报告会常显这一口径。
2. **反向依赖扫描 Reverse-dependency scan**（兜底盲区）：扫描自动化 / Hook / 路由状态 / 插件清单等配置里的技能引用，凡被引用即锁定为受保护。
3. **最后修改时间 Last-modified time**（最低置信 lowest）：仅当无遥测时作参考，**不可单独作为关闭依据**。
4. **用户确认 User confirmation**（最终裁决 final say）：任何「可关闭候选」动刀前必须经用户逐条确认。

## 6. 用户确认点 / User confirmation points

- **本工具不会自行关闭任何技能。** 写路径仅限一处，且需你显式授权——在 WorkBuddy 等可关平台上传入
  `--overrides --apply --yes`：此时先自动备份 `settings.json`，再把候选合并进 `skillOverrides`；
  缺 `--yes` 只做 dry-run 预览；不可关平台直接拒绝 `--apply`。
  This tool never closes a skill on its own. The only write path is your explicit
  `--overrides --apply --yes` on can_close platforms (backup first, dry-run without --yes).
- **优先引导宿主自带开关**：如 WorkBuddy 的 `/skills` 菜单（按 Esc 才落盘）、千问/百度的客户端启用开关；通用档没有关闭通道，只给候选清单。
- **可关闭候选**：确认前先看「影响预览」（`--impact <名称>`），确认无关键词触发器 / 专家组件 / 自动化依赖。

## 7. 风险边界 / Risk boundaries

- **默认只读，写路径单一且受控 / Read-only by default, single consent-gated write path**：本工具默认不写任何
  宿主配置、不调用任何禁用/删除接口；它**具备**一项受控写能力——`--overrides --apply --yes`
  （先备份、缺 `--yes` 即 dry-run、不可关平台拒绝），此能力在报告与 `--overrides` 输出中都会显式标注。
  Read-only by default: no config writes, no disable/delete calls. It does have a single
  consent-gated write capability — `--overrides --apply --yes` (auto-backup, dry-run without --yes,
  rejected on non-closable platforms) — which every report and --overrides output states explicitly.
- **未显式调用 ≠ 没用**：关键词触发器、专家/连接器组件的间接调用在用量日志里完全无痕——这是结构性盲区，靠反向依赖扫描 + 用户确认双层兜底。
- **遥测缺口不判死**：无用量日志或日志读取失败时，全库落「需人工确认」，不输出可关闭项——宁可少报，不可误杀。
- **受保护技能永不进候选**：本工具自身、`protected: true`、安全/审计类、被引用锁定、用户 `--protect` 追加。
- **重复检测是近似比对**（名称/描述/体积），不是语义级去重；结论仅基于可发现的配置根，T2 自动挂载与描述性关键词引用扫不到。

---

## 附：平台档位一览 / Platform matrix

| 平台 Platform | 探测 Detection | 用量账本 Usage ledger | 程序化关闭 Programmatic close | 本工具行为 Behaviour |
|------|---------|---------|-----------|-----------|
| WorkBuddy | `~/.workbuddy/skills` 自动 | ✅ `usage-log.json` | ✅ `skillOverrides`（需 `--apply --yes`，先备份） | 盘点 + 可关闭草稿 |
| 千问办公 QwenWork | `~/.qwenworkcn/skills` 自动 | ✅ `skill-usage.json` | 经连接器/UI（不代执行） | 盘点 + 调用记录 + 客户端确认清单 |
| 百度搭子 Baidu DuMate | 多根自动探测 | ❌ | 经 UI/连接器（不代执行） | 盘点 + 关闭指引；无遥测全库需人工确认 |
| 通用档 Generic（含天禧等沙箱） | `--root` 指定 | 默认无 | ❌ 无关闭通道 | 盘点 + 建议；全库需人工确认 |

> 原则：**能力感知**——平台能不能「程序化关闭」决定工具产出什么。不可关平台不产出关闭动作，
> 只做体检与候选清单，把「动刀」留给宿主与用户。
> Principle: capability-aware — what the tool emits depends on whether the platform can close
> programmatically. Non-closable platforms get inventory + candidate lists only.

---

# English version (full)

## 1. When to use

Office agents (WorkBuddy, QwenWork, Baidu DuMate, Tianxi AI, …) accumulate skills whose
name+description entries ride along in every conversation turn — 54 installed skills ≈ 5,000+
tokens burned per turn. Use this skill when the user asks "what skills do I have", "which can be
closed or merged", "how much context do they cost", or wants a pre-close impact review.
Trigger examples: "inventory my installed skills" · "which skills can I close" · "show the impact
of closing <skill>". Not for unrelated tasks (report writing, mail, code generation).

## 2. Inputs

- **Skills directory** (required; auto-detected for known platforms, `--root <dir>` otherwise):
  each subdirectory containing a `SKILL.md` counts as one skill.
- **Usage log** (optional, `--usage-log`): WorkBuddy's `usage-log.json` is auto-detected.
- **Reverse-dependency roots** (optional, `--refs`): automation/hook/routing configs that may
  reference skills implicitly.
- **Protect list** (optional, `--protect a,b,c` / `--protect-file`); a safety/audit keyword
  heuristic is built in.

Pure local static analysis: no network, no subprocesses.

## 3. Outputs

1. **Inventory report** (default): totals, market vs self-built ratio, token-footprint estimate,
   per-skill table, four buckets — **used / closeable / manual-review / protected**.
2. **Impact preview**: for every reference-locked skill, which references break if closed
   (`[kind] full path` + hit terms); single-skill deep dive via `--impact <name>`.
3. **Duplicate hints**: multiple active copies, active+disabled copies, same-name skills.
4. **Machine-readable JSON** (`--json`): buckets, structured `referenced_by`, `telemetry_scope`.

## 4. Behaviour contract (read this before trusting the tool)

- **Read-only by default.** Inventory, classification and advice write nothing anywhere.
- **Exactly one write path**: `--overrides --apply --yes` on platforms with a programmatic close
  channel (WorkBuddy family). It automatically backs up `settings.json`, then merges "off" entries
  into `skillOverrides`. Without `--yes` it is a dry-run preview; non-closable platforms reject
  `--apply` outright. Every report and draft states this explicitly — the tool never closes a
  skill silently or on its own initiative.
- **Permission scope**: reads skill directories, usage logs and automation/hook/routing/plugin
  configs; writes only `~/.workbuddy/settings.json` (`skillOverrides` key, via the path above);
  no network; no subprocesses.
- **Telemetry gap ⇒ nothing is judged closeable**: without a usable usage log everything lands in
  manual-review. Under-reporting beats false kills.
- **Protected skills never enter the closeable bucket**: this tool itself, `protected: true`
  frontmatter, safety/audit keyword hits, reference-locked, user-added.

## 5. Why "no usage record" is not "unused"

Usage logs only record explicit invocations (T1). Auto-mounting by description match, keyword
triggers, scheduled tasks, hooks and expert/connector-internal calls (T2–T6) are invisible. The
reverse-dependency scan catches what is discoverable in config roots; the rest is covered by the
manual-review bucket and your confirmation — the tool's job is to provide facts, the decision
stays human.

## 6. Platform matrix

See the bilingual table above — behaviour per platform is capability-aware: closable platforms get
close drafts (still gated by `--apply --yes`), non-closable platforms get inventory + client-side
instructions only.
