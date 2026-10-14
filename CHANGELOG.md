# Changelog — skill-inventory

All notable changes to this skill are documented here. Format follows a reverse-chronological
(newer on top) list per release. Version is bumped per SemVer on every user-facing change.

## [1.5.2] — 2026-10-14

### Tianxi (天禧 AI) publish-readiness remediation (P0–P2)
- **P0 — Version alignment**: `config.yaml` bumped `1.5.1 → 1.5.2` so the three in-repo
  version markers (SKILL.md frontmatter / config.yaml / SKILL.en.md frontmatter) agree again.
- **P0 — `config.yaml` contradiction removed for the Tianxi package**: the skill legitimately
  *writes* (consent-gated `--overrides --apply --yes` and `--set-lang`), so `config.yaml`'s
  `permissions.filesystem: read-only` was contradictory. `config.yaml` is **excluded from the
  Tianxi upload zip** (it is a local archive file, not an official upload requirement per the
  2026-10-01 platform doc verification) — eliminating the false read-only claim.
- **P1 — Dedicated white-list packaging script** (`tools/build_tianxi_zip.py`): produces a
  deterministic `dist/skill-inventory-1.5.2-tianxi.zip`, dropping dev noise
  (`references/check_skill_md.py`, `references/__pycache__`, dotfiles) and `config.yaml`.
  Replaces the stale `v1.4.0` package. Includes a post-pack safety scan (no `urllib`/`requests`/
  `http.client`/`socket.create`/`os.system`/`subprocess`/`os.popen`/`eval` in any `.py`;
  `SKILL.md` frontmatter must be valid YAML).
- **P1 — Docs aligned with implementation**: Tianxi AI is now explicitly described as supported
  **via the generic agent mode** (no dedicated profile; sandboxes have no close channel), in both
  `SKILL.md` and `SKILL.en.md` "when to use" sections. No over-claiming of a proprietary profile.
- **P2 — CHANGELOG.md / RELEASE_NOTES.md** added for the Lenovo three-place version-consistency practice.
- **P2 — Project-level `.skill-config.json`** created (private, git-ignored) with the schema the
  `lenovoskill` CLI actually reads (`name`/`description`/`description_zh`/`version`/`updateNotes`/
  `ignore`), pre-filling `ignore` with `config.yaml` for belt-and-suspenders exclusion.

### Carried over from earlier 1.5.x (audit-remediation)
- Non-blocking code-review fixes already shipped in `1.5.2` HEAD `df01c66`:
  - `backup_settings()` returns only the backup path (no misleading tuple).
  - Protected-leaf / safety-heuristic state moved to `main()` locals passed into `scan()` —
    eliminates cross-invocation module-level global leakage.
  - `attach_usage` substring magic number `5` → named constant `MIN_SUBSTR_LEN`.
  - `rows` implicit schema documented above `scan()` row construction (lowers B1 change risk).
  - Backup timestamp gains `%f` microseconds to avoid same-second `--apply` overwrite.
  - New i18n template `.format()` syntax self-test (206 templates all pass).

## [1.5.1] — 2026-10-09
- Resolved ClawHub DBM 91% / Intent-Code 87% contradiction (P0-1..P0-4):
  precise `persistence` wording, repo-wide "no autonomous residency" phrasing, removed shebang,
  added `capabilities`. AGENTIC over-delegation hits → 0.

## [1.5.0] — 2026-10-08
- Initial public-facing inventory skill with four-bucket classification
  (used / protected / closeable / manual-review) and anti-accidental-close guardrails.
