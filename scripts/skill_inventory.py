#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill-inventory —— 办公型 Agent 的技能库盘点与效能体检 / Skill inventory & health check for office agents.

    python skill_inventory.py                      # WorkBuddy 默认盘点
    python skill_inventory.py --agent qwen         # 千问办公（有调用记录则显示，关闭走连接器）
    python skill_inventory.py --agent baidu         # 百度搭子（多根自动探测：全局/会话/插件/禁用；无调用遥测）
    python skill_inventory.py --unused             # 只看无使用记录的
    python skill_inventory.py --json               # 机器可读
    python skill_inventory.py --overrides          # 起草可关闭清单（草稿，需人工确认）
    python skill_inventory.py --overrides --apply --yes   # 在你同意下，WB 写入 skillOverrides 关闭
    python skill_inventory.py --lang en            # English report (default: zh)

行为边界 / Behaviour contract
----------------------------
默认只读 / Read-only by default: the tool inventories, classifies and prints advice. It writes
nothing unless you explicitly pass `--overrides --apply --yes` (WorkBuddy-family platforms only).
写路径仅限一处 / Single write path: `--apply --yes` merges "off" entries into ~/.workbuddy/settings.json
`skillOverrides`, after automatically backing up the file; without `--yes` it is a dry-run preview.
Platforms without a programmatic close channel (qwen / baidu / generic) reject --apply outright.
    python skill_inventory.py --overrides --apply --yes   # 在你同意下，WB 写入 skillOverrides 关闭

为什么需要它
------------
技能清单（name + description）每一轮对话都进模型上下文。装得多不等于能力强——
装 54 个技能约等于每轮白烧 5,000+ tokens。本脚本给出「哪些该关」的事实依据，
判断仍由人做。

两个数据源（WorkBuddy 示例；其他平台用 --root 指向其技能目录）
----------
  技能目录   ~/.workbuddy/skills/        每个 SKILL.md 的 frontmatter
  使用记录   ~/.workbuddy/usage-log.json 的 skills 键

⚠️ 使用记录的口径是「Skill 工具被显式调用」，**有盲区**：
   · 技能被自动化 / 定时任务 / hook / 隐式加载不会计入；
   · 用户可能**从未在对话里明说**要调某 skill，而是：
       (a) 预先配置了「关键词/触发器」让某类输入自动唤起它；
       (b) 借助会内部调用该 skill 的「专家 / 连接器组件」间接使用它。
   这两种用法在用量日志里**完全无痕**。
   所以：有记录 ⇒ 确实用过（可信）；无记录 ⇒ **绝不**直接判死。

🔒 P0 护栏（本工具的硬性安全设计）
------------------------------
  1. 受保护技能（见 PROTECTED_LEAVES / frontmatter `protected: true` / 安全关键词启发式）
     永不进入「可关闭」候选，单独列出「需人工介入才能关闭」。
  2. 默认只读 / Read-only by default：盘点、分类、建议全程不写任何文件。写路径仅限一处，即
     `--overrides --apply --yes`（仅 WorkBuddy 等可关平台）：先自动备份 settings.json，
     再把候选合并进 skillOverrides；缺 `--yes` 时只做 dry-run 预览，不读写任何文件。
     / Read-only by default: the only write path is `--overrides --apply --yes` (can_close
     platforms only), which backs up settings.json first; without --yes it is a dry-run.
  3. 遥测缺口降级：当平台无用量日志 / 日志读取失败时，**全库不判为可关闭**，
     只给「需人工确认」档，并显式告警「无法确认冷技能」。
  4. 反向依赖扫描：判「可关闭」前，先扫自动化 / Hook / 专家·连接器 / 子 agent 的定义文件，
     凡被引用的技能**锁定**进受保护桶——堵住「被关键词触发器或专家组件间接调用却无使用日志」的误杀。
  5. **能力感知关闭（capability-aware close）**：不同 Agent 的「关闭」能力不同——
     · 千问办公等**无关闭单技能开关**的平台：本工具不产出任何关闭动作，只给盘点 +
       手动移除目录指引（避免给出用户根本执行不了的「关闭建议」）。
     · WorkBuddy / 百度搭子等**可关闭**平台：才输出关闭动作；且 WB 的 `--apply --yes`
       仅在**你显式同意**下、并先自动备份后才落地。

零依赖：自带最小 frontmatter 解析（支持 key: value 与 key: > 块）。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import re
import shutil
import sys
import time

try:                      # 有 PyYAML 就用真解析器：内置解析器对含空行的折叠块会截断
    import yaml            # type: ignore
except ImportError:       # 零依赖环境下回退
    yaml = None

HOME = pathlib.Path.home()
APPDATA = pathlib.Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))
SKILLS_DIR = HOME / ".workbuddy" / "skills"
USAGE_LOG = HOME / ".workbuddy" / "usage-log.json"

# 30 天内改动过 = 视为「可能新建/在用」。usage-log 对新建技能必然没有记录，
# 不设这道闸就会把刚写的技能也判成「该关」。
RECENT_DAYS = 30

# ───────────────────────────── 平台档位（能力感知） ─────────────────────────────
# skills_root   ：技能根目录列表。多数平台单根；百度搭子多根（全局/会话/插件/禁用分散）。
# usage_log     ：用量账本路径；为 None 表示本平台未向技能暴露单技能用量（遥测缺口降级）。
# usage_adapter ：用量格式适配器键（None=WorkBuddy 原生；"qwen"=usageCount/lastUsedAt）。
# can_close     ：工具是否产出「可关闭候选 + 关闭草稿」。
# close_kind    ："filesystem"（WB 写 skillOverrides）/ "connector"（千问/百度经连接器或 UI 开关，工具不代执行）。
PLATFORMS = {
    "workbuddy": {
        "label": "WorkBuddy", "label_en": "WorkBuddy",
        "skills_root": [HOME / ".workbuddy" / "skills"],
        "usage_log": HOME / ".workbuddy" / "usage-log.json",
        "usage_adapter": None,
        "can_close": True,
        "close_kind": "filesystem",
    },
    "qwen": {
        "label": "千问办公", "label_en": "QwenWork",
        "skills_root": [HOME / ".qwenworkcn" / "skills"],   # 实测真机路径（非 .qwenwork）
        "usage_log": HOME / ".qwenworkcn" / "skill-usage.json",  # 实测存在：usageCount/lastUsedAt
        "usage_adapter": "qwen",
        "can_close": True,            # 连接器 supportedActions 含 enable/disable/remove → 可关
        "close_kind": "connector",    # 关闭通道在 qwenwork 连接器，不经文件系统
    },
    "baidu": {
        "label": "百度搭子", "label_en": "Baidu DuMate",
        "skills_root": None,          # 多根（全局/会话/插件/禁用），由 detect_baidu_roots 自动探测
        "usage_log": None,            # 本机/云端均未暴露单技能用量日志 → 遥测缺口
        "usage_adapter": None,
        "can_close": True,            # 禁用开关 + 专家套件禁用（在客户端 UI）
        "close_kind": "connector",
        "multi_root": True,
    },
    # 通用档（generic）：未识别宿主 / 自定义目录。参赛（天禧沙箱等）与任意办公 Agent 的兜底：
    # 只盘点 + 建议，永不程序化关闭，无遥测就诚实降级——「宁少报，不误杀」在陌生环境里是安全网。
    "generic": {
        "label": "通用（自定义目录）", "label_en": "Generic (custom dir)",
        "skills_root": None,          # 必须由 --root 指定
        "usage_log": None,            # 默认无遥测；可用 --usage-log 显式提供
        "usage_adapter": None,
        "can_close": False,           # 未知宿主 → 绝不产出「可关闭」，全落「需人工确认」
        "close_kind": "none",
    },
}


# ───────────────────────────── P0 护栏数据 ─────────────────────────────
# 默认受保护（永远不进「可关闭」候选）。可自行扩展或用 --protect / --protect-file 追加。
PROTECTED_LEAVES = {
    "skill-inventory",          # 本工具自身
}

# 安全/审计类技能启发式关键词：命中即视为「重要，需人工确认才能关」。
# 可用 --no-safety-heuristic 关闭（若你的命名恰好误命中）。
SAFETY_KEYWORDS = (
    "security", "audit", "safe", "guard", "privacy",
    "sanitize", "compliance", "backup",
)

# 反向依赖扫描的默认参照根（存在才扫）：只扫「定义目录」，不扫 settings.json
# —— settings.json 是技能登记册（全量清单），扫它会造成整本技能册被误锁为「受保护」。
# 真正的「被自动化 / Hook / 专家·连接器调用」定义应在 automations/、hooks/ 等目录里；
# 若你的引用定义在别处，用 --refs 显式指。
DEFAULT_REF_ROOTS = [
    HOME / ".workbuddy" / "automations",
    HOME / ".workbuddy" / "hooks",
]


# ───────────────────────────── 解析层 ─────────────────────────────
def parse_frontmatter(text: str) -> dict:
    """解析 frontmatter。优先用 PyYAML；无则回退内置解析器。

    内置解析器只认**顶层**键，三种标量都支持：
    单行（可带引号）、块标量（`>` / `|`，允许含空行）、普通标量跨行续写。
    """
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
    if end is None:
        return {}
    body = lines[1:end]

    if yaml is not None:
        try:
            data = yaml.safe_load("\n".join(body))
            if isinstance(data, dict):
                return data
        except Exception:
            pass  # 解析失败再回退，保证不因单个坏文件中断盘点

    return _fallback_frontmatter(body)


def _fallback_frontmatter(lines: list) -> dict:
    """零依赖回退解析器：只提取顶层键，忽略所有缩进的嵌套结构。"""
    fm: dict = {}
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip() or line[:1] in (" ", "\t"):  # 空行/缩进行 → 属于嵌套结构
            i += 1
            continue
        key, sep, val = line.partition(":")
        if not sep:
            i += 1
            continue
        key, val = key.strip(), val.strip()

        if val in (">", "|", ">-", "|-", ">+", "|+"):        # 块标量：收到底
            j, buf = i + 1, []
            while j < n and (not lines[j].strip() or lines[j][:1] in (" ", "\t")):
                buf.append(lines[j].strip())
                j += 1
            fm[key] = " ".join(x for x in buf if x).strip()
            i = j
            continue

        if val:                                              # 单行标量
            fm[key] = val.strip("\"'")
            j, buf = i + 1, []
            while j < n and lines[j][:1] in (" ", "\t") and lines[j].strip():
                nxt = lines[j].strip()
                if nxt.startswith("- ") or ":" in nxt.split(" ", 1)[0]:
                    break                                    # 列表项 / 嵌套键 → 不是续写
                buf.append(nxt)
                j += 1
            if buf:
                fm[key] = f"{fm[key]} {' '.join(buf)}".strip()
                i = j
            else:
                i += 1
            continue

        fm.setdefault(key, "")                               # 空值：保留键，之后不覆盖
        i += 1
    return fm


def norm(s: str) -> str:
    return (s or "").lower().replace("_", "-").strip()


def _adapt_qwen(raw: dict) -> dict:
    """千问 skill-usage.json：{"<skill>": {"usageCount": n, "lastUsedAt": <ms>}}
    归一化为内部统一 schema：{uid: {"lastUsedDate": iso, "recentDates": [], "uses": n}}。"""
    out = {}
    for uid, v in raw.items():
        if not isinstance(v, dict):
            continue
        n = int(v.get("usageCount") or 0)
        ms = v.get("lastUsedAt")
        iso = ""
        if ms:
            try:
                iso = _dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")
            except Exception:
                iso = ""
        out[uid] = {"lastUsedDate": iso, "recentDates": [], "uses": n}
    return out


def load_usage(path, adapter=None) -> tuple:
    """返回 (usage_dict, telemetry_available: bool)。

    usage_dict 统一为 {uid: {"lastUsedDate": iso, "recentDates": [...], "uses": n}}。
    adapter="qwen" 时先把千问格式归一化。

    P1 已修复：原先静默吞异常返回 {}，会导致日志一旦损坏/轮换，全库无声变成
    「未使用」→ 整套关闭建议 100% 错误且无人察觉。现在改为 stderr 显式告警，
    并返回 available=False，让上层走「遥测缺口降级」分支（不判死）。
    """
    if path is None or not path.exists():
        print(M("warn_no_log"),
              file=sys.stderr)
        return {}, False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if adapter == "qwen":
            data = _adapt_qwen(raw)
        else:
            data = raw.get("skills") or {}
        return data, True
    except Exception as e:  # noqa: BLE001 - 我们就是要兜住一切解析错误并告警
        print(M("warn_log_fail", e=e),
              file=sys.stderr)
        return {}, False


def scan(roots: list, market_resolver=None) -> list:
    """扫描技能根目录（支持多根合并），返回技能行列表。

    roots: list of dict {"path": Path, "label": str, "disabled": bool}
      - label 非空且多根时，dir 字段加区域前缀便于区分同名技能。
      - disabled=True 表示该区域是「已禁用」库（如 .skills_disabled）。
    market_resolver: 可选 callable(skill_dir: Path) -> bool，覆盖默认的「_meta.json 存在即市场」判定
        （千问用它改读中心化 lock 文件的 source 字段，见 _qwen_extra）。

    P1-4 已修复：rglob 会连带捞出 <skill>/references/SKILL.md 之类的嵌套文件，
    被误计为独立技能。现采用「最浅 SKILL.md 优先」规则——若某 SKILL.md 的祖先目录
    （介于其与 root 之间）也存在 SKILL.md，则该文件视为嵌套引用，跳过。

    多根去重：同名 leaf 出现在多个区域时，优先保留非 disabled 区域的那条
    （避免技能同时存在于 skills/ 与 .skills_disabled/ 时被重复计数）。
    """
    multi = len(roots) > 1
    raw: list = []
    for rd in roots:
        root = rd["path"]
        label = rd.get("label", "")
        disabled = rd.get("disabled", False)
        # 第一遍：收集所有技能目录（含 SKILL.md 的目录）
        skill_dirs = [p.parent for p in root.rglob("SKILL.md") if ".git" not in p.parts]
        skill_dir_set = set(skill_dirs)
        for sd in sorted(skill_dirs):
            # 排除嵌套：祖先（sd 与 root 之间，不含 root）若也是技能目录 → 跳过
            cur = sd.parent
            nested = False
            while cur != root:
                if cur in skill_dir_set:
                    nested = True
                    break
                if cur.parent == cur:        # 已到文件系统根，防死循环
                    break
                cur = cur.parent
            if nested:
                continue
            p = sd / "SKILL.md"
            text = p.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            files = [f for f in sd.rglob("*") if f.is_file() and ".git" not in f.parts]
            total = sum(f.stat().st_size for f in files)
            mtime = max((f.stat().st_mtime for f in files), default=0)
            leaf = sd.name
            name = fm.get("name") or leaf
            # 受保护判定（P0）：自保护清单 ∪ frontmatter 显式标记 ∪ 安全/审计类关键词启发式
            safety_hit = any(k in norm(name) or k in norm(leaf) for k in SAFETY_KEYWORDS)
            protected = (
                norm(leaf) in {norm(x) for x in PROTECTED_LEAVES}
                or str(fm.get("protected", "")).strip().lower() in ("true", "1", "yes", "y", "protected")
                or str(fm.get("critical", "")).strip().lower() in ("true", "1", "yes")
                or safety_hit
            )
            rel = sd.relative_to(root).as_posix()
            d = f"{label}/{rel}" if (multi and label) else rel
            raw.append({
                "dir": d,
                "leaf": leaf,
                "name": name,
                "desc": fm.get("description") or "",
                "from_market": (market_resolver(sd) if market_resolver is not None
                                else (sd / "_meta.json").exists()),
                "lines": len(text.splitlines()),
                "files": len(files),
                "kb": round(total / 1024, 1),
                "last_modified": _dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d") if mtime else "?",
                "mtime": mtime,
                "protected": protected,
                "safety_hit": safety_hit,
                "locked": False,
                "referenced_by": [],
                "region": label,
                "disabled_region": disabled,
            })
    # 多根去重：同名 leaf 优先非 disabled 区域；同时记录该 leaf 跨越的区域数与
    # 其中「非禁用」区域数（用于 P0-1 在报告中区分「真·多份激活」与「激活+禁用副本」）。
    seen: dict = {}
    order: list = []
    for r in raw:
        lf = norm(r["leaf"])
        if lf not in seen:
            seen[lf] = {"row": r, "regions": {r["region"]},
                        "active": 0 if r["disabled_region"] else 1}
            order.append(lf)
        else:
            seen[lf]["regions"].add(r["region"])
            if not r["disabled_region"]:
                seen[lf]["active"] += 1
            cur = seen[lf]["row"]
            if cur["disabled_region"] and not r["disabled_region"]:
                seen[lf]["row"] = r
    out = []
    for lf in order:
        info = seen[lf]
        row = info["row"]
        row["region_count"] = len(info["regions"])
        row["region_active_count"] = info["active"]
        out.append(row)
    return out


def _est_tokens(text: str) -> float:
    """CJK 字符约占 1.6 token/字，其余约 4 字符/token（P2-6 修正原 chars/3.2 低估）。"""
    cjk = sum(1 for ch in text if ord(ch) > 0x2E80)
    other = len(text) - cjk
    return cjk / 1.6 + other / 4.0


def _col_w(s: str) -> int:
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in s)


def _pad(s: str, width: int, align: str = "<") -> str:
    """按显示列（CJK=2）截断/补空格，保证表格对齐（P2-6）。"""
    cols = _col_w(s)
    if cols > width:
        out, c = [], 0
        for ch in s:
            w = 2 if ord(ch) > 0x2E80 else 1
            if c + w > width:
                break
            c += w
            out.append(ch)
        s, cols = "".join(out) + "…", width
    return (s + " " * (width - cols)) if align == "<" else (" " * (width - cols) + s)


def find_duplicates(rows: list) -> dict:
    """P0-1：按归一化名称分组，找出同名（疑似重复/冗余）技能。"""
    by_name: dict = {}
    for r in rows:
        by_name.setdefault(norm(r["name"]), []).append(r)
    return {k: v for k, v in by_name.items() if len(v) > 1}


def detect_baidu_roots(root_arg) -> list:
    """百度搭子多根探测：全局主库 + 各会话的 skills/plugins/.skills_disabled。

    返回 list of {"path","label","disabled"}；无法探测返回 None。
    可用 --root 显式指向单个区域目录（支持逗号分隔多个）。
    """
    if root_arg:
        parts = [x.strip() for x in root_arg.split(",") if x.strip()]
        out = []
        for x in parts:
            p = pathlib.Path(x)
            out.append({
                "path": p,
                "label": p.name,
                "disabled": (".skills_disabled" in p.parts or ".plugins_disabled" in p.parts),
            })
        return out or None
    xdg = APPDATA / "qianfan-desktop-app" / "qianfan_desk_xdg"
    if not xdg.is_dir():
        return None
    roots = []
    g = xdg / "global" / "data" / "skills"
    if g.is_dir() and any(g.rglob("SKILL.md")):
        roots.append({"path": g, "label": "全局主库", "disabled": False})
    for sess in sorted(xdg.iterdir()):
        if not sess.is_dir():
            continue
        for sub, lab, dis in (
            ("data/skills", "会话技能", False),
            ("data/plugins", "专家插件", False),
            ("data/.skills_disabled", "会话禁用", True),
        ):
            d = sess / sub
            if d.is_dir() and any(d.rglob("SKILL.md")):
                roots.append({"path": d, "label": lab, "disabled": dis})
    gd = xdg / "global" / "data" / ".skills_disabled"
    if gd.is_dir() and any(gd.rglob("SKILL.md")):
        roots.append({"path": gd, "label": "全局禁用", "disabled": True})
    gp = xdg / "global" / "data" / ".plugins_disabled"
    if gp.is_dir() and any(gp.rglob("SKILL.md")):
        roots.append({"path": gp, "label": "全局插件禁用", "disabled": True})
    return roots or None


def _qwen_extra(qwen_root: pathlib.Path):
    """千问专用：返回 (market_dirs: set|None, ref_roots: list)。

    market_dirs：来自 `skills/.skills_store_lock.json` 中 source!=local 的 installDir 集合，
        作为「来自市场/社区」的权威判定（P2-5：不再只靠逐目录的 _meta.json，后者千问仅 2/34 命中且无来源字段）。
        锁文件缺失时返回 None（交由 scan 走默认 _meta.json 判定）。
    ref_roots：可能隐式引用技能的配置——路由状态(.dws-skill-state.json 的 skillNames/routingFallbackSkill)、
        锁文件、各 skill 的 config.json、插件的 plugin.json（P2-7 反向依赖扫描根）。
    """
    skills = qwen_root / "skills"
    market_dirs = None
    lock = skills / ".skills_store_lock.json"
    if lock.exists():
        market_dirs = set()
        try:
            data = json.loads(lock.read_text(encoding="utf-8"))
            for v in (data.get("skills") or {}).values():
                if not isinstance(v, dict):
                    continue
                src = str(v.get("source", "")).lower()
                if src and src != "local":
                    idir = v.get("installDir")
                    if idir:
                        market_dirs.add(pathlib.Path(idir))
        except Exception:
            market_dirs = set()
    ref = []
    for f in ("skills/.dws-skill-state.json", "skills/.skills_store_lock.json", "mcp-adaptor.config"):
        p = qwen_root / f
        if p.exists():
            ref.append(str(p))
    for pat in ("skills/*/config.json", "plugins/*/.qoder-plugin/plugin.json"):
        for p in sorted(qwen_root.glob(pat)):
            ref.append(str(p))
    return market_dirs, ref


def attach_usage(rows: list, usage: dict) -> None:
    for r in rows:
        cands = {norm(r["leaf"]), norm(r["name"])}
        best = None
        for uid, v in usage.items():
            u = norm(uid)
            if any(c == u or (len(c) >= 5 and (c in u or u in c)) for c in cands if c):
                if best is None or (v.get("lastUsedDate") or "") > (best[1].get("lastUsedDate") or ""):
                    best = (uid, v)
        r["used_as"] = best[0] if best else None
        r["last_used"] = best[1].get("lastUsedDate") if best else None
        r["uses"] = best[1].get("uses", len(best[1].get("recentDates", []))) if best else 0


def _ref_kind(p: pathlib.Path) -> str:
    """按路径归类引用来源类型（影响预览用）：自动化 / Hook / 路由状态 / 插件清单等。"""
    parts = [x.lower() for x in p.parts]
    name = p.name.lower()
    if "automations" in parts:
        return "自动化"
    if "hooks" in parts:
        return "Hook"
    if name == ".dws-skill-state.json":
        return "路由状态"
    if name == ".skills_store_lock.json":
        return "商店锁"
    if ".qoder-plugin" in parts or name == "plugin.json":
        return "插件清单"
    if "mcp-adaptor" in name:
        return "MCP 配置"
    if name == "config.json":
        return "技能配置"
    return "其他配置"


def scan_references(rows: list, ref_roots: list) -> dict:
    """反向依赖扫描（P0 增强）：在自动化 / Hook / 专家·连接器 / 子 agent 定义里找对本技能的引用。

    用户可能从不在对话里明说要调某 skill，而是被「关键词触发器 / 自动化任务 / Hook /
    专家·连接器组件」间接调用——这些在用量日志里**完全无痕**。直接扫描这些定义文件，
    凡被引用即**锁定**，绝不作为「可关闭」候选。思路借鉴 Hermes skill-drift-check 的 pre-flight 校验。

    返回（P0 影响预览结构化）：
        {skill_dir: [{"path": 完整路径, "kind": 来源类型, "terms": [命中的技能名, ...]}]}
    其中条目按 (kind, path) 排序；结构化目的：报告可输出「关闭 X 将断掉哪些链路」的因果映射。
    """
    search = {}   # 归一化术语 -> (skill_dir, 原始术语)
    for r in rows:
        for key in (r["leaf"], r["name"]):
            nk = norm(key)
            if nk:
                search[nk] = (r["dir"], key)
    files = []
    for root in ref_roots:
        p = pathlib.Path(root)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and f.suffix.lower() in (
                    ".json", ".md", ".yaml", ".yml", ".txt", ".py", ".toml"
                ) and ".git" not in f.parts:
                    files.append(f)
    # 词边界精确匹配：整词/连字符 token 才算引用（避免 "git" 误锁 "github" 等子串误判）
    patterns = {
        nk: re.compile(r"(?<![\w@/-])" + re.escape(nk) + r"(?![\w@/-])")
        for nk in search
    }
    referenced = {}   # skill_dir -> {path_str: {"path","kind","terms":set}}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            continue
        hit_dirs = {}
        for nk, (d, orig) in search.items():
            if patterns[nk].search(text):
                hit_dirs.setdefault(d, set()).add(orig)
        if not hit_dirs:
            continue
        for d, terms in hit_dirs.items():
            files_map = referenced.setdefault(d, {})
            entry = files_map.setdefault(str(f), {"path": str(f), "kind": _ref_kind(f), "terms": set()})
            entry["terms"] |= terms
    out = {}
    for d, fm in referenced.items():
        entries = sorted(fm.values(), key=lambda e: (e["kind"], e["path"]))
        for e in entries:
            e["terms"] = sorted(e["terms"])
        out[d] = entries
    return out


def classify(rows: list, telemetry: bool, can_close: bool) -> dict:
    """三档分类 + 受保护桶。

    - protected：受保护清单命中 → 永远不关，需人工介入。
    - cleanup  ：无使用记录 且 超过 RECENT_DAYS 天没改过 → 候选可关闭（仍需人工确认）。
    - review   ：其余「无使用记录但近期改过 / 或平台无遥测」→ 需人工确认，不可自动关。
    - keep    ：有使用记录。

    🔒 P0 关键一：当 telemetry=False（无遥测/读取失败），cleanup 桶恒为空，
       所有无记录技能落入 review，并打「遥测缺口」标记。
    🔒 能力感知关键二：当 can_close=False（平台不支持程序化关闭），**即使有遥测也绝不产出
       cleanup**——避免给用户在千问等平台上根本执行不了的「关闭建议」。
    """
    now = time.time()
    buckets = {
        "protected": [], "keep": [], "cleanup": [], "review": [],
        "telemetry_gap": not telemetry, "cannot_close": not can_close,
    }
    for r in rows:
        if r["protected"] or r.get("locked"):
            buckets["protected"].append(r)
            continue
        if r["used_as"]:
            buckets["keep"].append(r)
            continue
        recent = (now - (r["mtime"] or 0)) < RECENT_DAYS * 86400
        if can_close and telemetry and not recent:
            buckets["cleanup"].append(r)
        else:
            # 无遥测、或近期改过、或平台不可关 → 都只能算「需人工确认」，绝不自动判死
            buckets["review"].append(r)
    return buckets


# ---------------------------------------------------------------------------
# i18n：报告语言（--lang en|zh，默认 zh）。键名按「函数_语义」命名。
# ---------------------------------------------------------------------------
LANG = "zh"
S = {
    # --- report(): 遥测口径 ---
    "tel_gap_1": ("⚠️  [遥测缺口] 本目录/平台无可用用量日志，无法确认冷技能。",
                  "⚠️  [Telemetry gap] No usable usage log on this platform; cold skills cannot be confirmed."),
    "tel_gap_2": ("    以下结论只基于「最后修改时间」，不可作为关闭依据——请人工确认每个技能是否",
                  "    Conclusions below rest on last-modified time only and must not close anything — please manually"),
    "tel_gap_3": ("    仍被「关键词触发器 / 自动化 / 专家·连接器组件」间接使用。\n",
                  "    confirm each skill is not indirectly used via keyword triggers / automations / experts.\n"),
    "tel_scope_1": ("ℹ  遥测口径：用量日志只覆盖「显式调用」（T1）。自动挂载 / 定时任务 / Hook / 专家内部",
                    "ℹ  Telemetry scope: the usage log only records explicit invocations (T1). Auto-mounting, scheduled"),
    "tel_scope_2": ("   调用（T2–T6）不计入——「有使用记录」≠「只被显式用过」，「无使用记录」也不等于",
                    "   tasks, hooks and expert-internal calls (T2–T6) are not counted. \"Used\" ≠ \"explicitly used\", and"),
    "tel_scope_3": ("   「没在用」（反向依赖扫描只兜住可发现的配置根）。\n",
                    "   \"no record\" ≠ \"unused\" (reverse-dependency scanning covers discoverable config roots only).\n"),
    # --- report(): 平台 notices ---
    "conn_note": ("🔒 注意：{label} 的关闭/禁用在客户端 UI 或对应连接器操作（技能列表「启用开关」/ 专家套件禁用），本工具不代执行任何关闭动作。\n",
                  "🔒 Note: in {label}, closing/disabling happens in the client UI or connector (enable toggle / expert-suite disable). This tool never performs a close action itself.\n"),
    "gen_note_1": ("ℹ  {label}：未识别宿主的通用模式——仅输出盘点与建议，无程序化关闭通道。",
                   "ℹ  {label}: generic mode for unrecognized hosts — inventory and advice only, no programmatic close channel."),
    "gen_note_2": ("   关闭请使用宿主自带的技能启用/禁用开关，并逐条人工确认；「需人工确认」档的存在\n   正是因为自动挂载 / 定时任务 / Hook / 专家组件的用量在日志里不可见。\n",
                   "   Use the host's own enable/disable toggles and confirm each item manually. The \"manual review\" bucket\n   exists precisely because automation/hook/expert usage is invisible to logs.\n"),
    # --- report(): 汇总表 ---
    "hdr_platform": ("平台", "Platform"),
    "hdr_total": ("技能总数", "Skills total"),
    "total_note": ("（市场安装 {m} / 自建或自改 {o}）", "(market-installed {m} / self-built or modified {o})"),
    "hdr_keep": ("有使用记录", "Used (has records)"),
    "hdr_prot": ("受保护（不关）", "Protected (no auto-close)"),
    "hdr_cleanup": ("可关闭候选", "Close candidates"),
    "hdr_cleanup_note": ("（仍须人工逐条确认）", "(per-item human confirmation still required)"),
    "hdr_review": ("需人工确认", "Manual review"),
    "hdr_footprint": ("清单占用", "Manifest footprint"),
    "footprint": ("{c} 字符  ≈ {t:.0f} tokens / 每轮对话", "{c} chars  ≈ {t:.0f} tokens / conversation turn"),
    "tbl_dir": ("目录", "Directory"), "tbl_lines": ("行", "ln"), "tbl_src": ("来源", "Src"),
    "tbl_kb": ("KB", "KB"),
    "tbl_mtime": ("最后改", "Modified"), "tbl_uses": ("用", "Use"), "tbl_lastused": ("最后用", "Last used"),
    "src_market": ("市场", "market"), "src_self": ("自建", "self"),
    # --- report(): 四档块 ---
    "cleanup_hdr": ("🔻 可关闭候选：无使用记录 且 超过 {d} 天没改过（{n} 个）",
                    "🔻 Close candidates: no usage record and untouched for over {d} days ({n})"),
    "cleanup_warn": ("   ⚠ 仅建议，未经你显式确认不得关闭；先确认无关键词/专家触发依赖。",
                     "   ⚠ Advice only — nothing is closed without your explicit confirmation; verify no trigger/expert dependency first."),
    "unit_lines": (" 行", " ln"),
    "review_hdr": ("⚠️  需人工确认：无使用记录但（近期改过 或 无遥测 或 平台不可关）（{n} 个）—— 别急着关",
                   "⚠️  Manual review: no usage record but recently modified / no telemetry / platform cannot close ({n}) — do not rush"),
    "prot_hdr": ("🔒 受保护（永不自动建议关闭，须人工明确介入）：{n} 个",
                 "🔒 Protected (never auto-suggested for closing; explicit human action required): {n}"),
    "reason_refs": ("被引用锁定：{n} 处（{kinds}）", "reference-locked: {n} hit(s) ({kinds})"),
    "reason_safety": ("安全/审计类", "safety/audit class"),
    "reason_marked": ("显式标记 protected / 自保护", "explicitly marked protected / self-protecting"),
    # --- report(): 影响预览 / 重复 ---
    "impact_hdr": ("🛰  影响预览（被引用锁定技能的依赖链路，{n} 个技能）：",
                   "🛰  Impact preview (dependency chains of reference-locked skills, {n}):"),
    "impact_row": ("关闭将断掉 {n} 处引用：", "closing breaks {n} reference(s):"),
    "impact_hits": ("命中: {t}", "hits: {t}"),
    "impact_hint": ("  （单技能深查：--impact <名称>；本扫描只覆盖可发现的配置根，T2 自动挂载不在此列）",
                    "  (single-skill deep dive: --impact <name>; scanning covers discoverable config roots only, T2 auto-mounting excluded)"),
    "dup_hdr": ("🔁 疑似重复/跨区（共 {n} 项）：", "🔁 Suspected duplicates/cross-region ({n} total):"),
    "dup_genuine": ("  · ⚠ 真·多份激活：{d} （{n} 个区域均激活）", "  · ⚠ multiple active copies: {d} (active in {n} regions)"),
    "dup_overlap": ("  · 激活+禁用副本：{d} （跨 {n} 区）", "  · active + disabled copy: {d} (across {n} regions)"),
    "dup_name": ("  · 同名：{n}  ←  {l}", "  · same name: {n}  ←  {l}"),
    # --- print_impact ---
    "imp_notfound": ("[impact] 未找到名称或目录含「{q}」的技能。", '[impact] no skill whose name or dir contains "{q}".'),
    "imp_locked": ("\n== {d}（{n}）— 🔒 被引用锁定，关闭将断掉 {m} 处引用：",
                   "\n== {d} ({n}) — 🔒 reference-locked; closing breaks {m} reference(s):"),
    "imp_hits": ("    命中: {t}", "    hits: {t}"),
    "imp_why_prot": ("受保护（非引用原因）", "protected (non-reference reason)"),
    "imp_why_norefs": ("未发现引用", "no references found"),
    "imp_nomatch_1": ("  （本工具能扫描的配置根里没有它；但 T2 自动挂载与描述性关键词引用扫不到，",
                      "  (not found in any config root this tool can scan; T2 auto-mounting and descriptive keyword"),
    "imp_nomatch_2": ("   关闭前仍请人工确认。）", "   references are invisible — still confirm manually before closing.)"),
    "imp_none_locked": ("\n[impact] 以上技能均未被自动化/Hook/路由/插件配置引用（就本工具可扫描的根而言）。",
                        "\n[impact] none of the above are referenced by automation/hook/routing/plugin configs (within scannable roots)."),
    # --- render_overrides ---
    "ov_generic_1": ("// 通用模式（未识别宿主）没有程序化关闭通道，--overrides 不适用。",
                     "// Generic mode (unrecognized host) has no programmatic close channel; --overrides does not apply."),
    "ov_generic_2": ("//    请直接看报告的「可关闭候选 / 需人工确认」，再到宿主自带开关里手动处理。",
                     "//    See the report's \"close candidates / manual review\" and use the host's own toggles."),
    "ov_conn_1": ("// ⚠️ {label} 关闭通道为连接器/UI，本工具不产出任何关闭动作或 WB 骨架。",
                  "// ⚠️ {label} closes via connector/UI; this tool emits no close actions or WB skeleton."),
    "ov_conn_2": ("//    以下仅为「可关闭候选 / 需确认」清单，请在客户端确认后手动关闭。\n",
                  "//    The list below is candidates/review only — close them manually in the client.\n"),
    "ov_gap": ("// ⚠️ [遥测缺口] 无可用用量日志：不列出可关闭候选（避免误杀）。\n",
               "// ⚠️ [Telemetry gap] no usable usage log: close candidates withheld (avoid false kills).\n"),
    "ov_gap_fs": ("// ⚠️ [遥测缺口] 无可用用量日志：下方不输出任何 off 项（避免误杀）。",
                  "// ⚠️ [Telemetry gap] no usable usage log: no \"off\" entries below (avoid false kills)."),
    "ov_gap_fs_2": ("//    请人工确认每个技能是否仍被关键词/专家/自动化间接使用后再处理。\n",
                    "//    Please manually confirm each skill is not indirectly used via keywords/experts/automations first.\n"),
    "ov_conn_cand": ("//   🔻 候选：{d}", "//   🔻 candidate: {d}"),
    "ov_conn_review": ("//   ⚠ 待确认：{d}", "//   ⚠ review: {d}"),
    "ov_conn_prot": ("//   🔒 受保护：{l}", "//   🔒 protected: {l}"),
    "ov_draft_1": ("// 🔒 仅供起草：已剔除受保护技能与近期改过的技能。",
                   "// 🔒 Draft only: protected and recently-modified skills excluded."),
    "ov_draft_2": ("//    ⚠️ 默认不自动应用；`--apply --yes` 才在您同意下落地（WB 写入 skillOverrides）。",
                   "//    ⚠️ Never applied automatically; `--apply --yes` applies it with your consent (WB writes skillOverrides)."),
    "ov_review_n": ("\n// 以下 {n} 个「需人工确认」，本次未纳入 off：", "\n// {n} manual-review items, not included in off this time:"),
    "ov_review_row": ("//   {l}  (最后改 {m})", "//   {l}  (modified {m})"),
    "ov_prot_n": ("\n// 🔒 以下 {n} 个受保护，已被排除：", "\n// 🔒 {n} protected skills excluded:"),
    "ov_apply_ui": ("\n// ℹ️ {label} 的关闭需在客户端 UI 操作（技能列表「启用开关」/ 专家套件禁用），本工具暂不代执行。",
                    "\n// ℹ️ {label}: closing must be done in the client UI (enable toggle / expert-suite disable); this tool does not perform it."),
    # --- apply_wb ---
    "warn_no_log": ("[warn] 未找到用量日志（未配置用量日志路径）—— 按「无遥测」降级，不判任何技能为可关闭。",
                    "[warn] no usage log found (no path configured) -- degrading to no-telemetry; no skill will be marked closeable."),
    "warn_log_fail": ("[warn] 用量日志读取失败（{e}）—— 按「无遥测」降级，不判任何技能为可关闭。",
                      "[warn] usage log read failed ({e}) -- degrading to no-telemetry; no skill will be marked closeable."),
    "ap_none": ("[apply] 没有可关闭候选，无需操作。", "[apply] no close candidates; nothing to do."),
    "ap_dry": ("[dry-run] 未加 --yes，仅预览（不读写文件）：", "[dry-run] --yes missing; preview only (no files read or written):"),
    "ap_backup": ("[backup] settings.json -> {p}", "[backup] settings.json -> {p}"),
    "ap_new": ("[warn] 未找到 settings.json，将新建。", "[warn] settings.json not found; a new one will be created."),
    "ap_done_1": ("[applied] 已写入 {n} 个 off 到 skillOverrides（四态之一；", '[applied] wrote {n} "off" entries into skillOverrides (one of the four states;'),
    "ap_done_2": ("           确认后建议用 /skills 菜单按 Esc 落盘，便于统一查看）。",
                  "           afterwards use the /skills menu (press Esc to persist) to review them in one place)."),
    # --- resolve_agent ---
    "ra_unknown": ("未知平台：{a}（可选：workbuddy / qwen / baidu / generic / auto）",
                   "unknown platform: {a} (choose: workbuddy / qwen / baidu / generic / auto)"),
    "ra_baidu_missing": ("⚠️ 未找到 {label} 的本地技能目录（预期位于 {p}）。请用 --root 指向某个技能区域目录。",
                         "⚠️ {label} local skills dir not found (expected under {p}). Point --root at a skills region directory."),
    "ra_generic_1": ("通用模式：未识别出已知办公 Agent 的技能目录。",
                     "Generic mode: no known office-agent skills directory detected."),
    "ra_generic_2": ("请用 --root <技能目录> 指向要盘点的目录（约定：目录内每个子目录 = 一个技能，含 SKILL.md 即视为技能）。",
                     "Use --root <skills-dir> to point at the directory to inventory (each subdirectory containing a SKILL.md counts as one skill)."),
    "ra_generic_3": ("可选：--usage-log <路径> 提供用量日志；--refs <路径> 提供反向依赖扫描根。",
                     "Optional: --usage-log <path> for a usage log; --refs <path> for reverse-dependency scan roots."),
    "ra_unverified": ("⚠️ {label} 的本地技能目录尚未在本机验证，请用 --root 指定。",
                      "⚠️ {label} local skills dir not verified on this machine; specify --root."),
    "ra_qwen_missing": ("未检测到千问办公的技能目录（{p}）。若已安装，请用 --root 指向其 skills 目录。",
                        "QwenWork skills dir not found ({p}). If installed, point --root at its skills directory."),
    "ra_missing": ("找不到技能目录：{p}", "skills directory not found: {p}"),
    # --- main ---
    "note_no_refs": ("[note] {label} 未找到可扫描的反向依赖根（自动化/Hook/路由配置），反向依赖锁定暂不可用；如有关键词触发器引用，请人工确认。",
                     "[note] {label}: no scannable reverse-dependency roots (automations/hooks/routing); reference locking unavailable — confirm trigger dependencies manually."),
    "unused_hdr": ("== 需关注（无使用记录）==", "== Needs attention (no usage records) =="),
    "unused_cannot": ("\n⚠️ {label} 不支持程序化关闭；以上仅作人工审查/手动移除参考。",
                      "\n⚠️ {label} does not support programmatic closing; the list above is for manual review/removal only."),
}


def plabel(profile: dict) -> str:
    """平台显示名：en 模式取 label_en（缺省回落 label）。"""
    if LANG == "en":
        return profile.get("label_en") or profile["label"]
    return profile["label"]


def M(key: str, **kw) -> str:
    """按当前 LANG 取文案；zh/en 双语，缺键回退 zh。"""
    entry = S[key]
    tmpl = entry[1] if LANG == "en" else entry[0]
    return tmpl.format(**kw) if kw else tmpl


def print_impact(rows: list, query: str) -> None:
    """--impact <名称>：单技能影响深查（全量列出、不截断），供关闭前逐条审阅（调研护栏 #4/#8）。"""
    q = query.lower()
    matched = [r for r in rows if q in r["dir"].lower() or q in r["name"].lower()]
    if not matched:
        print(M("imp_notfound", q=query), file=sys.stderr)
        return
    any_locked = False
    for r in sorted(matched, key=lambda x: x["dir"]):
        refs = r.get("referenced_by") or []
        if refs:
            any_locked = True
            print(M("imp_locked", d=r["dir"], n=r["name"], m=len(refs)))
            for e in refs:
                print(f"  · [{e['kind']}] {e['path']}")
                print(M("imp_hits", t=", ".join(e["terms"])))
        else:
            why = M("imp_why_prot") if r.get("protected") else M("imp_why_norefs")
            print(f"\n== {r['dir']}（{r['name']}）— {why} ==")
            if refs is not None and not refs and not r.get("protected"):
                print(M("imp_nomatch_1"))
                print(M("imp_nomatch_2"))
    if not any_locked:
        print(M("imp_none_locked"), file=sys.stderr)


def report(rows: list, telemetry: bool, profile: dict) -> None:
    total_chars = sum(len(r["name"]) + len(r["desc"]) for r in rows)
    total_tokens = sum(_est_tokens(r["name"] + r["desc"]) for r in rows)
    market = sum(1 for r in rows if r["from_market"])
    b = classify(rows, telemetry, profile["can_close"])

    if b["telemetry_gap"]:
        print(M("tel_gap_1"))
        print(M("tel_gap_2"))
        print(M("tel_gap_3"))
    elif telemetry:
        # 调研 §2/§3：遥测只覆盖 T1 显式调用；「call_depth 覆盖 T5」本身属推断（§8 已标注）。
        # 有日志 ≠ 安全，这句必须在有遥测的平台上也常显。
        print(M("tel_scope_1"))
        print(M("tel_scope_2"))
        print(M("tel_scope_3"))

    if profile.get("close_kind") == "connector":
        print(M("conn_note", label=plabel(profile)))

    if profile.get("close_kind") == "none":
        print(M("gen_note_1", label=plabel(profile)))
        print(M("gen_note_2"))

    print(f"{M('hdr_platform'):<28}{plabel(profile)}")
    print(f"{M('hdr_total'):<28}{len(rows)}    {M('total_note', m=market, o=len(rows) - market)}")
    print(f"{M('hdr_keep'):<28}{len(b['keep'])}")
    print(f"{M('hdr_prot'):<28}{len(b['protected'])}")
    print(f"{M('hdr_cleanup'):<28}{len(b['cleanup'])}    {M('hdr_cleanup_note')}")
    print(f"{M('hdr_review'):<28}{len(b['review'])}")
    print(f"{'':<28}" + M("footprint", c=total_chars, t=total_tokens))
    print()

    print(f"{_pad(M('tbl_dir'),36)}{'':<2}{M('tbl_lines'):>5}{M('tbl_kb'):>8}{M('tbl_src'):>8}{M('tbl_mtime'):>11}{M('tbl_uses'):>5}{M('tbl_lastused'):>11}")
    print("-" * 88)
    for r in sorted(rows, key=lambda x: -(x["mtime"] or 0)):
        src = M("src_market") if r["from_market"] else M("src_self")
        tag = "🔒" if r["protected"] else ("⚠" if r in b["review"] else "")
        print(f"{_pad(r['dir'],36)}{tag:<2}{r['lines']:>5}{r['kb']:>8}{src:>8}"
              f"{r['last_modified']:>11}{r['uses']:>4}{r['last_used'] or '—':>11}")

    if b["cleanup"]:
        print()
        print(M("cleanup_hdr", d=RECENT_DAYS, n=len(b["cleanup"])))
        print(M("cleanup_warn"))
        for r in sorted(b["cleanup"], key=lambda x: -x["lines"]):
            print(f"  {_pad(r['dir'],40)}{r['lines']:>5}{M('unit_lines')}   {r['last_modified']}")

    if b["review"]:
        print()
        print(M("review_hdr", n=len(b["review"])))
        for r in sorted(b["review"], key=lambda x: -x["mtime"]):
            print(f"  {_pad(r['dir'],40)}{r['lines']:>5}{M('unit_lines')}   {r['last_modified']}")

    if b["protected"]:
        print()
        print(M("prot_hdr", n=len(b["protected"])))
        for r in sorted(b["protected"], key=lambda x: x["dir"]):
            refs = r.get("referenced_by") or []
            if refs:
                kinds = ", ".join(sorted({e["kind"] for e in refs}))
                reason = M("reason_refs", n=len(refs), kinds=kinds)
            elif r["safety_hit"]:
                reason = M("reason_safety")
            else:
                reason = M("reason_marked")
            print(f"  {_pad(r['dir'],40)}（{reason}）")

    # 影响预览（调研护栏 #4，§7 唯一 ⚠️ 项）：关闭某技能将断掉哪些链路——结构化逐条映射
    locked = [r for r in rows if r.get("referenced_by")]
    if locked:
        print()
        print(M("impact_hdr", n=len(locked)))
        for r in sorted(locked, key=lambda x: x["dir"]):
            refs = r["referenced_by"]
            print(f"  ▸ {_pad(r['dir'], 36)} {M('impact_row', n=len(refs))}")
            for e in refs:
                print(f"      · [{e['kind']}] {e['path']}")
                print(f"        {M('impact_hits', t=', '.join(e['terms']))}")
        print(M("impact_hint"))

    # P0-1：疑似重复/冗余技能
    #   (a) 同一 leaf 在 ≥2 个「非禁用」区域都激活 → 真·多份加载（重点）；
    #   (b) 同一 leaf 跨区但仅 1 个激活（多为「激活 + 禁用副本」）→ 低优先提示；
    #   (c) 不同 leaf 但归一化名称相同 → 疑似重名技能。
    genuine = [r for r in rows if r.get("region_active_count", 1) >= 2]
    overlap = [r for r in rows if r.get("region_count", 1) > 1
               and r.get("region_active_count", 1) < 2]
    name_dups = find_duplicates(rows)
    if genuine or overlap or name_dups:
        print()
        print(M("dup_hdr", n=len(genuine) + len(overlap) + len(name_dups)))
        for r in sorted(genuine, key=lambda x: x["dir"]):
            print(M("dup_genuine", d=_pad(r["dir"], 28), n=r["region_active_count"]))
        for r in sorted(overlap, key=lambda x: x["dir"]):
            print(M("dup_overlap", d=_pad(r["dir"], 24), n=r["region_count"]))
        for name, grp in sorted(name_dups.items()):
            locs = ", ".join(_pad(r["dir"], 26) for r in grp)
            print(M("dup_name", n=name, l=locs))


def render_overrides(rows: list, telemetry: bool, profile: dict, do_apply: bool, yes: bool) -> None:
    b = classify(rows, telemetry, profile["can_close"])

    # 通用档（generic）：未知宿主没有关闭通道，--overrides 不适用——显式拦截而非落进 filesystem 分支
    if profile.get("close_kind") == "none":
        print(M("ov_generic_1"))
        print(M("ov_generic_2"))
        return

    # 连接器平台（千问/百度）：关闭在客户端 UI，不产出 WB skillOverrides 骨架
    if profile.get("close_kind") == "connector":
        print(M("ov_conn_1", label=plabel(profile)))
        print(M("ov_conn_2"))
        if b["telemetry_gap"]:
            print(M("ov_gap"))
        for r in sorted(b["cleanup"], key=lambda x: x["dir"]):
            print(M("ov_conn_cand", d=r["dir"]))
        for r in sorted(b["review"], key=lambda x: x["dir"]):
            print(M("ov_conn_review", d=r["dir"]))
        for r in sorted(b["protected"], key=lambda x: x["dir"]):
            print(M("ov_conn_prot", l=r["leaf"]))
        return

    # 可关平台（filesystem，WorkBuddy）：输出关闭草稿；--apply 才在同意下落地
    if b["telemetry_gap"]:
        print(M("ov_gap_fs"))
        print(M("ov_gap_fs_2"))
    print(M("ov_draft_1"))
    print(M("ov_draft_2"))
    print('"skillOverrides": {')
    for r in sorted(b["cleanup"], key=lambda x: x["dir"]):
        print(f'  "{r["leaf"]}": "off",')
    print('}')
    if b["review"]:
        print(M("ov_review_n", n=len(b["review"])))
        for r in sorted(b["review"], key=lambda x: x["dir"]):
            print(M("ov_review_row", l=r["leaf"], m=r["last_modified"]))
    if b["protected"]:
        print(M("ov_prot_n", n=len(b["protected"])))
        for r in sorted(b["protected"], key=lambda x: x["dir"]):
            print(f"//   {r['leaf']}")

    if do_apply:
        if profile["close_kind"] == "filesystem":
            apply_wb([r["leaf"] for r in b["cleanup"]], yes)
        else:
            print(M("ov_apply_ui", label=plabel(profile)))


def backup_settings() -> pathlib.Path:
    """动刀前自动备份 settings.json（audit-hermes 风）。返回备份路径。"""
    settings = HOME / ".workbuddy" / "settings.json"
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = settings.with_name(settings.name + f".bak.{ts}")
    if settings.exists():
        shutil.copy2(settings, bak)
    return bak, settings


def apply_wb(leaves: list, yes: bool) -> None:
    """在你显式同意（--yes）下，把可关闭候选写入 WB 的 skillOverrides（off）。先自动备份。

    dry-run（未加 --yes）只预览，不读写任何文件。
    """
    if not leaves:
        print(M("ap_none"))
        return
    settings = HOME / ".workbuddy" / "settings.json"
    if not yes:
        print(M("ap_dry"))
        print(json.dumps({"skillOverrides": {l: "off" for l in leaves}}, ensure_ascii=False, indent=2))
        return
    # 仅在真正同意时才备份 + 写入
    bak, _ = backup_settings()
    if settings.exists():
        print(M("ap_backup", p=bak))
    else:
        print(M("ap_new"))
    data = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
    ov = data.get("skillOverrides") or {}
    for lf in leaves:
        ov[lf] = "off"
    data["skillOverrides"] = ov
    settings.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(M("ap_done_1", n=len(leaves)))
    print(M("ap_done_2"))


def resolve_agent(agent_arg: str, root_arg: str, usage_arg: str):
    """解析平台档位，返回 (profile, roots, usage_path, agent_key)。

    roots: list of {"path","label","disabled"}；百度为自动探测的多根。
    目录不存在 / 无法探测时返回 (None, None, None, None) 让 main 友好退出。
    """
    agent = agent_arg
    if agent == "auto":
        if SKILLS_DIR.exists():
            agent = "workbuddy"
        elif (HOME / ".qwenworkcn" / "skills").exists():
            agent = "qwen"
        else:
            agent = "generic"   # 未知宿主（天禧沙箱等）：回落通用档，不再硬套 workbuddy 路径
    profile = PLATFORMS.get(agent)
    if profile is None:
        print(M("ra_unknown", a=agent), file=sys.stderr)
        return None, None, None, None

    # 百度：多根自动探测（或 --root 显式指定）
    if profile.get("multi_root"):
        roots = detect_baidu_roots(root_arg)
        if not roots:
            print(M("ra_baidu_missing", label=profile["label"],
                    p=APPDATA / 'qianfan-desktop-app' / 'qianfan_desk_xdg'), file=sys.stderr)
            return None, None, None, None
        return profile, roots, None, agent

    # 单根平台（workbuddy / qwen）：skills_root 固定为单元素列表
    if root_arg:
        roots = [{"path": pathlib.Path(root_arg), "label": "", "disabled": False}]
    else:
        sr = profile["skills_root"]
        if not sr:
            if agent == "generic":
                print(M("ra_generic_1"), file=sys.stderr)
                print(M("ra_generic_2"), file=sys.stderr)
                print(M("ra_generic_3"), file=sys.stderr)
            else:
                print(M("ra_unverified", label=plabel(profile)), file=sys.stderr)
            return None, None, None, None
        roots = [{"path": p, "label": "", "disabled": False} for p in sr]
    missing = [r for r in roots if not r["path"].is_dir()]
    if missing:
        for r in missing:
            if agent == "qwen":
                print(M("ra_qwen_missing", p=r["path"]), file=sys.stderr)
            else:
                print(M("ra_missing", p=r["path"]), file=sys.stderr)
        return None, None, None, None
    usage = pathlib.Path(usage_arg) if usage_arg else profile["usage_log"]
    return profile, roots, usage, agent


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Office-agent skill inventory & health check 办公型 Agent 技能库盘点与效能体检")
    ap.add_argument("--agent", default="auto",
                    choices=["workbuddy", "qwen", "baidu", "generic", "auto"],
                    help="Target platform (determines close channel) 目标平台档位；auto 探测失败回落 generic")
    ap.add_argument("--root", default="",
                    help="Skills directory (overrides platform default) 技能目录")
    ap.add_argument("--usage-log", default="",
                    help="Usage log path (no log -> telemetry-gap degradation) 用量日志路径")
    ap.add_argument("--unused", action="store_true",
                    help="List only skills without usage records 只列出无使用记录的技能")
    ap.add_argument("--json", action="store_true",
                    help="Machine-readable JSON output 机器可读 JSON（键恒为英文）")
    ap.add_argument("--overrides", action="store_true",
                    help="Draft a skillOverrides 'off' skeleton (advice only) 起草可关闭清单（草稿，须人工确认）")
    ap.add_argument("--apply", action="store_true",
                    help="Apply the draft with your consent (can_close platforms only; requires --yes) "
                         "落地关闭（仅可关平台，须配 --yes；先自动备份）")
    ap.add_argument("--yes", action="store_true",
                    help="Confirm --apply (otherwise dry-run preview) 确认执行 --apply（否则仅预览）")
    ap.add_argument("--protect", default="",
                    help="Extra protected skill names (comma-separated) 追加受保护技能名")
    ap.add_argument("--protect-file", default="",
                    help="Read protected names from file (one per line) 从文件读取受保护技能名")
    ap.add_argument("--no-safety-heuristic", action="store_true",
                    help="Disable the safety/audit keyword heuristic (on by default) 关闭安全类关键词启发式")
    ap.add_argument("--refs", default="",
                    help="Extra reverse-dependency scan roots (comma-separated) 额外反向依赖扫描根")
    ap.add_argument("--impact", metavar="NAME", default=None,
                    help="Impact preview for one skill (untruncated) 单技能影响深查")
    ap.add_argument("--no-ref-scan", action="store_true",
                    help="Disable reverse-dependency scanning (on by default) 关闭反向依赖扫描")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"],
                    help="Report language (default: zh; JSON keys are always English) 报告语言")
    args = ap.parse_args()

    global LANG
    LANG = args.lang

    profile, roots, usage_path, agent_key = resolve_agent(args.agent, args.root, args.usage_log)
    if roots is None:
        return 2

    # 合并受保护清单
    extra = {norm(x) for x in args.protect.split(",") if x.strip()}
    if args.protect_file:
        pf = pathlib.Path(args.protect_file)
        if pf.is_file():
            extra |= {norm(l) for l in pf.read_text(encoding="utf-8").splitlines() if l.strip()}
    for leaf in extra:
        PROTECTED_LEAVES.add(leaf)
    if args.no_safety_heuristic:
        global SAFETY_KEYWORDS
        SAFETY_KEYWORDS = ()  # 关闭启发式

    # 千问：用中心化 lock 文件的 source 字段判定「来自市场」（P2-5），并取反向依赖扫描根（P2-7）
    market_resolver = None
    qwen_ref = []
    if agent_key == "qwen" and roots:
        market_dirs, qwen_ref = _qwen_extra(roots[0]["path"].parent)
        if market_dirs is not None:
            market_resolver = lambda sd: sd in market_dirs or (sd / "_meta.json").exists()

    rows = scan(roots, market_resolver)

    # 反向依赖扫描（P0 增强）：锁定被自动化 / Hook / 专家·连接器 / 路由层引用的技能
    if not args.no_ref_scan:
        ref_roots = [str(p) for p in DEFAULT_REF_ROOTS if pathlib.Path(p).exists()]  # WorkBuddy 默认根
        if agent_key == "qwen":
            ref_roots += qwen_ref          # 千问路由状态 / 插件 config 等
        if args.refs:
            ref_roots += [x for x in args.refs.split(",") if x.strip()]
        if not ref_roots and agent_key != "workbuddy":
            print(M("note_no_refs", label=plabel(profile)), file=sys.stderr)
        if ref_roots:
            referenced = scan_references(rows, ref_roots)
            for r in rows:
                rb = referenced.get(r["dir"])
                if rb:
                    r["referenced_by"] = rb
                    r["locked"] = True

    if args.impact:
        print_impact(rows, args.impact)
        return 0

    usage, telemetry = load_usage(usage_path, profile.get("usage_adapter"))
    attach_usage(rows, usage)

    if args.json:
        b = classify(rows, telemetry, profile["can_close"])
        print(json.dumps({
            "agent": profile["label"],
            "can_close": profile["can_close"],
            "rows": rows,
            "buckets": {k: [r["dir"] for r in v] for k, v in b.items() if isinstance(v, list)},
            "telemetry_gap": b["telemetry_gap"],
            "telemetry_scope": ("none" if b["telemetry_gap"] else "t1-only"),
            "cannot_close": b["cannot_close"],
        }, ensure_ascii=False, indent=2))
        return 0

    if args.overrides:
        render_overrides(rows, telemetry, profile, args.apply, args.yes)
        return 0

    if args.unused:
        b = classify(rows, telemetry, profile["can_close"])
        print(M("unused_hdr"))
        for r in sorted(b["review"] + b["cleanup"], key=lambda x: -x["lines"]):
            print(f"{r['dir']:<40}{r['lines']:>5}{M('unit_lines')}   {r['last_modified']}")
        if b["cannot_close"]:
            print(M("unused_cannot", label=plabel(profile)))
        return 0

    report(rows, telemetry, profile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
