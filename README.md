# skill-inventory · 面向办公型 Agent 的技能库盘点与效能体检

为办公型 Agent（WorkBuddy、千问办公、百度搭子、天禧AI 等）做「技能库盘点 + 效能体检」：
扫描任意技能目录，统计数量 / 体积 / 上下文 token 占用，识别重复与近似技能，
并给出**保守**的瘦身建议。本工具只出报告、不关技能——判断权始终在人。

> 装得多不等于能力强。技能清单（name + description）每一轮对话都进模型上下文，
> 装 54 个技能约等于每轮白烧 5,000+ tokens。本工具给「哪些该关」提供事实依据。

## 什么时候用

- 想知道「我装了哪些技能」「哪些技能该关 / 该合并」「技能占了多少上下文」
- 想给办公型 Agent 做「效能体检」、压一压上下文 token 消耗
- 要盘点 WorkBuddy / 千问办公 / 百度搭子 / 天禧AI 等平台的技能目录

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

## 平台档位与能力感知关闭

不同 Agent 的「关闭」能力不同，本工具按 `can_close` 分叉——**不可关平台绝不产出任何关闭动作**，只给报告 + 手动移除指引：

| 平台 | 可扫描 | 有用量账本 | 可程序化关闭 | 本工具行为 |
|------|--------|-----------|-------------|-----------|
| **WorkBuddy** | ✅ `~/.workbuddy/skills` | ✅ `usage-log.json` | ✅ `skillOverrides` 四态 | 出盘点 + 可关闭草稿；`--apply --yes` 在你同意下写入 `off` |
| **千问办公** | ✅ `~/.qwenworkcn/skills` | ✅ 有（usage adapter 读取） | ❌ **无禁用开关**（实测） | 出盘点 + connector/UI 关闭说明，**绝不**代执行关闭 |
| **百度搭子** | ✅ 本地沙箱（路径待验→`--root`） | ❌ 无 | ✅ 禁用开关 + 专家套件禁用 | 出盘点 + 关闭指引；独占「专家套件」治理维度 |
| **通用档**（未知宿主，含天禧等云端沙箱） | ✅ `--root` 指定的目录 | ❌ 默认无（可用 `--usage-log` 指定） | ❌ 无关闭通道 | `--agent generic`：纯盘点 + 四档建议，全部落「需人工确认」，绝不产出关闭动作 |

> 原则：**未显式调用 ≠ 没用**。千问这类无关闭开关的平台，本工具只做「体检」，把「动刀」留给你手动处理，避免给出你根本执行不了的「关闭建议」。

## 🔒 P0 护栏（硬性，不可违背）

本工具的本质是「体检报告」，**不是「手术刀」**：

1. **绝不自动关闭技能。** 只输出建议文本，不写 `settings.json`、不调用任何禁用/删除接口。
   即使生成了 `--overrides` 骨架，也**必须等用户逐条显式确认后**才能动手，且优先引导用户用宿主自带的
   `/skills` 菜单（按 Esc 才落盘）而非直接改配置文件。
   · **在你同意下关闭（仅可关平台）**：在 WorkBuddy 等 `can_close` 平台，可加 `--apply --yes` 让工具**代你**
   把候选写入 `skillOverrides` 的 `off` 态；该动作**先自动备份 `settings.json`、且缺 `--yes` 只做 dry-run 预览**，
   绝不静默执行。千问等不可关平台会直接拒绝 `--apply`。
2. **受保护技能永远不进「可关闭」候选。** 包括：本工具自身、frontmatter 标了 `protected: true` 的技能、
   安全/审计类（名称含 security/audit/safe/guard/privacy/sanitize/compliance/backup），以及用户用
   `--protect` 追加的。报告里它们单列在「受保护」一档。
3. **未显式调用 ≠ 没用。** 用户可能**从不在对话里明说**要调某技能，而是：
   - 预先配置了**关键词/触发器**，让某类输入自动唤起它；
   - 借助会内部调用该技能的**专家/连接器组件**间接使用它。
   这两种用法在用量日志里**完全无痕**。所以**任何「可关闭候选」在关闭前，都必须向用户确认它是否仍被上述方式依赖**。
4. **遥测缺口不判死。** 当平台无用量日志、或日志读取失败（已修 P1，会显式告警而非静默），
   全库只能落「需人工确认」档，**绝不输出可关闭项**——宁可少报，不可误杀。
5. **反向依赖扫描（应对你最担心的场景）。** 在判「可关闭」前，工具会先扫自动化任务 / Hook 里的技能引用
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

## 许可证

MIT —— 见 [LICENSE](LICENSE)。
