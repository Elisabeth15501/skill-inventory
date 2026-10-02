# Skill 触发方式分类（T1–T6）与「用量盲区」论证 / Skill trigger taxonomy (T1–T6) and the telemetry blind spot

> **文档定位 / What this file is**：这是 skill-inventory **设计依据文档**，论证「为什么不能只依赖
> usage-log.json 判定可关闭」。它描述的是**各平台的通用机制**，不是本技能的触发配置。
> This is a design-rationale document. It explains platform-wide trigger mechanics — it is NOT
> this skill's trigger configuration.
>
> **本技能的触发边界 / This skill's actual trigger scope**：只响应「技能库盘点 / 效能体检 / 关闭前
> 影响评估」类请求（如「盘点我装了哪些技能」「哪些技能可以关」「关闭 XX 前看影响」）；写周报、发邮件、
> 代码生成等无关任务不触发。Only inventory / health-check / pre-close impact requests match;
> unrelated tasks never trigger it.

> 用途：说明为什么 `skill-inventory` 不能只依赖 `usage-log.json` 判定「可关闭」。
> 本文件是 P0 护栏（反向依赖扫描 + 遥测缺口降级）的设计依据。

## 一、用户触发 Skill 的六种方式 / Six ways users invoke a skill

| 编号 ID | 触发方式 Trigger | 典型场景 Typical case | 写入 usage-log? Logged? |
|------|----------|----------|--------------------|
| **T1** | 显式调用 Explicit | 用户在对话里说「用 skill-inventory」或 `/skillname` | ✅ 是 Yes |
| **T2** | 描述自动匹配 Auto-match | Agent 根据 SKILL.md 的 `description` 把用户意图自动匹配到某个 skill，用户**没点名** / agent matches the task against skill descriptions; the user never names it | ❌ 否 No |
| **T3** | 关键词路由 Keyword routing | 用户或某份配置预先设定了「命中关键词 → 调用某 skill」，对话中只出现关键词 | ❌ 否 No |
| **T4** | 自动化/定时任务 Automation / scheduled | automations 里的定时任务（cron/recurring）调用 skill | ❌ 否 No |
| **T5** | 钩子 Hooks | 事件钩子在某种条件下触发 skill | ❌ 否 No |
| **T6** | 专家/连接器内部调用 Expert/connector-internal | 某个 Expert 组件或 Connector 在内部调动某个 skill | ❌ 否 No |

## 二、用量盲区（为什么只看日志会误杀） / The blind spot (why logs alone mislead)

`usage-log.json` 当前只记录 **T1 显式调用**。T2–T6 全部不落日志。
`usage-log.json` records T1 only; T2–T6 leave no trace.

市调结论（product-reviewer，对标 jiepi-skill / skill-monitor / audit-hermes）：普通用户**很少在对话里点名**某个 skill——
- 很多人是用「关键词触发」（T3）或「专家组件里嵌着 skill」（T6）来间接使用；
- 还有人是用定时任务（T4）/ 钩子（T5）让 skill 在后台跑。

therefore：

- **T2–T6 的重度使用（每日/每周都在用）约 30–70%+ 在日志里完全不可见**；
  Heavy T2–T6 usage (daily/weekly) is ~30–70%+ invisible in logs (composite estimate from the
  sources below, not a single-source measurement — see the research archive, wiki §8).
- **轻量使用（偶发）约 10–20%+ 不可见**。

→ 如果 `skill-inventory` 仅凭「日志里没出现」就判定「可关闭」，会**误杀大量仍在被静默调用的关键 skill**。
→ Closing on "absent from the log" alone would kill many skills that are still silently in use.

## 三、本 Skill 的应对（P0 护栏） / This skill's countermeasures (P0 guardrails)

1. **遥测缺口降级（telemetry-gap degradation）**：当 `usage-log.json` 缺失/损坏/无 `skills` 字段时，`load_usage()` 返回 `( {}, False )` 并打印 stderr 警告；此时 `cleanup` 桶**恒为空**，所有「近期无调用」的 skill 一律进入 `review`（人工确认），不自动建议关闭。
   When the log is missing/corrupt, the closeable bucket stays empty and everything lands in manual review.
2. **反向依赖扫描（reverse-dependency scan）**：扫描 `automations/`、`hooks/`（用词边界正则，避免 `git` 误锁 `github`），凡被引用的 skill 直接锁进 `protected`。`settings.json` 是 skill 注册表，**刻意排除**（否则会误锁 23 个）。
   Word-boundary regex scanning of automation/hook configs; referenced skills are locked as protected.
3. **安全关键词 + 自保护 + `--protect`**：含 `security/audit/safe/guard/privacy/sanitize/compliance/backup` 的 leaf、本 skill 自身、以及用户显式 `--protect` 的，一律进 `protected`。
4. **写路径唯一且需授权（single consented write path）**：默认只读；`cleanup` 桶只给「建议」。唯一的落盘动作是 `--overrides --apply --yes`（先自动备份 `settings.json`，缺 `--yes` 仅 dry-run），由用户显式触发。
   Read-only by default; the only disk write is `--overrides --apply --yes` (auto-backup first, dry-run without `--yes`), always user-initiated.

## 四、仍待用户确认的边界 / Open boundaries needing user confirmation

- 本地 automations / hooks / expert 定义的实际路径需用户确认，否则 `--refs` 反向依赖扫描无法真正生效（目前默认扫 `~/.workbuddy/automations` 与 `~/.workbuddy/hooks`）。
- 跨 agent（千问办公 / 百度搭子 / 天禧AI）的触发方式映射仍需各平台实测回填；本文以 WorkBuddy 为主。
- Cross-agent trigger mappings (QwenWork / Baidu / Tianxi) still need per-platform field testing;
  this document is WorkBuddy-first.
