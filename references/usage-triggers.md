# Skill 触发方式分类（T1–T6）与「用量盲区」论证

> 用途：说明为什么 `skill-inventory` 不能只依赖 `usage-log.json` 判定「可关闭」。
> 本文件是 P0 护栏（反向依赖扫描 + 遥测缺口降级）的设计依据。

## 一、用户触发 Skill 的六种方式

| 编号 | 触发方式 | 典型场景 | 是否写入 usage-log |
|------|----------|----------|--------------------|
| **T1** | 显式调用 | 用户在对话里说「用 skill-inventory」或 `/skillname` | ✅ 是（Skill 工具显式调用会被记录） |
| **T2** | 描述自动匹配 | Agent 根据 SKILL.md 的 `description` 把用户意图自动匹配到某个 skill，用户**没点名** | ❌ 否 |
| **T3** | 关键词路由 | 用户或某份配置预先设定了「命中关键词 → 调用某 skill」，对话中只出现关键词 | ❌ 否 |
| **T4** | 自动化/定时任务 | automations 里的定时任务（cron/recurring）调用 skill | ❌ 否 |
| **T5** | 钩子（hooks） | 事件钩子在某种条件下触发 skill | ❌ 否 |
| **T6** | 专家/连接器内部调用 | 某个 Expert 组件或 Connector 在内部调动某个 skill | ❌ 否 |

## 二、用量盲区（为什么只看日志会误杀）

`usage-log.json` 当前只记录 **T1 显式调用**。T2–T6 全部不落日志。

市调结论（product-reviewer，对标 jiepi-skill / skill-monitor / audit-hermes）：普通用户**很少在对话里点名**某个 skill——
- 很多人是用「关键词触发」（T3）或「专家组件里嵌着 skill」（T6）来间接使用；
- 还有人是用定时任务（T4）/ 钩子（T5）让 skill 在后台跑。

 therefore：

- **T2–T6 的重度使用（每日/每周都在用）约 30–70%+ 在日志里完全不可见**；
- **轻量使用（偶发）约 10–20%+ 不可见**。

→ 如果 `skill-inventory` 仅凭「日志里没出现」就判定「可关闭」，会**误杀大量仍在被静默调用的关键 skill**。

## 三、本 Skill 的应对（P0 护栏）

1. **遥测缺口降级（telemetry-gap degradation）**：当 `usage-log.json` 缺失/损坏/无 `skills` 字段时，`load_usage()` 返回 `( {}, False )` 并打印 stderr 警告；此时 `cleanup` 桶**恒为空**，所有「近期无调用」的 skill 一律进入 `review`（人工确认），绝不自动建议关闭。
2. **反向依赖扫描（reverse-dependency scan）**：扫描 `automations/`、`hooks/`（用词边界正则，避免 `git` 误锁 `github`），凡被引用的 skill 直接锁进 `protected`。`settings.json` 是 skill 注册表，**刻意排除**（否则会误锁 23 个）。
3. **安全关键词 + 自保护 + `--protect`**：含 `security/audit/safe/guard/privacy/sanitize/compliance/backup` 的 leaf、本 skill 自身、以及用户显式 `--protect` 的，一律进 `protected`。
4. **永不自动关闭（never-auto-close）**：`cleanup` 桶只给「建议」，实际关闭动作必须由用户/人工执行。

## 四、仍待用户确认的边界

- 本地 automations / hooks / expert 定义的实际路径需用户确认，否则 `--refs` 反向依赖扫描无法真正生效（目前默认扫 `~/.workbuddy/automations` 与 `~/.workbuddy/hooks`）。
- 跨 agent（千问办公 / 百度搭子 / 天禧AI）的触发方式映射仍需各平台实测回填；本文以 WorkBuddy 为主。
