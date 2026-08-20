# Coding Best Practices & Reminders

> **Style rule:** Notes must be clear and concise — 300 characters or less each. Group by topic, not by date. Whenever a PR review (CodeRabbit or human) catches a mistake, add or amend a note here right away so it isn't repeated.

## Hooks & Subprocess Handling

**Catch specific exceptions, not `Exception`.** Broad `except Exception` in the pre-commit hook silently swallows unexpected errors; use `(OSError, subprocess.SubprocessError)` for subprocess calls and `json.JSONDecodeError` for stdin parsing.

**Resolve `git` via `shutil.which("git")`.** A literal `"git"` string can fail if git isn't on PATH in some environments; resolve the executable and bail early if not found.

## Shell Snippets in Docs

**Guard `git describe --tags --abbrev=0` for tagless repos.** It errors on a fresh repo with no tags. Capture into a variable with `2>/dev/null` and fall back to `git log master --oneline` when empty.

## DPAS Classification (module.py)

**Don't require `\b` word boundaries around embedded DPAS codes.** Source strings like `DPASDX-C2INSSHIP` have no boundary before `D` (preceded by `S`). Use `D[OX]-[A-Z]\d+` without boundaries — the greedy `\d+` already stops correctly.

**Don't gate DPAS fill on a blank-value sentinel set.** Checking Classification against `('', 'nan', 'None', '<NA>', 'NaT')` misses non-blank defaults like `0.0`. DPAS from the delivery schedule is authoritative — fill unconditionally instead.

**Guard Classification fill with an explicit empty mask, don't overwrite existing values.** A vectorized fill using only `mapped.notna()` clobbers pre-existing Classification cells. Combine with an `empty_mask` (`isna()` or `== ''`) so only blank cells get filled.

**Avoid `zip(strict=True)` — it requires Python 3.10+.** If `requirements.txt` doesn't pin Python ≥3.10, replace with an explicit length check and `raise ValueError` before zipping.

## Report Regeneration — Preserving Manual Edits (module.py)

**Every report regeneration must be additive-only toward the previous file — never delete a manual edit or highlight.** `_get_completed_jobs`/`_save_formatted_excel` carry forward *any* highlighted cell (any color, any column, not just yellow on Scheduled End Date) and *any* manually-typed value into a cell the fresh transform left blank. A cell only changes when this run has a legitimate new computed value (fresh source data, or the tool's own schedule-change/late-date coloring) for it — it is never silently blanked or un-highlighted.

**`cell.fill` from an openpyxl workbook is a `StyleProxy`, not a plain `PatternFill`.** Reassigning it directly to a cell in another (or the freshly re-saved) workbook raises `TypeError: unhashable StyleProxy`. Always `copy(cell.fill)` (from `copy import copy`) before storing/reapplying it.
