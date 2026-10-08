#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SKILL.md 格式自检（Claude 渐进式披露加载规则）

用法：python check_skill_md.py [SKILL.md 路径]
零依赖；若环境有 PyYAML 则做 YAML 解析校验，没有则只做文本级检查。
判据来源见 deliverables/gstack/acceptance-and-optimization-2026-10-08.md 第五节。
"""
from __future__ import annotations

import pathlib
import re
import sys

BUDGET = 8000          # SKILL.md 正文 token 上限
CUSHION = 5000         # 为上下文压缩预留的余量
CORE_FRONT = 3000      # 核心规则必须落在的 token 位置
MAX_SECTION_SHARE = 0.15


def est_tokens(s: str) -> float:
    """与脚本内同一口径估算：CJK ÷1.6，其余 ÷4。"""
    cjk = sum(1 for ch in s if ord(ch) > 0x2E80)
    return cjk / 1.6 + (len(s) - cjk) / 4.0


def split_sections(lines: list) -> list:
    """返回 [(标题, 行号, 该节 token 数)]，含开头 frontmatter 作为 (fm, 0, n)。"""
    marks = [(i, l) for i, l in enumerate(lines) if l.startswith("## ")]
    out = [("（frontmatter）", 0, est_tokens("\n".join(lines[:marks[0][0]] if marks else lines)))]
    for n, (i, l) in enumerate(marks):
        end = marks[n + 1][0] if n + 1 < len(marks) else len(lines)
        out.append((l.strip("# ").strip(), i + 1, est_tokens("\n".join(lines[i:end]))))
    return out


def main() -> int:
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "SKILL.md")
    if not path.exists():
        print(f"[E-ROOT] 找不到 {path}")
        return 2
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # YAML（可选）
    fm: dict = {}
    if text.startswith("---"):
        try:
            import yaml
            fm = yaml.safe_load(text.split("---")[1]) or {}
        except ImportError:
            print("[note] 未装 PyYAML，跳过 YAML 校验（文本级检查照常）")
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] frontmatter 不是合法 YAML：{e}")
            return 1

    desc = str(fm.get("description", ""))
    allowed = str(fm.get("allowed-tools", ""))
    tk_total = est_tokens(text)
    tk_body = tk_total - est_tokens("\n".join(lines[:_fm_end(lines)]))

    # 前 CORE_FRONT token 落在哪一节（取该位置所属的最后一节标题）
    acc, cut_line, cut_sec = 0.0, 1, "（frontmatter）"
    for i, l in enumerate(lines, 1):
        acc += est_tokens(l)
        if l.startswith("## "):
            cut_sec = l.strip("# ").strip()
        if acc >= CORE_FRONT:
            cut_line = i
            break

    # 单节占比只看正文（frontmatter 属 L1 常驻层，单独算预算）
    secs = [(t, k) for t, _, k in split_sections(lines)][1:]
    worst = max(secs, key=lambda kv: kv[1]) if secs else ("-", 0.0)
    worst_share = worst[1] / max(tk_body, 1)

    # (名称, 状态, 详情)  状态 ∈ OK / WARN / FAIL
    checks = [
        ("name 格式（小写短横线、≤64）",
         "OK" if re.fullmatch(r"[a-z0-9-]{1,64}", str(fm.get("name", ""))) else "FAIL", ""),
        ("description ≤1024 字符（Claude 硬上限）",
         "OK" if len(desc) <= 1024 else "FAIL", f"{len(desc)} 字符"),
        ("description 含否定边界（不触发/仅用于/not for）",
         "OK" if any(k in desc.lower() for k in ("不触发", "仅用于", "不负责", "not for", "不适用")) else "FAIL", ""),
        ("when_to_use 字段存在（宿主语义匹配用）",
         "OK" if "when_to_use" in fm else "WARN", "可由 description 承载，但独立字段更稳"),
        ("有写操作时声明 invocable 边界",
         "OK" if (not any(k in allowed for k in ("Write", "Edit")))
            or any(k in fm for k in ("disable-model-invocation", "user-invocable")) else "FAIL",
         "本技能会改宿主配置，建议显式声明"),
        ("硬约束独立成节且前置（## 0.）",
         "OK" if any(l.startswith("## 0") for l in lines[:40]) else "FAIL", ""),
        ("硬约束逐条标注「每轮」（≥3 处）",
         "OK" if text.count("每轮") >= 3 else "WARN", f"「每轮」{text.count('每轮')} 处"),
        (f"全文 ≤{BUDGET} token（硬上限）",
         "OK" if tk_total <= BUDGET else "FAIL", f"{tk_total:.0f} token"),
        (f"建议 ≤{BUDGET - CUSHION} token（给压缩留 {CUSHION} 余量）",
         "OK" if tk_total <= BUDGET - CUSHION else "WARN", f"{tk_total:.0f} token"),
        (f"核心规则落在前 {CORE_FRONT} token 内",
         "OK" if any(l.startswith("## 0") for l in lines[:max(cut_line, 1)]) else "WARN",
         f"第 {cut_line} 行进入「{cut_sec}」"),
        (f"单节占比 ≤{MAX_SECTION_SHARE:.0%}（正文内）",
         "OK" if worst_share <= MAX_SECTION_SHARE else "WARN",
         f"最重「{worst[0]}」{worst_share:.0%}"),
        ("触发正例 ≥1 条口语问句",
         "OK" if ("「" in text or re.search(r'"[^"]{6,}"', text)) else "FAIL", "中英版引号均可"),
        ("形近反例（同一话题但不触发）",
         "OK" if ("形近" in text or "不是技能库治理" in text) else "WARN", "建议补 1 条形近反例"),
    ]

    print(f"SKILL.md  {len(text)} 字符 / {tk_total:.0f} token（正文 {tk_body:.0f}）/ {len(lines)} 行")
    print(f"前 {CORE_FRONT} token 边界：第 {cut_line} 行 · 所属章节「{cut_sec}」\n")
    icon = {"OK": "  [OK]  ", "WARN": "  [WARN]", "FAIL": "  [FAIL]"}
    for name, st, detail in checks:
        print(icon[st] + name + (f"  —— {detail}" if detail else ""))
    n_ok = sum(1 for _, s, _ in checks if s == "OK")
    n_warn = sum(1 for _, s, _ in checks if s == "WARN")
    n_fail = sum(1 for _, s, _ in checks if s == "FAIL")
    print(f"\n{n_ok} 通过 · {n_warn} 建议改进 · {n_fail} 必须修")
    return 1 if n_fail else 0


def _fm_end(lines: list) -> int:
    """frontmatter 结束行号（第二道 --- 的下一行）。"""
    for i, l in enumerate(lines[1:], 1):
        if l.strip() == "---":
            return i + 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
