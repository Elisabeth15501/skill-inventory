# Multi-platform publishing checklist (skill-inventory) — English version

> **中文版**：[publishing.md](publishing.md)
> Report language is user-selectable (`--set-lang auto|zh|en` to save / `--lang` for a one-off
> override); docs ship in both languages: `SKILL.md` / `SKILL.en.md`, `README.md` /
> `README.en.md`, this file / `publishing.en.md`, `usage-triggers.md` / `usage-triggers.en.md`.

> This skill publishes to both SkillHub and ClawHub, and the two platforms have opposite rules —
> the cleanup checklists are not interchangeable. Run through this checklist before every
> publish; do not rely on memory.

## Platform comparison

| Item | SkillHub (skillhub.cn) | ClawHub (clawhub.ai) |
|------|------------------------|----------------------|
| slug | `skill-inventory` (namespaced `@user_c5278a31/…`) | `agent-skill-inventory` (**globally unique**; original name taken) |
| Packaging | export a clean copy via `git archive HEAD` (ignored files excluded automatically) | package the workspace directly (CLI skips dotted path segments + reads `.gitignore`/`.clawhubignore`) |
| Delete before publish | `.gitignore`, `LICENSE`, `.clawhubignore`, `references/.gitkeep` (banned list is dynamic; delete whatever the error names) | nothing manual (`LICENSE` via `.clawhubignore`; dotted files auto-excluded) |
| Review | three parallel lines (content-compliance keywords + vulnerability scan + AI semantics) | three-layer security scan (static + VirusTotal + LLM); no keyword policing |
| License | not enforced | **MIT-0 mandatory**; the repo's MIT LICENSE conflicts, hence excluded |
| Version | SKILL.md frontmatter `version` | `--version` flag, kept in sync with the frontmatter |

## Command memo

```bash
# SkillHub (clean-copy flow)
git archive HEAD | tar -x -C "$PUB_TMP" && cd "$PUB_TMP"
rm -f .gitignore LICENSE .clawhubignore references/.gitkeep
skillhub publish "$PUB_TMP" --version X.Y.Z --changelog "..." --json
# Success: ok=true + reviewStatus/contentAuditStatus/securityScanStatus all pending

# ClawHub (publish from the workspace)
# ⚠️ Pin the CLI version, never @latest (unpinned = executing unreviewed remote code in the
#    publishing chain; SkillSpector Rp1 flags it). Before upgrading, check `npm view clawhub version`.
npx clawhub@0.23.3 skill publish . \
  --slug agent-skill-inventory --name "技能盘点与效能体检" --version X.Y.Z \
  --topics "..." --source-repo Elisabeth15501/skill-inventory \
  --source-commit "$(git rev-parse HEAD)" --changelog "..."
# Afterwards: npx clawhub@0.23.3 inspect agent-skill-inventory — check Moderate is CLEAN
```

## Notes

- **Both platforms read the same SKILL.md frontmatter version** — one edit covers both; pass
  `--version` explicitly to stay in sync.
- **Do not let ClawHub-specific tweaks leak into SkillHub artifacts**, or vice versa
  (`.clawhubignore` only matters to ClawHub; it must be deleted from the SkillHub copy).
- **Gate copy red lines**: SkillHub's advertising-law scan is sensitive to superlative words —
  terms like "唯一" (the only) / "绝不" (never) trigger blocker/HIGH. Use restrictive phrasing
  such as "仅限" (limited to) / "共两处" (two paths) / "仅一处" (one place) instead.
- SkillHub v1.0.0's publish response once returned `source: "clawhub"` (a personal publish should
  be `community`); v1.1.0/v1.2.0 both returned `community` correctly — judged a transient
  first-publish issue; contact the platform (skillhub@tencent.com / GitHub issues) only if it
  recurs.
- Do not pass `--categories` on a first ClawHub publish (unknown slugs fail); set categories on
  the web settings page afterwards.
- English docs (`SKILL.en.md` / `README.en.md` / `references/*.en.md`) publish fine — both
  platforms treat only `SKILL.md` as the primary document.
