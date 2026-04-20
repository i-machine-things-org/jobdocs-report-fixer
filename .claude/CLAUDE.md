# Auto Version Control Rules - Claude AI

You are a senior software developer. These rules override your default behavior. Follow them on every action without being asked.

## Rule 0: Always Read First

Before taking any action on this project — including edits, commits, or file creation:

1. Read `.claude/CLAUDE.md` and `.claude/S&P.md`.
2. Run `gh pr list` — if a PR exists for the current branch, run `gh pr view <number> --comments` and read **all comments** (CodeRabbit and human) before proceeding.
3. Run `gh issue list` — check for open issues relevant to the current work.
4. Do not make any edits until all outstanding findings and review comments are addressed or acknowledged.

No exceptions.

### S&P.md is for programming notes only

`.claude/S&P.md` is a standards and practices log — a reference for coding patterns, past findings, and decisions. It is **not** the source of truth for PR review status.

- To check if a PR review is complete or paused: **always use `gh pr view <number> --comments`**.
- CodeRabbit may auto-pause reviews after rapid commits — check for `review paused` in the summary comment.
- If paused, trigger a new run with: `gh pr comment <number> --body "@coderabbitai review"`
- If CR hits a rate limit (`Rate limit exceeded`), run `date -u` to get the current UTC time, calculate the UTC timestamp when the window clears, and state it explicitly. Re-trigger on the first user interaction at least 5 minutes after that time.
- **Sequential PR workflow:** Open one PR, wait for CR to finish and address all findings, merge, then open the next.

## Trigger Prompt

When the user says **"run auto version control"** (or any close variation), immediately run the full assessment:

1. Run `git status`, `git branch`, and `git log --oneline -10`
2. Run `gh issue list` and report any open issues
3. Report the current state: branch, uncommitted changes, recent commits, version tags
4. Flag any issues: working on main, uncommitted changes, missing .gitignore, no tags
5. Recommend next actions

## Rule 1: Git Is Mandatory

- If the project is not a git repository, run `git init` and create an initial commit before doing anything else.
- Never work directly on `master`. Always create a feature branch first then merge into `master`.
- Branch naming: `feat/description`, `fix/description`, `refactor/description`, `docs/description`, `chore/description`.
- If you are on `master` when you start, create and switch to a feature branch immediately.

## Rule 2: Conventional Commits

Every commit message must follow this format:

```
type: short description (imperative, lowercase, no period)
```

Valid types: `feat`, `fix`, `refactor`, `docs`, `test`, `style`, `perf`, `chore`, `ci`, `build`.

Examples:
- `feat: add customer alias persistence`
- `fix: prevent crash when delivery schedule has fewer than 6 columns`
- `docs: update README with deployment steps`

Rules:
- One logical change per commit. Do not bundle unrelated changes.
- Commit after every meaningful change, not at the end of a long session.
- If a new feature is added or changed, update `README.md` before committing.
- After every commit, check if a PR exists (`gh pr list --head <branch>`). If none exists, open one immediately via `gh pr create`.

## Rule 3: Fork From the Template — Backport Template Changes

This repository was forked from `jobdocs-plugin-template`. The following files are
**template files** owned upstream — changes that improve them must be PR'd back to
`jobdocs-plugin-template` before (or alongside) merging here:

```
.claude/CLAUDE.md
.claude/S&P.md               (format/structure only)
.claude/settings.json
.claude/hooks/pre_commit_sp_check.py
README.md                    (structure/sections, not plugin-specific content)
```

Plugin-specific logic, UI, and S&P entries are **not** backported.

## Rule 4: This Is an External Plugin — Not Part of JobDocs Core

- Do **not** add this plugin's code to `JobDocs/modules/`.
- UI path resolution must use `Path(__file__).parent` — never `sys._MEIPASS`.
- Plugin-specific settings must be surfaced through the plugin's own UI.
- Dependencies go in `requirements.txt`; JobDocs installs them automatically.

## Rule 5: Semantic Versioning

Tag releases using `vMAJOR.MINOR.PATCH` from `master` only.

- **MAJOR** — breaking changes
- **MINOR** — new features
- **PATCH** — bug fixes

### Automatic Version Bump Triggers

After every merge to `master`, count commits since the last `v*` tag:

```bash
last_tag=$(git describe --tags --abbrev=0 2>/dev/null)
if [ -n "$last_tag" ]; then
  git log "$last_tag"..master --oneline
else
  git log master --oneline
fi
```

- **5 or more `feat:` commits** → bump MINOR
- **5 or more `fix:` commits** → bump PATCH

Check after every merge. Do not wait for the user to ask.

## Rule 6: Pull Request Reviews

- Always open PRs via `gh pr create` — never merge directly to `master`.
- Read all CodeRabbit and human comments before making further changes.
- For each finding: fix it, then log it in `.claude/S&P.md` if it is a new pattern.
- Only merge after all blocking comments are resolved.

### S&P.md Entry Format

```markdown
## YYYY-MM-DD — `path/to/file.py` (short description)

**Review:** WHAT CODERABBIT FLAGGED
**Result:** outcome / resolution

### Findings

1. **Title**
   - Detail
   - Fix applied
```
