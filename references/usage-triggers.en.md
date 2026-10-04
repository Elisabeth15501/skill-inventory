# Skill trigger taxonomy (T1–T6) and the telemetry blind spot — English version

> **中文版**：[usage-triggers.md](usage-triggers.md)

> **What this file is**: the design-rationale document for skill-inventory, arguing why
> usage-log.json alone must never decide "closeable". It describes **platform-wide mechanics**,
> not this skill's trigger configuration.
>
> **This skill's actual trigger scope**: only inventory / health-check / pre-close impact /
> report-language-setting requests (e.g. "inventory my installed skills", "which skills can be
> closed", "show the impact of closing X", "switch the report to English"); unrelated tasks
> (reports, mail, code generation) never trigger it.
>
> Purpose: explain why `skill-inventory` cannot rely on `usage-log.json` alone when judging
> "closeable". This file underpins the P0 guardrails (reverse-dependency scan +
> telemetry-gap degradation).

## 1. Six ways users invoke a skill

| ID | Trigger | Typical case | Logged? |
|----|---------|--------------|---------|
| **T1** | Explicit | user says "use skill-inventory" or `/skillname` in conversation | ✅ yes |
| **T2** | Description auto-match | agent matches the task against the SKILL.md `description`; the user never names it | ❌ no |
| **T3** | Keyword routing | a pre-set "keyword → invoke skill" rule fires on a matching keyword | ❌ no |
| **T4** | Automation / scheduled | cron/recurring automations call the skill | ❌ no |
| **T5** | Hooks | event hooks fire the skill under conditions | ❌ no |
| **T6** | Expert/connector-internal | an Expert or Connector component calls the skill internally | ❌ no |

## 2. The blind spot (why logs alone mislead)

`usage-log.json` records **T1 only**; T2–T6 leave no trace.

Market research (product-reviewer, benchmarking jiepi-skill / skill-monitor / audit-hermes):
ordinary users **rarely name a skill in conversation** —
- many use keyword triggers (T3) or expert components with embedded skills (T6) indirectly;
- others run skills in the background via scheduled tasks (T4) / hooks (T5).

Therefore:

- **Heavy T2–T6 usage (daily/weekly) is ~30–70%+ invisible in logs** (composite estimate from
  the sources in the research archive, wiki §8 — not a single-source measurement);
- **Light (occasional) usage is ~10–20%+ invisible**.

→ Closing on "absent from the log" alone would kill many skills that are still silently in use.

## 3. This skill's countermeasures (P0 guardrails)

1. **Telemetry-gap degradation**: when `usage-log.json` is missing/corrupt/lacks a `skills`
   field, `load_usage()` returns `( {}, False )` and prints a stderr warning; the `cleanup`
   bucket then stays **empty** and every "recently uncalled" skill lands in `review`
   (manual confirmation) — nothing is auto-suggested for closing.
2. **Reverse-dependency scan**: scans `automations/` and `hooks/` with word-boundary regexes
   (so `git` does not lock `github`); any referenced skill is locked into `protected`.
   `settings.json` is the skill registry and is **deliberately excluded** (scanning it would
   falsely lock the whole library).
3. **Safety keywords + self-protection + `--protect`**: leaves containing
   `security/audit/safe/guard/privacy/sanitize/compliance/backup`, this skill itself, and
   anything the user passes via `--protect` all land in `protected`.
4. **Two write targets + one backup artifact, all consent-gated**: read-only by default; the
   `cleanup` bucket is advice only. Exactly two user-initiated writes: `--overrides --apply --yes`
   (dry-run without `--yes`; before the write it creates a `settings.json.bak.<timestamp>` safety
   copy and prints its path) and `--set-lang` (writes the report language preference to
   `~/.workbuddy/skill-inventory.json`).
5. **Persistence cut**: no cron jobs, no startup scripts, no daemons, no self-modification. The
   language preference file is a **display preference** only (a single JSON key) — nothing is
   scheduled or registered from it, it is read solely to pick the report language on the next run,
   and `--set-lang auto` or deleting it restores the default; it is not a persistence mechanism.
   The `off` entries in `skillOverrides` are reversible via the host's `/skills` menu.

## 4. Open boundaries needing user confirmation

- The actual local paths of automations / hooks / expert definitions need user confirmation,
  otherwise `--refs` reverse-dependency scanning cannot take effect (defaults scan
  `~/.workbuddy/automations` and `~/.workbuddy/hooks`).
- Cross-agent trigger mappings (QwenWork / Baidu DuMate / Tianxi AI) still need per-platform
  field testing; this document is WorkBuddy-first.
