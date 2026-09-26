#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill-inventory —— 跨平台 Agent 技能库盘点与效能体检。

    python skill_inventory.py                 # 完整表格 + 三档分类
    python skill_inventory.py --root DIR       # 盘点任意技能目录（跨平台）
    python skill_inventory.py --unused          # 只看无使用记录的
    python skill_inventory.py --json            # 机器可读
    python skill_inventory.py --overrides       # 起草可关闭清单（仅建议，需人工确认）

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
  2. 本工具**只输出建议，绝不自动改写 settings.json 或禁用任何技能**。
     `--overrides` 产物也仅是「草稿」，须逐条人工确认后再用。
  3. 遥测缺口降级：当平台无用量日志 / 日志读取失败时，**全库不判为可关闭**，
     只给「需人工确认」档，并显式告警「无法确认冷技能」。
  4. 反向依赖扫描：判「可关闭」前，先扫自动化 / Hook / 专家·连接器 / 子 agent 的定义文件，
     凡被引用的技能**锁定**进受保护桶——堵住「被关键词触发器或专家组件间接调用却无使用日志」的误杀。

零依赖：自带最小 frontmatter 解析（支持 key: value 与 key: > 块）。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
import sys
import time

try:                      # 有 PyYAML 就用真解析器：内置解析器对含空行的折叠块会截断
    import yaml            # type: ignore
except ImportError:       # 零依赖环境下回退
    yaml = None

HOME = pathlib.Path.home()
SKILLS_DIR = HOME / ".workbuddy" / "skills"
USAGE_LOG = HOME / ".workbuddy" / "usage-log.json"

# 30 天内改动过 = 视为「可能新建/在用」。usage-log 对新建技能必然没有记录，
# 不设这道闸就会把刚写的技能也判成「该关」。
RECENT_DAYS = 30

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


def load_usage(path: pathlib.Path) -> tuple:
    """返回 (usage_dict, telemetry_available: bool)。

    P1 已修复：原先静默吞异常返回 {}，会导致日志一旦损坏/轮换，全库无声变成
    「未使用」→ 整套关闭建议 100% 错误且无人察觉。现在改为 stderr 显式告警，
    并返回 available=False，让上层走「遥测缺口降级」分支（不判死）。
    """
    if not path.exists():
        print(f"[warn] 未找到用量日志：{path} —— 按「无遥测」降级，不判任何技能为可关闭。",
              file=sys.stderr)
        return {}, False
    try:
        return (json.loads(path.read_text(encoding="utf-8")).get("skills") or {}), True
    except Exception as e:  # noqa: BLE001 - 我们就是要兜住一切解析错误并告警
        print(f"[warn] 用量日志读取失败（{e}）—— 按「无遥测」降级，不判任何技能为可关闭。",
              file=sys.stderr)
        return {}, False


def scan(root: pathlib.Path) -> list:
    rows = []
    for p in sorted(root.rglob("SKILL.md")):
        if ".git" in p.parts:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        files = [f for f in p.parent.rglob("*") if f.is_file() and ".git" not in f.parts]
        total = sum(f.stat().st_size for f in files)
        mtime = max((f.stat().st_mtime for f in files), default=0)
        leaf = p.parent.name
        name = fm.get("name") or leaf
        # 受保护判定（P0）：自保护清单 ∪ frontmatter 显式标记 ∪ 安全/审计类关键词启发式
        safety_hit = any(k in norm(name) or k in norm(leaf) for k in SAFETY_KEYWORDS)
        protected = (
            norm(leaf) in {norm(x) for x in PROTECTED_LEAVES}
            or str(fm.get("protected", "")).strip().lower() in ("true", "1", "yes", "y", "protected")
            or str(fm.get("critical", "")).strip().lower() in ("true", "1", "yes")
            or safety_hit
        )
        rows.append({
            "dir": p.parent.relative_to(root).as_posix(),
            "leaf": leaf,
            "name": name,
            "desc": fm.get("description") or "",
            "from_market": (p.parent / "_meta.json").exists(),
            "lines": len(text.splitlines()),
            "files": len(files),
            "kb": round(total / 1024, 1),
            "last_modified": _dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d") if mtime else "?",
            "mtime": mtime,
            "protected": protected,
            "safety_hit": safety_hit,
            "locked": False,
            "referenced_by": [],
        })
    return rows


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
        r["uses"] = len(best[1].get("recentDates", [])) if best else 0


def scan_references(rows: list, ref_roots: list) -> dict:
    """反向依赖扫描（P0 增强）：在自动化 / Hook / 专家·连接器 / 子 agent 定义里找对本技能的引用。

    用户可能从不在对话里明说要调某 skill，而是被「关键词触发器 / 自动化任务 / Hook /
    专家·连接器组件」间接调用——这些在用量日志里**完全无痕**。直接扫描这些定义文件，
    凡被引用即**锁定**，绝不作为「可关闭」候选。思路借鉴 Hermes skill-drift-check 的 pre-flight 校验。
    """
    search = {}
    for r in rows:
        for key in (r["leaf"], r["name"]):
            nk = norm(key)
            if nk:
                search[nk] = r
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
        term: re.compile(r"(?<![\w@/-])" + re.escape(term) + r"(?![\w@/-])")
        for term in search
    }
    referenced = {}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            continue
        for term, pat in patterns.items():
            if pat.search(text):
                referenced.setdefault(search[term]["dir"], []).append(f.name)
    return referenced


def classify(rows: list, telemetry: bool) -> dict:
    """三档分类 + 受保护桶。

    - protected：受保护清单命中 → 永远不关，需人工介入。
    - cleanup  ：无使用记录 且 超过 RECENT_DAYS 天没改过 → 候选可关闭（仍需人工确认）。
    - review   ：其余「无使用记录但近期改过 / 或平台无遥测」→ 需人工确认，不可自动关。
    - keep    ：有使用记录。

    🔒 P0 关键：当 telemetry=False（无遥测/读取失败），cleanup 桶恒为空，
       所有无记录技能落入 review，并打「遥测缺口」标记。
    """
    now = time.time()
    buckets = {"protected": [], "keep": [], "cleanup": [], "review": [], "telemetry_gap": not telemetry}
    for r in rows:
        if r["protected"] or r.get("locked"):
            buckets["protected"].append(r)
            continue
        if r["used_as"]:
            buckets["keep"].append(r)
            continue
        recent = (now - (r["mtime"] or 0)) < RECENT_DAYS * 86400
        if telemetry and not recent:
            buckets["cleanup"].append(r)
        else:
            # 无遥测、或近期改过 → 都只能算「需人工确认」，绝不自动判死
            buckets["review"].append(r)
    return buckets


def report(rows: list, telemetry: bool) -> None:
    total_chars = sum(len(r["name"]) + len(r["desc"]) for r in rows)
    market = sum(1 for r in rows if r["from_market"])
    b = classify(rows, telemetry)

    if b["telemetry_gap"]:
        print("⚠️  [遥测缺口] 本目录/平台无可用用量日志，无法确认冷技能。")
        print("    以下结论只基于「最后修改时间」，不可作为关闭依据——请人工确认每个技能是否")
        print("    仍被「关键词触发器 / 自动化 / 专家·连接器组件」间接使用。\n")

    print(f"技能总数        {len(rows)}    （市场安装 {market} / 自建或自改 {len(rows) - market}）")
    print(f"有使用记录      {len(b['keep'])}")
    print(f"受保护（不关）  {len(b['protected'])}")
    print(f"可关闭候选      {len(b['cleanup'])}    （仍须人工逐条确认）")
    print(f"需人工确认      {len(b['review'])}")
    print(f"清单占用        {total_chars} 字符  ≈ {total_chars / 3.2:.0f} tokens / 每轮对话")
    print()

    print(f"{'目录':<36}{'':<2}{'行':>5}{'KB':>8}{'来源':>6}{'最后改':>11}{'用':>4}{'最后用':>11}")
    print("-" * 84)
    for r in sorted(rows, key=lambda x: -(x["mtime"] or 0)):
        src = "市场" if r["from_market"] else "自建"
        tag = "🔒" if r["protected"] else ("⚠" if r in b["review"] else "")
        print(f"{r['dir']:<36}{tag:<2}{r['lines']:>5}{r['kb']:>8}{src:>6}"
              f"{r['last_modified']:>11}{r['uses']:>4}{r['last_used'] or '—':>11}")

    if b["cleanup"]:
        print()
        print(f"🔻 可关闭候选：无使用记录 且 超过 {RECENT_DAYS} 天没改过（{len(b['cleanup'])} 个）")
        print("   ⚠ 仅建议，未经你显式确认不得关闭；先确认无关键词/专家触发依赖。")
        for r in sorted(b["cleanup"], key=lambda x: -x["lines"]):
            print(f"  {r['dir']:<40}{r['lines']:>5} 行   {r['last_modified']}")

    if b["review"]:
        print()
        print(f"⚠️  需人工确认：无使用记录但（近期改过 或 无遥测）（{len(b['review'])} 个）—— 别急着关")
        for r in sorted(b["review"], key=lambda x: -x["mtime"]):
            print(f"  {r['dir']:<40}{r['lines']:>5} 行   {r['last_modified']}")

    if b["protected"]:
        print()
        print(f"🔒 受保护（永不自动建议关闭，须人工明确介入）：{len(b['protected'])} 个")
        for r in sorted(b["protected"], key=lambda x: x["dir"]):
            if r.get("referenced_by"):
                shown = ", ".join(sorted(set(r["referenced_by"]))[:3])
                reason = f"被引用锁定（{shown}）"
            elif r["safety_hit"]:
                reason = "安全/审计类"
            else:
                reason = "显式标记 protected / 自保护"
            print(f"  {r['dir']:<40}（{reason}）")


def render_overrides(rows: list, telemetry: bool) -> None:
    b = classify(rows, telemetry)
    if b["telemetry_gap"]:
        print("// ⚠️ [遥测缺口] 无可用用量日志：下方不输出任何 off 项（避免误杀）。")
        print("//    请人工确认每个技能是否仍被关键词/专家/自动化间接使用后再处理。\n")
    print("// 🔒 仅供起草：已剔除受保护技能与近期改过的技能。")
    print("//    ⚠️ 本工具绝不自动应用；请逐条人工确认以下技能确实无依赖后再关闭。")
    print("//    特别注意：未显式调用 ≠ 没用——可能被你设的关键词触发器、")
    print("//    自动化任务、或专家/连接器组件间接调用（用量日志抓不到）。")
    print('// 写入 ~/.workbuddy/settings.json 的 skillOverrides；确认后改用 /skills 菜单（按 Esc 落盘）。')
    print('"skillOverrides": {')
    for r in sorted(b["cleanup"], key=lambda x: x["dir"]):
        print(f'  "{r["leaf"]}": "off",')
    print('}')
    if b["review"]:
        print(f"\n// 以下 {len(b['review'])} 个「需人工确认」，本次未纳入 off：")
        for r in sorted(b["review"], key=lambda x: x["dir"]):
            print(f"//   {r['leaf']}  (最后改 {r['last_modified']})")
    if b["protected"]:
        print(f"\n// 🔒 以下 {len(b['protected'])} 个受保护，已被排除：")
        for r in sorted(b["protected"], key=lambda x: x["dir"]):
            print(f"//   {r['leaf']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="跨平台 Agent 技能库盘点与效能体检")
    ap.add_argument("--root", default=str(SKILLS_DIR), help="技能目录（默认 ~/.workbuddy/skills，可指向任意平台）")
    ap.add_argument("--usage-log", default=str(USAGE_LOG), help="用量日志路径（默认 ~/.workbuddy/usage-log.json；无则按无遥测降级）")
    ap.add_argument("--unused", action="store_true", help="只列出无使用记录的技能")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--overrides", action="store_true",
                    help="为「可关闭候选」生成 skillOverrides 的 off 骨架（草稿，须人工确认）")
    ap.add_argument("--protect", default="", help="追加受保护技能名（逗号分隔，leaf 或 name）")
    ap.add_argument("--protect-file", default="", help="从文件读取受保护技能名（每行一个）")
    ap.add_argument("--no-safety-heuristic", action="store_true",
                    help="关闭「安全/审计类」关键词启发式保护（默认开启）")
    ap.add_argument("--refs", default="", help="额外反向依赖扫描根（逗号分隔，文件或目录）")
    ap.add_argument("--no-ref-scan", action="store_true",
                    help="关闭反向依赖扫描（默认开启：扫自动化/Hook/设置里的技能引用并锁定）")
    args = ap.parse_args()

    root = pathlib.Path(args.root)
    if not root.is_dir():
        print(f"找不到技能目录：{root}", file=sys.stderr)
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

    rows = scan(root)

    # 反向依赖扫描（P0 增强）：锁定被自动化 / Hook / 专家·连接器引用的技能
    if not args.no_ref_scan:
        ref_roots = [str(p) for p in DEFAULT_REF_ROOTS if pathlib.Path(p).exists()]
        if args.refs:
            ref_roots += [x for x in args.refs.split(",") if x.strip()]
        if ref_roots:
            referenced = scan_references(rows, ref_roots)
            for r in rows:
                rb = referenced.get(r["dir"])
                if rb:
                    r["referenced_by"] = rb
                    r["locked"] = True

    usage, telemetry = load_usage(pathlib.Path(args.usage_log))
    attach_usage(rows, usage)

    if args.json:
        b = classify(rows, telemetry)
        print(json.dumps({
            "rows": rows,
            "buckets": {k: [r["dir"] for r in v] for k, v in b.items() if isinstance(v, list)},
            "telemetry_gap": b["telemetry_gap"],
        }, ensure_ascii=False, indent=2))
        return 0

    if args.overrides:
        render_overrides(rows, telemetry)
        return 0

    if args.unused:
        b = classify(rows, telemetry)
        print(f"== 可关闭候选（{len(b['cleanup'])} 个）==")
        for r in sorted(b["cleanup"], key=lambda x: -x["lines"]):
            print(f"{r['dir']:<40}{r['lines']:>5} 行   {r['last_modified']}")
        print(f"\n== 需人工确认（{len(b['review'])} 个）==")
        for r in sorted(b["review"], key=lambda x: -x["mtime"]):
            print(f"{r['dir']:<40}{r['lines']:>5} 行   {r['last_modified']}")
        if b["protected"]:
            print(f"\n== 受保护（{len(b['protected'])} 个，已排除）==")
            for r in sorted(b["protected"], key=lambda x: x["dir"]):
                print(f"{r['dir']:<40}")
        return 0

    report(rows, telemetry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
