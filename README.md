# skill-inventory · 面向办公型 Agent 的技能库盘点与效能体检

> English version: [README.en.md](README.en.md) · 文档语言：`SKILL.md`（中文）/ `SKILL.en.md`（English）

为办公型 Agent（WorkBuddy、千问办公、百度搭子、天禧AI 等）做「技能库盘点 + 效能体检」：
扫描任意技能目录，统计数量 / 体积 / 上下文 token 占用，识别重复与近似技能，
并给出**保守**的瘦身建议。**默认只读**：盘点、分类、建议全程不写任何文件；
写路径共两处、均需显式授权（`--overrides --apply --yes` 关闭写入，仅 WorkBuddy 等可关平台，
先自动备份；`--set-lang` 语言偏好写入）——判断权始终在人。

> 装得多不等于能力强。技能清单（name + description）每一轮对话都进模型上下文，
> 装 54 个技能约等于每轮白烧 5,000+ tokens。本工具给「哪些该关」提供事实依据。

## 什么时候用

- 想知道「我装了哪些技能」「哪些技能该关 / 该合并」「技能占了多少上下文」
- 想给办公型 Agent 做「效能体检」、压一压上下文 token 消耗
- 要盘点 WorkBuddy / 千问办公 / 百度搭子 / 天禧AI 等平台的技能目录
- 想把报告语言固定为中文或英文（或恢复自动跟随对话）

## 怎么用

脚本在 `scripts/skill_inventory.py`。默认盘点 WorkBuddy 技能库：

```bash
python scripts/skill_inventory.py                          # 完整表格 + 四档分类（auto 探测平台）
python scripts/skill_inventory.py --agent workbuddy        # 指定平台档位
python scripts/skill_inventory.py --agent qwen             # 千问办公（可扫不可关）
python scripts/skill_inventory.py --agent baidu --root DIR # 百度搭子（可扫可关，路径待验）
python scripts/skill_inventory.py --overrides              # 起草可关闭清单（仅草稿）
python scripts/skill_inventory.py --overrides --apply --yes   # WB：在你同意下写入 skillOverrides 关闭
python scripts/skill_inventory.py --json                   # 机器可读输出
python scripts/skill_inventory.py --protect a,b,c          # 追加受保护技能
```

跨办公型 Agent：用 `--agent` 选平台档位（workbuddy / qwen / baidu / auto），或用 `--root` 直接指向技能目录。
用量日志用 `--usage-log` 指定；**若该平台无用量日志，工具会自动降级为「不判任何技能可关闭」**。

## 语言设置（auto / zh / en）

| 选项 | 说明 |
|------|------|
| `auto`（默认） | 自动——Agent 按当前对话语言传 `--lang` 决定；未传参时回落：环境变量 `SKILL_INV_LANG` → 系统区域语言 → 中文 |
| `zh` | 报告语言固定为中文（随时可用 `--set-lang` / `--lang` 改回） |
| `en` | 报告语言固定为英文（随时可用 `--set-lang` / `--lang` 改回） |

```bash
python scripts/skill_inventory.py --show-lang   # 查看当前设置、选项说明与切换方式
python scripts/skill_inventory.py --set-lang en # 保存偏好（写入 ~/.workbuddy/skill-inventory.json），立即生效
python scripts/skill_inventory.py --set-lang auto
python scripts/skill_inventory.py --lang en     # 仅本次运行覆盖，不改已保存设置
```

保存后切换立即生效；`--set-lang auto` 或删除 `~/.workbuddy/skill-inventory.json` 即恢复默认。
`auto` 是「尚未表达偏好时的回落」而非锁定——随时 `--set-lang` 固定语言，或 `--lang` 单次覆盖。
四档分类标识恒为英文，`--json` 键恒为英文——程序化消费不受语言设置影响。

## 平台档位与能力感知关闭

不同 Agent 的「关闭」能力不同，本工具按 `can_close` 分叉——**不可关平台不产出任何关闭动作**，只给报告 + 手动移除指引：

| 平台 | 可扫描 | 有用量账本 | 可程序化关闭 | 本工具行为 |
|------|--------|-----------|-------------|-----------|
| **WorkBuddy** | ✅ `~/.workbuddy/skills` | ✅ `usage-log.json` | ✅ `skillOverrides` 四态 | 出盘点 + 可关闭草稿；`--apply --yes` 在你同意下写入 `off` |
| **千问办公** | ✅ `~/.qwenworkcn/skills` | ✅ 有（usage adapter 读取） | ❌ **无禁用开关**（实测） | 出盘点 + connector/UI 关闭说明，不代执行关闭 |
| **百度搭子** | ✅ 本地沙箱（路径待验→`--root`） | ❌ 无 | ✅ 禁用开关 + 专家套件禁用 | 出盘点 + 关闭指引；独占「专家套件」治理维度 |
| **通用档**（未知宿主，含天禧等云端沙箱） | ✅ `--root` 指定的目录 | ❌ 默认无（可用 `--usage-log` 指定） | ❌ 无关闭通道 | `--agent generic`：纯盘点 + 四档建议，全部落「需人工确认」，不产出关闭动作 |

> 原则：**未显式调用 ≠ 没用**。千问这类无关闭开关的平台，本工具只做「体检」，把「动刀」留给你手动处理，避免给出你根本执行不了的「关闭建议」。

## 🔒 行为契约（先读这段再信任它）

**默认只读，写路径两处目标 + 一份备份工件、均需显式授权：**

1. **默认不写任何文件。** 盘点、分类、建议全程只读；不调用任何禁用/删除接口。
2. **写路径一（关闭，需你显式授权）。** 在 WorkBuddy 等可关平台上，`--overrides --apply --yes`
   会**先自动备份 `settings.json`**，再把候选合并进 `skillOverrides` 的 `off` 态；
   缺 `--yes` 只做 dry-run 预览（不读写任何文件）；千问等不可关平台直接拒绝 `--apply`。
   每份报告和 `--overrides` 输出都会显式标注这条写路径——本工具**不会**静默或自行关闭任何技能。
   优先引导宿主自带开关（如 `/skills` 菜单，按 Esc 才落盘）。
   **备份工件**：`--apply --yes` 落笔前在 `settings.json` 旁生成 `settings.json.bak.<时间戳>`
   安全副本，路径打印在输出里；副本惰性、不会被回读，可随时自行删除。
3. **写路径二（语言偏好，需你显式触发）。** `--set-lang auto|zh|en` 把报告语言偏好写入
   `~/.workbuddy/skill-inventory.json`（仅此一个键）；这是一项用户可控的显示偏好，
   `--set-lang auto` 或删除该文件即恢复默认。
4. **无持久化机制。** 不注册定时任务 / cron、不写启动项、不留守护进程、不自我修改。
   跨会话效果仅两处，均为用户显式授权的公开功能、随时可逆——`skillOverrides` 的 off 项
   （可在宿主 `/skills` 菜单恢复）与语言偏好文件。语言偏好文件只是显示偏好（单个 JSON 键）：
   不基于它注册或排程任何东西，仅在下一次运行时被读取用来挑报告语言；`--set-lang auto`
   或删除该文件即恢复默认——它不属于驻留机制。
5. **受保护技能永远不进「可关闭」候选。** 包括：本工具自身、frontmatter 标了 `protected: true` 的技能、
   安全/审计类（名称含 security/audit/safe/guard/privacy/sanitize/compliance/backup），以及用户用
   `--protect` 追加的。报告里它们单列在「受保护」一档。
6. **未显式调用 ≠ 没用。** 用户可能**从不在对话里明说**要调某技能，而是：
   - 预先配置了**关键词/触发器**，让某类输入自动唤起它；
   - 借助会内部调用该技能的**专家/连接器组件**间接使用它。
   这两种用法在用量日志里**完全无痕**。所以**任何「可关闭候选」在关闭前，都必须向用户确认它是否仍被上述方式依赖**。
7. **遥测缺口不判死。** 当平台无用量日志、或日志读取失败（已修 P1，会显式告警而非静默），
   全库只能落「需人工确认」档，**不输出可关闭项**——宁可少报，不可误杀。
8. **反向依赖扫描（应对你最担心的场景）。** 在判「可关闭」前，工具会先扫自动化任务 / Hook 里的技能引用
   （默认 `~/.workbuddy/automations` 与 `~/.workbuddy/hooks`，可用 `--refs` 追加）。
   **凡被引用的技能一律锁定为「受保护」**——无论它有没有用量日志。这堵住了
   「用户只设了关键词/触发器、或借专家·连接器组件间接调用，日志里完全无痕」导致的误杀。
   若你的引用定义在别处，用 `--refs /path/to/defs` 指明；想完全关掉用 `--no-ref-scan`。

## 输出怎么读

- **有使用记录**：确实用过（可信）。
- **可关闭候选**：无使用记录 且 超过 30 天没改过。**仍须人工确认**，且先排除关键词/专家触发依赖。
- **需人工确认**：无使用记录但近期改过，或本平台无遥测——别急着关。
- **受保护**：永不自动建议关闭，须人工明确介入。

## 局限性（如实告知）

- 调用频率只依赖平台用量日志；WorkBuddy 有真账本（`usage-log.json`），其余平台多数无等价账本，
  此时结论仅基于最后修改时间，**不可作为关闭依据**。
- 无法从文件系统探测「关键词触发器/专家组件」依赖，这是结构性盲区，只能靠用户确认兜底。
- 重复检测是名称/描述/体积的近似比对，不是语义级去重。

## 关于自动化扫描器的说明（SkillSpector findings 与逐条回应）

部分自动扫描器（如 ClawHub SkillSpector）会对本技能报出若干条 findings。绝大多数属于**检查局限**
或**对已披露能力的重复提示**，不是可疑行为。下表逐条给出可核对的事实依据（行数为 v1.3.1 实测）：

| 规则 | 扫描器的说法 | 事实依据与回应 |
|---|---|---|
| **Ae1** 引用的工件未被完整检查 | 无法把 `scripts/skill_inventory.py` 完整纳入上下文检查 | **检查能力局限**。该脚本 v1.3.1 实测 1293 行，零第三方依赖（仅标准库，`yaml` 为可选加速项）。同一文件的**静态分析层结论为 Pass**（"No suspicious patterns detected"）。完整源码公开在 [GitHub 仓库](https://github.com/Elisabeth15501/skill-inventory)，可随时人工审查。findings 条数随脚本行数增长（7→11→12），与代码量正相关，不反映行为变化 |
| **Lp1** 能力宽于声明 | 脚本会写盘，能力范围超出声明 | 声明已补全为**两处写目标 + 一份备份工件**（frontmatter `permissions` 与脚本头部声明块均可 grep 验证）：① `settings.json` 的 `skillOverrides` 键——需 `--apply --yes` 双显式 flag，缺一即 dry-run；② 语言偏好文件——需显式 `--set-lang`；③ `settings.json.bak.<ts>` 安全副本——仅在第①步落笔前生成，路径打印在输出里，从不回读。逐条见上方「行为契约」 |
| **Session Persistence** | 存在跨会话驻留 | 无 cron / 启动项 / 守护进程 / 自我修改。语言偏好文件是显示偏好（单个 JSON 键），不基于它注册或排程任何东西，仅在下次运行时被读取一次；`--set-lang auto` 或删文件即恢复默认 |
| **Anti-Refusal** | 文档出现「always / 始终」类措辞 | 已改为「报告语言固定为 X（随时可改回）」——描述的是**工具输出语言**，不构成对用户的服从承诺 |
| **Rp1** | 供应链存在未钉版依赖 | 技能运行零外部依赖（Python 标准库）；文档中的发布命令已钉 `clawhub@0.23.3`，不用 `@latest` |
| **NL Policy** | 语言选择 | 三选项 auto / zh / en。auto 是**用户未表达偏好时的回落**，不是锁定：随时 `--set-lang` 固定，或 `--lang` 单次覆盖 |

**平台侧结论**：静态分析 + 人工复核均为 **Moderate CLEAN**；扫描器 Overview 自述
"disclosed, user-triggered… no evidence of hidden network, persistence, or destructive behavior"。
脚本头部另有一块机器可 grep 的「权限与持久化声明」，欢迎直接验证。若你发现声明与实现不符，
请优先回报 issue——这比任何扫描器判定都更快地修正问题。

## 许可证

MIT —— 见 [LICENSE](LICENSE)。
