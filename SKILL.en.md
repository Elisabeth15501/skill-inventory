# skill-inventory · Skill inventory & health check for office agents (English version)

> **中文文档**：`SKILL.md`（this file is the English version）· `README.md`。
> The report language is user-selectable — see "Language setting" below.
> Maintainer-only notes (publishing checklist / usage-trigger archive) live in the GitHub
> repo's `references/` and are not part of the distributed package.

Office agents (WorkBuddy, QwenWork, Baidu DuMate, Tianxi AI, …) accumulate skills whose
name+description entries ride along in every conversation turn — 54 installed skills ≈ 5,000+
tokens burned per turn.

## 1. When to use

Trigger examples (auto-mounted via `description` match, or invoked explicitly):

- "inventory my installed skills"
- "which skills can I close or merge", "how much context do my skills cost"
- "show the impact of closing <skill> before I do it"
- "switch the report language to English/Chinese", "set language to auto"

**Not for**: unrelated tasks (report writing, mail, code generation) — this skill only
inventories and assesses skill libraries.

## 2. Language setting (auto / zh / en)

| Option | Meaning |
|--------|---------|
| `auto` (default) | automatic — the Agent decides per conversation language via `--lang`; if unset, falls back to env `SKILL_INV_LANG` → system locale → Chinese |
| `zh` | report language pinned to Chinese (change any time via `--set-lang` / `--lang`) |
| `en` | report language pinned to English (change any time via `--set-lang` / `--lang`) |

- **View**: `--show-lang` prints the current setting, all three options with descriptions,
  and how to change them.
- **Save**: `--set-lang auto|zh|en` writes the preference file
  `~/.workbuddy/skill-inventory.json` (that file only, written only when you run the command);
  the change takes effect on the next run immediately. `--set-lang auto` or deleting the file
  restores the default.
- **One-off override**: `--lang zh|en` affects this run only and does not touch the saved setting.
- **Precedence**: `--lang` (this run) ＞ saved setting (zh/en) ＞ auto fallback chain.
- **`auto` is not a lock-in**: it is the fallback for users who have not expressed a preference,
  not an enforced choice — pin zh or en with `--set-lang` at any time, or override a single run
  with `--lang`. Users who pick nothing simply get the default report language.
- **Invariant**: bucket names are always English identifiers (used / protected / closeable /
  manual-review) and `--json` output is always English-keyed — programmatic consumption is
  language-independent.

## 3. Inputs

| Input | Required | Notes |
|-------|----------|-------|
| Skills directory | ✅ (auto-detected for known platforms) | each subdirectory containing a `SKILL.md` counts as one skill; use `--root <dir>` otherwise |
| Usage log | optional | `--usage-log <path>`; WorkBuddy's `usage-log.json` is auto-detected |
| Reverse-dependency roots | optional | `--refs <path>`: automation/hook/routing configs that may reference skills implicitly |
| Protect list | optional | `--protect a,b,c` or `--protect-file`; a safety/audit keyword heuristic is built in |

**Permission scope** (mirrors the machine-readable declaration in the script docstring):

- **Read**: skills directories, usage logs, automation/hook/routing/plugin configs
- **Write** (two target paths + one backup artifact, all requiring explicit consent):
  1. the `skillOverrides` key of `~/.workbuddy/settings.json` — only via your explicit
     `--apply --yes`;
  2. the language preference file `~/.workbuddy/skill-inventory.json` — only via your
     explicit `--set-lang`;
  3. backup artifact — while `--apply --yes` runs, a `settings.json.bak.<timestamp>` safety copy
     is created beside `settings.json` (inert copy, path printed to you, never read back).
- **Network**: none. **Subprocess**: none.

Pure local static analysis — no network, no subprocesses (sandbox red-line compliant).

## 4. Outputs

1. **Inventory report** (default): totals, market vs self-built ratio, token-footprint estimate,
   per-skill table, four buckets — **used / closeable / manual-review / protected**.
2. **Impact preview**: for every reference-locked skill, which references break if closed
   (`[kind] full path` + hit terms); single-skill deep dive via `--impact <name>`.
3. **Duplicate hints**: multiple active copies, active+disabled copies, same-name skills.
4. **Machine-readable JSON** (`--json`): buckets, structured `referenced_by`, `telemetry_scope`.

## 5. How to run

| Command | Purpose |
|---|---|
| `python scripts/skill_inventory.py` | auto-detect platform, full report |
| `python scripts/skill_inventory.py --agent workbuddy` | WorkBuddy (usage ledger; close drafts) |
| `python scripts/skill_inventory.py --agent qwen` | QwenWork (usage records; close via connector/UI) |
| `python scripts/skill_inventory.py --agent baidu` | Baidu DuMate (multi-root; no telemetry → all manual review) |
| `python scripts/skill_inventory.py --agent generic --root <dir>` | generic mode: any platform / custom directory |
| `python scripts/skill_inventory.py --impact <name>` | single-skill impact deep dive |
| `python scripts/skill_inventory.py --json` | machine-readable JSON |
| `python scripts/skill_inventory.py --show-lang` | show language setting and options |
| `python scripts/skill_inventory.py --set-lang auto\|zh\|en` | save the language setting (effective immediately) |
| `python scripts/skill_inventory.py --lang zh\|en` | language override for this run |

Flow: `auto-detect platform → fall back to generic mode`. Generic mode **requires** `--root`;
without a usage log the tool degrades to "nothing judged closeable"; `--refs` adds
reverse-dependency scan roots.

## 6. Data-source precedence

1. **Platform usage log** (highest confidence): explicit invocations only (T1); auto-mounting,
   scheduled tasks, hooks and expert-internal calls (T2–T6) are invisible — the report states
   this scope on every run.
2. **Reverse-dependency scan** (covers the blind spot): skills referenced by automations / hooks /
   routing states / plugin manifests are locked as protected.
3. **Last-modified time** (lowest confidence): reference only when no telemetry exists —
   **never a close justification on its own**.
4. **User confirmation** (final say): every close candidate requires per-item human confirmation.

## 7. User confirmation points

- **The tool never closes a skill on its own.** The close write path runs only with your explicit
  authorization — pass `--overrides --apply --yes` on closable platforms (WorkBuddy family); the
  tool backs up `settings.json` first, then merges "off" entries into `skillOverrides`; without
  `--yes` it is a dry-run preview; non-closable platforms reject `--apply` outright.
- **Prefer the host's own toggles**: e.g. WorkBuddy's `/skills` menu (press Esc to persist),
  QwenWork/Baidu client switches; generic mode has no close channel and outputs candidate lists only.
- **Close candidates**: review the impact preview (`--impact <name>`) first; confirm there is no
  keyword-trigger / expert / automation dependency.

## 8. Risk boundaries

- **Read-only by default; two disclosed, consent-gated write targets plus one backup artifact**:
  no config writes and no disable/delete calls unless you explicitly authorize one of the two
  capabilities — `--overrides --apply --yes` (dry-run without `--yes`, rejected on non-closable
  platforms) and `--set-lang` (writes the language preference file only). Both are labeled
  explicitly in every report and output, and the close write always produces a timestamped
  `settings.json.bak.<ts>` safety copy first, whose path is printed so you can delete it.
- **No persistence mechanisms**: no cron jobs, no startup scripts, no daemons, no
  self-modification. Cross-session effects are limited to two user-consented, disclosed and
  reversible writes — the `off` entries in `skillOverrides` (reversible via the host's `/skills`
  menu) and the language preference file. The language preference file is a display preference
  only (a single JSON key): nothing is scheduled or registered from it, it is read solely to
  pick the report language, and `--set-lang auto` or deleting the file restores the default —
  it is not a persistence mechanism.
- **"No usage record" is not "unused"**: keyword triggers and expert/connector-internal calls
  leave no trace in usage logs — a structural blind spot covered by reverse-dependency scanning
  plus user confirmation.
- **Telemetry gap ⇒ nothing judged closeable**: without a usable usage log everything lands in
  manual-review. Under-reporting beats false kills.
- **Protected skills never enter the closeable bucket**: this tool itself, `protected: true`,
  safety/audit keyword hits, reference-locked skills, user-added via `--protect`.
- **Duplicate detection is approximate** (name/description/size), not semantic dedup; results
  cover discoverable config roots only — T2 auto-mounting and descriptive keyword references
  are invisible to it.

---

## Platform matrix

| Platform | Detection | Usage ledger | Programmatic close | Behaviour |
|----------|-----------|--------------|--------------------|-----------|
| WorkBuddy | `~/.workbuddy/skills` auto | ✅ `usage-log.json` | ✅ `skillOverrides` (needs `--apply --yes`, backup first) | inventory + close drafts |
| QwenWork | `~/.qwenworkcn/skills` auto | ✅ `skill-usage.json` | via connector/UI (never performed by this tool) | inventory + usage records + client-side checklist |
| Baidu DuMate | multi-root auto | ❌ | via UI/connector | inventory + close instructions; no telemetry → all manual review |
| Generic (incl. Tianxi sandboxes) | `--root` | none by default | ❌ no close channel | inventory + advice; all manual review |

> Principle: **capability-aware** — what the tool emits depends on whether the platform can close
> programmatically. Non-closable platforms get inventory + candidate lists only; the "knife" stays
> with the host and the user.
