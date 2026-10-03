# skill-inventory · Skill inventory & health check for office agents (English)

> 中文版：[README.md](README.md) · Docs language: `SKILL.md` (Chinese) / `SKILL.en.md` (English)

Skill inventory & health check for office agents (WorkBuddy, QwenWork, Baidu DuMate, Tianxi AI,
…): scans any skills directory, measures size / context-token footprint, detects duplicates, and
classifies skills into **used / closeable / manual-review / protected** with **conservative**
slimming advice. **Read-only by default**: inventory, classification and advice write nothing
anywhere; there are exactly two write paths, both requiring explicit consent
(`--overrides --apply --yes` for closes — WorkBuddy-family platforms only, auto-backup first;
`--set-lang` for the language preference) — the decision stays human.

> Skills whose manifest (name + description) rides along in every conversation turn cost real
> tokens — 54 installed skills ≈ 5,000+ tokens burned per turn. This tool provides the facts for
> "which ones to close".

## When to use

- "What skills do I have", "which can be closed / merged", "how much context do they cost"
- Health-check an office agent's skill library and cut context-token spend
- Inventory skills on WorkBuddy / QwenWork / Baidu DuMate / Tianxi AI
- Pin the report language to English or Chinese (or restore auto-follow)

## Usage

The script lives at `scripts/skill_inventory.py`. By default it inventories the WorkBuddy library:

```bash
python scripts/skill_inventory.py                          # full table + four buckets (auto-detect)
python scripts/skill_inventory.py --agent workbuddy        # platform profile
python scripts/skill_inventory.py --agent qwen             # QwenWork (scan-only)
python scripts/skill_inventory.py --agent baidu --root DIR # Baidu DuMate (path TBC → --root)
python scripts/skill_inventory.py --overrides              # draft the close list (draft only)
python scripts/skill_inventory.py --overrides --apply --yes   # WB: apply with your consent (backup first)
python scripts/skill_inventory.py --json                   # machine-readable output
python scripts/skill_inventory.py --protect a,b,c          # extra protected skills
```

Cross-agent: pick a platform with `--agent` (workbuddy / qwen / baidu / auto) or point `--root`
straight at a skills directory. Pass the usage log via `--usage-log`; **if the platform has no
usage log, the tool degrades to "nothing judged closeable"**.

## Language setting (auto / zh / en)

| Option | Meaning |
|--------|---------|
| `auto` (default) | automatic — the Agent decides per conversation language via `--lang`; if unset, falls back to env `SKILL_INV_LANG` → system locale → Chinese |
| `zh` | always respond in Chinese |
| `en` | always respond in English |

```bash
python scripts/skill_inventory.py --show-lang   # current setting, options and how to change
python scripts/skill_inventory.py --set-lang en # save preference (writes ~/.workbuddy/skill-inventory.json), effective immediately
python scripts/skill_inventory.py --set-lang auto
python scripts/skill_inventory.py --lang en     # this run only, keeps the saved setting
```

Changes take effect immediately after saving; `--set-lang auto` or deleting
`~/.workbuddy/skill-inventory.json` restores the default. Bucket names are always English
identifiers and `--json` keys are always English — scripted consumption is language-independent.

## Platform profiles & capability-aware closing

Agents differ in "close" capability; the tool branches on `can_close` — **non-closable platforms
never get close actions**, only a report plus manual-removal instructions:

| Platform | Scannable | Usage ledger | Programmatic close | Behaviour |
|----------|-----------|--------------|--------------------|-----------|
| **WorkBuddy** | ✅ `~/.workbuddy/skills` | ✅ `usage-log.json` | ✅ `skillOverrides` four states | inventory + close drafts; `--apply --yes` writes `off` with your consent |
| **QwenWork** | ✅ `~/.qwenworkcn/skills` | ✅ (usage adapter) | ❌ **no disable switch** (field-tested) | inventory + connector/UI close instructions; never performs a close |
| **Baidu DuMate** | ✅ local sandbox (path TBC → `--root`) | ❌ | ✅ disable switch + expert-suite disable | inventory + close instructions; owns the "expert suite" dimension |
| **Generic** (unknown hosts, incl. Tianxi cloud sandboxes) | ✅ `--root` directory | ❌ by default (`--usage-log` to add) | ❌ no close channel | `--agent generic`: pure inventory + advice, all manual review, no close actions |

> Principle: **"no usage record" is not "unused"**. On platforms without a close switch the tool
> only health-checks and leaves the knife to you, avoiding "close advice" you cannot execute.

## 🔒 Behaviour contract (read this before trusting it)

**Read-only by default; exactly two write paths, both consent-gated:**

1. **Writes nothing by default.** Inventory, classification and advice are read-only; no
   disable/delete API is called.
2. **Write path 1 (closes; needs your explicit consent).** On closable platforms
   (WorkBuddy family), `--overrides --apply --yes` **backs up `settings.json` automatically
   first**, then merges candidates into the `off` state of `skillOverrides`; without `--yes` it
   is a dry-run preview (no files read or written); non-closable platforms (QwenWork etc.)
   reject `--apply` outright. Every report and `--overrides` output states this path explicitly —
   the tool **never** closes a skill silently or on its own initiative. Host-native toggles
   (e.g. the `/skills` menu, press Esc to persist) are preferred.
3. **Write path 2 (language preference; needs your explicit command).** `--set-lang auto|zh|en`
   writes the report language preference to `~/.workbuddy/skill-inventory.json` (that one key
   only); a user-controlled display preference, revertible via `--set-lang auto` or by deleting
   the file.
4. **No persistence mechanisms.** No cron jobs, no startup scripts, no daemons, no
   self-modification. Cross-session effects are limited to two user-consented, disclosed and
   reversible writes — the `off` entries in `skillOverrides` (reversible via the host's `/skills`
   menu) and the language preference file (revert via `--set-lang auto` or file deletion).
5. **Protected skills never enter the closeable bucket.** This includes: this tool itself,
   skills marked `protected: true` in frontmatter, safety/audit classes (names containing
   security/audit/safe/guard/privacy/sanitize/compliance/backup), and anything added via
   `--protect`. They are listed separately as "protected".
6. **"No usage record" is not "unused".** Users may **never name a skill in conversation** and
   instead:
   - pre-configure **keyword triggers** that auto-invoke it;
   - use it indirectly via **expert/connector components** that call it internally.
   Both leave **no trace** in usage logs. So **every close candidate must be confirmed with the
   user** for these dependencies before closing.
7. **Telemetry gap ⇒ nothing judged closeable.** When the platform has no usage log, or the log
   fails to read (P1 fixed: explicit warning instead of silence), everything lands in
   "manual review" and **no close candidates are emitted** — under-reporting beats false kills.
8. **Reverse-dependency scanning (the scenario you worry about most).** Before judging
   "closeable", the tool scans automations / hooks for skill references (default
   `~/.workbuddy/automations` and `~/.workbuddy/hooks`; extend with `--refs`). **Any referenced
   skill is locked as "protected"** — with or without usage records. This blocks false kills
   caused by keyword triggers or expert/connector-internal calls invisible to logs. Point
   `--refs /path/to/defs` at definitions stored elsewhere; disable entirely with `--no-ref-scan`.

## Reading the output

- **used**: genuinely used (trustworthy).
- **closeable**: no usage record and untouched for over 30 days. **Still requires human
  confirmation**, and keyword/expert-trigger dependencies must be ruled out first.
- **manual-review**: no usage record but recently modified, or no telemetry on this platform —
  do not rush.
- **protected**: never auto-suggested for closing; explicit human action required.

## Limitations (stated honestly)

- Usage frequency relies on the platform usage log; WorkBuddy has a real ledger
  (`usage-log.json`), most other platforms do not — conclusions then rest on last-modified time
  only, which **must not justify closing**.
- Keyword-trigger / expert-component dependencies cannot be probed from the filesystem — a
  structural blind spot covered only by user confirmation.
- Duplicate detection is approximate (name/description/size), not semantic dedup.

## About automated scanners (Ae1 findings)

Some automated scanners (e.g. ClawHub SkillSpector) report **Ae1 "Referenced artifact was not
completely inspected"** — the scanner cannot fully inline the referenced ~900-line
`scripts/skill_inventory.py`. This is an **inspection limitation**, not suspicious behavior:

- the script's own **static analysis passes** ("No suspicious patterns detected");
- the full source is public on the [GitHub repo](https://github.com/Elisabeth15501/skill-inventory)
  for manual review at any time;
- the script docstring carries a machine-greppable "Permission & persistence declaration" block —
  feel free to verify with grep.

## License

MIT — see [LICENSE](LICENSE).
