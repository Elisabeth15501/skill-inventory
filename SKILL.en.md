# skill-inventory · Skill inventory & health check for office agents (English version)

> **中文文档**：`SKILL.md`（this file is the English version）· `README.md`。
> The report language is user-selectable — see "Language setting" below.
> Both editions carry the same content: the English files are not shorter (measured on v1.4.0 —
> SKILL 14,460 vs 10,722 chars, README 14,505 vs 7,261), with matching section counts and FAQ items.
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
| Skills directory | ✅ (auto-detected for known platforms) | each subdirectory containing a `SKILL.md` counts as one skill; use `--root <dir>` otherwise, or just `--probe` to let the tool find it |
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
| `python scripts/skill_inventory.py --agent generic --probe [dirs]` | let the tool **find** skill directories on unknown hosts (optional comma-separated candidates; `SKILL_INVENTORY_ROOT` env var also honored) |
| `python scripts/skill_inventory.py --impact <name>` | single-skill impact deep dive |
| `python scripts/skill_inventory.py --json` | machine-readable JSON |
| `python scripts/skill_inventory.py --show-lang` | show language setting and options |
| `python scripts/skill_inventory.py --set-lang auto\|zh\|en` | save the language setting (effective immediately) |
| `python scripts/skill_inventory.py --lang zh\|en` | language override for this run |
| `python scripts/skill_inventory.py --selftest` | self-test the built-in frontmatter parser (zero deps, offline) |

Flow: `auto-detect platform → fall back to generic mode`. In generic mode `--probe` looks for the
skills directory itself (fall back to `--root <dir>` if it finds nothing); without a usage log the tool
degrades to "nothing judged closeable"; `--refs` adds reverse-dependency scan roots.

## 6. What a real run actually prints

After running `python scripts/skill_inventory.py` once, the terminal prints the following
structure (excerpt, WorkBuddy mode, English):

```text
ℹ  Telemetry scope: the usage log covers explicit invocations only (T1). Auto-mounting,
   scheduled tasks, hooks and expert-internal calls (T2–T6) are not counted — "has usage
   records" ≠ "only used explicitly", and "no usage records" ≠ "unused" (reverse-dependency
   scanning only covers discoverable config roots).

Platform                        WorkBuddy
Total skills                    59    (market-installed 29 / self-made or edited 30)
Has usage records               27
Protected (do not close)        6
Close candidates                19    (still require per-item human confirmation)
Manual review                   7
                       19,665 chars  ≈ 6,912 tokens / per conversation turn

Directory                                     Lines    KB    Source        Last mod    Uses   Last used
--------------------------------------------------------------------------------------
agnes-ai                            ⚠     537    23.9    self-made 2026-10-09  0       —
ai-weekly                               168  2734.0    self-made 2026-10-09  1  2026-10-05
skill-publish-gate                      211   324.7    self-made 2026-10-09  2  2026-10-09
skill-inventory                     🔒     91    52.1    self-made 2026-09-28  0       —
office-token-booster                  375   653.2    self-made 2026-09-25  4  2026-08-21
skill-creator                           356    52.6    market  2026-06-30  17  2026-08-27

🔻 Close candidates: no usage record AND untouched for 30+ days (19 items)
   ⚠ Suggestions only — do NOT close without your explicit confirmation; first confirm no
     keyword / expert / automation dependency.
  bug-fixing                                667 lines  2026-08-04
  log-analyzer                              501 lines  2026-08-04
  code-fix                                  262 lines  2026-08-04

🔒 Protected (do not close): 6 items
  skill-inventory                     (this tool itself; never enters candidates)
  skill-clean-audit                   (safety/audit heuristic hit)
  security-audit                      (name contains "security")
  ⋯
```

Legend: `⚠` = recently modified but no usage record (goes to "manual review");
`🔒` = protected (never enters candidates); `—` = no usage record.
Lines/KB = line count and size of that skill's `SKILL.md`.

**Machine-readable (`--json`)**: adding `--json` emits a JSON object whose top-level keys
are always English (unaffected by the language setting):

```json
{
  "agent": "workbuddy",
  "can_close": true,
  "rows": [
    { "name": "office-token-booster", "lines": 375, "kb": 653.2,
      "from_market": false, "last_modified": "2026-09-25", "last_used": "2026-08-21",
      "uses": 4, "protected": false, "locked": false, "referenced_by": [] }
  ],
  "buckets": { "protected": [ "skill-inventory" ], "keep": [ "⋯" ],
               "cleanup": [ "bug-fixing" ], "review": [ "⋯" ] },
  "telemetry_gap": false,
  "telemetry_scope": "t1-only",
  "cannot_close": false
}
```

The four `buckets`: `protected` (protected, do not close) / `keep` (has usage records,
retain) / `cleanup` (close candidates, still need human confirmation) / `review`
(manual review). `telemetry_gap=true` means no telemetry, so the report contains no
close candidates.

**Self-test (`--selftest`)**: verifies the built-in fallback parser against PyYAML's
block-scalar semantics; runs offline:

```text
[selftest] frontmatter block-scalar semantics
  8 cases passed / 0 failed (reference: PyYAML)
  [OK] SKILL.md fallback parse: version=1.5.1, description 1390 chars
```

## 7. Data-source precedence

1. **Platform usage log** (highest confidence): explicit invocations only (T1); auto-mounting,
   scheduled tasks, hooks and expert-internal calls (T2–T6) are invisible — the report states
   this scope on every run.
2. **Reverse-dependency scan** (covers the blind spot): skills referenced by automations / hooks /
   routing states / plugin manifests are locked as protected.
3. **Last-modified time** (lowest confidence): reference only when no telemetry exists —
   **never a close justification on its own**.
4. **User confirmation** (final say): every close candidate requires per-item human confirmation.

## 8. User confirmation points

- **The tool never closes a skill on its own.** The close write path runs only with your explicit
  authorization — pass `--overrides --apply --yes` on closable platforms (WorkBuddy family); the
  tool backs up `settings.json` first, then merges "off" entries into `skillOverrides`; without
  `--yes` it is a dry-run preview; non-closable platforms reject `--apply` outright.
- **Prefer the host's own toggles**: e.g. WorkBuddy's `/skills` menu (press Esc to persist),
  QwenWork/Baidu client switches; generic mode has no close channel and outputs candidate lists only.
- **Close candidates**: review the impact preview (`--impact <name>`) first; confirm there is no
  keyword-trigger / expert / automation dependency.

## 9. Risk boundaries

- **Read-only by default; two disclosed, consent-gated write targets plus one backup artifact**:
  no config writes and no disable/delete calls unless you explicitly authorize one of the two
  capabilities — `--overrides --apply --yes` (dry-run without `--yes`, rejected on non-closable
  platforms) and `--set-lang` (writes the language preference file only). Both are labeled
  explicitly in every report and output, and the close write always produces a timestamped
  `settings.json.bak.<ts>` safety copy first, whose path is printed so you may delete it manually when no longer needed.
- **No autonomous residency**: no cron jobs, no startup scripts, no daemons, no
  self-modification (i.e. no autonomous execution). Cross-session **visible writes** are limited
  to two user-consented, disclosed and reversible capabilities — the `off` entries in
  `skillOverrides` (reversible via the host's `/skills` menu) and the language preference file.
  The language preference file is a display preference only (a single JSON key): nothing is
  scheduled or registered from it, it is read solely to pick the report language, and
  `--set-lang auto` or deleting the file restores the default.
  ↳ Note: this tool **does perform authorized cross-session writes** (see the "two write targets
  + backup artifact" item above) — that is distinct from autonomous residency (autonomous
  execution), which we have none of.
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

## 10. Mistakes to avoid

The six most common pitfalls in real use that this tool is **deliberately not** designed to
encourage:

| # | Wrong move | Why it's wrong | Right move |
|---|---|---|---|
| 1 | **Deleting the skill directory directly** to "close" a skill | Bypasses the backup artifact and protected-lock detection; may delete a skill still referenced by automations/hooks/triggers with no rollback | Let the tool emit an `--overrides` draft, then close via the host `/skills` menu or manual removal using the backup path printed in the report |
| 2 | **Closing without checking impact preview** | The skill may still be called implicitly by keyword triggers / experts / automations, leaving no log trace → false kill | Run `--impact <name>` first; confirm `referenced_by` is empty before acting |
| 3 | **Treating "no usage record" as "unused"** | "No record" only means no T1 explicit hit; T2 auto-mount / T3 keyword routing / T4 scheduled tasks / T5 hooks / T6 expert-internal calls leave no trace | Read both the "close candidates" and "manual review" buckets; confirm every candidate with the user before closing |
| 4 | **Expecting `--apply` to work on non-closable platforms** | `can_close=False` platforms (QwenWork / Baidu / generic) have no programmatic close channel; `--apply` is rejected outright | Use the host's own enable/disable toggles or manual client removal; the tool only reports inventory and candidates |
| 5 | **Treating `--protect` as a universal guard** | `--protect` only adds named skills to the protected bucket; it does not change the fact that "reverse-dependency scan only covers discoverable config roots" | Pair with `--refs` to point at extra reference-definition roots (automations/hooks/routing) for double coverage |
| 6 | **`--root` pointing at a parent directory** that swallows unrelated dirs | In generic mode, `--root` scans **every** subdirectory under it as a skill, pulling in unrelated folders | Point `--root` exactly at the "skills root" (each subdirectory = one skill); on unknown hosts prefer `--probe` to let the tool find the root itself |

> Design posture: **under-report rather than false-kill.** The tool will never decide for you
> that a skill "may be closed" — it only emits candidates and impacts, and every write
> requires your explicit authorization plus a printed backup path.

---

## 11. FAQ

**Q1. Why is my skill in "manual review" instead of "close candidates"?**
Only skills with **no usage record** *and* **untouched for over 30 days** become close candidates.
Four things push a skill into manual review: ① no telemetry (usage log missing/unreadable) — the tool
under-reports rather than risking a false kill; ② modified within the last 30 days; ③ the host has no
programmatic close channel (e.g. QwenWork, generic mode); ④ it matches a protection rule. Passing
`--usage-log <path>` and protecting confirmed skills with `--protect` cuts most of the noise.

**Q2. Does "has usage record" mean "only ever invoked explicitly"?**
No. The usage log records **explicit invocations only** (T1). Auto-mounting (T2), keyword routing (T3),
scheduled tasks (T4), hooks (T5) and expert/connector-internal calls (T6) leave no trace at all. So
"used" does not mean "explicitly used", and — more importantly — "no record" does not mean "unused";
that gap is exactly why manual review exists.

**Q3. The report says "telemetry gap". How do I fix it?**
It means the usage log could not be read, so conclusions rest on last-modified time only and **no**
close candidates are emitted. Two remedies: ① if the platform has a log, point at it with
`--usage-log <path>` (e.g. `~/.qwenworkcn/skill-usage.json`); ② if there is no log, rely on
reverse-dependency scanning (`--refs` for automation / hook / config roots) plus manual confirmation —
the tool stays conservative in that state.

**Q4. Could closing a skill break an automation or keyword trigger?**
Three guardrails: ① reverse-dependency scanning locks anything referenced by automation / hooks /
routing / plugin configs into the protected bucket; ② safety-audit keywords and this tool itself are
never candidates; ③ every candidate needs your per-item confirmation. **Guardrails are not
exhaustive** — T2 auto-mounting and descriptive keyword references are invisible, so always review the
impact preview first: `--impact <name>`.

**Q5. What exactly gets written, and can I undo it?**
One place only: the `skillOverrides` key of `~/.workbuddy/settings.json` (candidates marked `off`).
Before writing, a timestamped `settings.json.bak.<ts>` backup is created and its path is printed; the
write itself is an atomic `os.replace`, so a half-written config is never left behind. Three ways back:
restore the backup file, flip the entries in the host's `/skills` menu, or delete the entries.

**Q6. Why do QwenWork / Baidu / generic mode get no close actions?**
Closing capabilities differ per host. Where `can_close=False` there is no programmatic per-skill
switch, so the tool forks by capability: inventory and candidate lists only, leaving the actual action
to the host's own toggles or manual removal — rather than suggesting something you cannot execute.

**Q7. How accurate is the "suspected duplicate" detection?**
It is **approximate** matching (name / description / size), not semantic deduplication: it will flag a
market copy and your own copy with the same name as suspected duplicates, and it can miss pairs whose
descriptions differ but whose function overlaps. Treat it as a lead, not a verdict.

**Q8. What do the `[E-LOG]` / `[E-CONF]` codes mean?**
Stable codes, easy to search and report:

| Code | Meaning | Typical fix |
|------|---------|-------------|
| `E-LOG` | usage log missing or unreadable | pass `--usage-log <path>`; or protect critical skills with `--protect` first |
| `E-ROOT` | skills directory not found | check the path, or point at it with `--root <dir>` |
| `E-PLATFORM` | unknown `--agent` value | use one of workbuddy / qwen / baidu / generic / auto |
| `E-NOCLOSE` | host has no programmatic close channel | use the host's toggles or remove manually |
| `E-CONF` | reading/writing settings.json failed | nothing was modified; check whether another process holds the file (reads are retried twice) |
| `E-READ` | one skill directory was unreadable | that directory is skipped, the rest is unaffected; check its permissions |

**Q9. The report lists no close candidates — does that mean my skills are all fine?**
Not necessarily; there is probably no telemetry (Q1/Q3). The tool's stance is "under-report rather
than falsely kill": without usage records it will not make the closing decision for you, but it always
tells you exactly where the gap is.

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
