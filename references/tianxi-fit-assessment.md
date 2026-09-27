# skill-inventory × 天禧 AI（联想）适配度评估

> 调研来源：联想开放平台 open.lenovomm.com 开发者文档 + 天禧 Claw 产品资料 + OpenClaw 沙箱机制三方资料交叉验证。
> 调研日期：2026-09-28。结论：**适配度低（作为天禧「运行时 skill」）**。

## 一、结论（一句话）

skill-inventory 现在「扫**本地** skills 目录 + 读**本地** usage-log + 反向依赖扫描」的核心逻辑，
在天禧的执行模型下**跑不通**。把它原样提交到天禧技能广场，运行时几乎无事可做，只会因「读不到目录 / 打不开日志」而报错或产出空报告。

## 二、三条硬卡点

| # | 卡点 | 原因 |
|---|------|------|
| 1 | **无本机文件系统访问** | 天禧第三方 skill 跑在**云端沙箱**，接触不到用户本机 `~/.workbuddy/skills/` 或任何宿主机全局技能目录。扫描对象根本不存在。 |
| 2 | **无等价用量账本** | 天禧不向 skill 暴露 usage-log 或技能清单 API；平台内部按「调用率」发奖，但不开放给 skill 读取。 |
| 3 | **离线 + workspace 隔离** | `network.outbound:false`（禁出站网络）+ 仅能读写沙箱 workspace。既无法联网拉数据，也无法越界读宿主文件。 |

## 三、运行时规范关键事实（核实过）

- **执行环境**：天禧 Claw 基于 OpenClaw 架构，端云混合——核心任务在云端独立云主机执行，本地仅做交互入口。第三方上传 skill 在平台云端沙箱跑。
- **技能包结构**：ZIP 上传，**根层必须直接是 `SKILL.md`**，包体 ≤10MB，平台自动识别 Slug/名称/描述。可选目录：`scripts/`（AI 直接 shell 调用）、`references/`、`assets/`。
- **SKILL.md frontmatter**（通用 Agent Skills 规范，天禧同源）：必填 `name`（小写 kebab-case、与目录名一致）、`description`（含触发关键词）；可选 `version / license / compatibility / metadata / allowed-tools`。
- **权限/联网模型**：`network.outbound:false` = 禁任何出站网络；沙箱把代码限制在 workspace 根目录内，禁止读写 workspace 外路径；禁不受控子进程（`os.system`/`subprocess` 被禁）。与本项目已满足的红线一致。
- **触发方式**：自然语言显式、定时任务（云端后台）、多 Agent 协作、平台经 A2A 调度 Skill/MCP/连接器/Agent。
- **遥测**：平台内部有「调用率」，但**不向 skill 暴露**等价 usage-log。

## 四、若仍想上架天禧：改造方案

- **方案 A（推荐改造方向）——单包静态体检 skill**：定位从「扫全网技能库」转为「开发者自检工具」。用户在对话里上传/指向一个 skill 文件夹 → 在 workspace 内对它做静态分析（体积、目录结构、依赖库、`config.yaml` 合规、`network.outbound`/危险关键词 `os.system`/`subprocess`/`requests` 扫描、SKILL.md frontmatter 规范校验），产出体检报告。**完全离线、无需宿主文件访问、符合沙箱约束**，且契合天禧「轻量化、场景明确」的审核偏好。代价：丢掉「跨库扫描 + 用量交叉验证 + 反向依赖」的核心价值，退化为一个 skill linter。
- **方案 B（不推荐）——调天禧技能管理 API**：未检索到天禧向 skill 开放「查询全局技能清单/用量」的运行时 API（提交是 ZIP 上传，非 API 驱动），此路大概率不存在。
- **方案 C——纯文档/指南型 skill**：把方法论写成「如何在 WorkBuddy 上做技能盘点」的指引型 SKILL.md（无脚本或仅做静态体检），作为知识型 skill 上架。安全、易过审，但价值有限。

## 五、务实建议

**更优路径 = 先稳住 WorkBuddy 自有市场 + 作为跨平台 Python 审计脚本分发，而非把运行时扫描版硬塞进天禧。**

- skill-inventory 的**原生栖息地就是 WorkBuddy**：本机桌面 agent、可授权访问本机 skills 目录、`usage-log.json` 真实存在、反向依赖（automations/hooks）也在本机——它的全部核心能力只有在「能摸本机文件系统 + 本机用量日志」的平台才成立，这是天禧给不了的。
- **跨平台分发**：以独立 Python 脚本发到 GitHub / ClawHub，服务 Claude Code / Codex / Cursor / Hermes 用户（这些也是本机 agent，能扫本地 skills 目录；可对标 jiepi-skill、pi-skill-audit 的分发方式）。
- **天禧上架**：另做「Skill 体检 / 开发者自检」轻量版（方案 A）作为生态占位与引流，明确标注「本工具在你的 workspace 内分析单个 skill 包」，不要伪装成全局扫描器。
- **一句话**：天禧版和 WorkBuddy 版应是两件不同的作品——前者是离线单包 linter，后者才是真正的库级盘点器。别用后者的身份去闯前者的沙箱。

## 六、诚实标记（提交前需补核实）

- 天禧官方**完整的 `config.yaml` schema（capability/permission/network/trigger 全字段）**在公开检索中未找到权威文档；当前 `config.yaml` 相关约束以已确认项 + OpenClaw 沙箱通用规范为准。
- 提交前建议向联想开放平台工单核实 schema 必填项，以及是否存在 skill 运行时管理 API（影响方案 B 可行性）。
