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

## Merge Key Normalization (module.py)

**Any column used as a merge/lookup key needs float-suffix stripping, not just the ones that broke first.** Excel/pandas upcasts a numeric column (Job ID, Line, PO) to float64 when any cell is blank, producing `'12345.0'` on `str()`. If the two sides of a join don't upcast identically, the merge silently drops matches. `Line` had this fix; `Job ID` and `Customer PO Number` didn't — `Job ID` is the delivery-schedule merge key for Promise Date, so mismatched rows came back with Promise Date NaN, and `Customer PO Number` feeds `_track_schedule_changes` history keys. Strip `\.0$` on every ID-like merge key, symmetrically on both sides of the join.

**Drop rows with a blank merge key before joining — don't let `'nan'` match `'nan'`.** `astype(str)` turns a missing/NaN key into the literal string `'nan'` on both sides of a merge, so a delivery-schedule row with no Job ID would match every source row that also has a blank Job ID and hand its Promise Date to all of them. Filter out `''`/`'nan'`/`'None'` keys from the lookup table before merging, not just from dict-building loops.
