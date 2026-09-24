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

## JobBOSS Custom Reports (jobboss_reports.py)

**`openpyxl`'s `Worksheet.insert_rows()` does not shift already-existing merged-cell ranges — only cell values.** Calling `merge_cells()` right after an `insert_rows(1)`, then calling `insert_rows(1)` again, leaves the first merge stuck at its original row instead of moving down with everything else. Do every `insert_rows()` call first, then create all `merge_cells()`/cell-value writes afterward, once row numbers are final.

**Never hardcode a report's title/date range — derive it from the data.** The report title's fiscal-year range came from period-code rows already in the sheet (e.g. `"2025-DEC"`, `"2026-JAN"`); scanning column A for a `^\d{4}-` prefix and taking min/max keeps the same handler correct on next year's export with no code change.

**Auto-fitting column width from `str(cell.value)` overstates numeric cells that already have a display `number_format`.** A raw float like `114.852138793421` measures 16 characters even though its `"#,##0.00"` format renders it much shorter — exclude `int`/`float` cells from the max-length scan and size columns from header/text content instead, or numeric columns balloon far wider than what Excel actually shows.

**Excel's own AutoFit Column Width ignores hidden-row and merged-cell content — replicate both exclusions, not just one.** A hidden footnote row's long disclaimer text, and a title merged across several columns, both sit in the sheet at real cell coordinates; skip rows where `row_dimensions[row].hidden` and skip the anchor cell of any `merged_cells.ranges` entry before computing a column's max content length.

**Hiding a column (not deleting it) still needs a real stored width, applied *before* setting `hidden = True`.** Autofit and column-hide are separate `column_dimensions` attributes on the same object — order them autofit-then-hide so a hidden column keeps a sensible width for whenever it's unhidden, instead of reading back as `None`/zero.

**A flat Excel Table has no "these rows are linked" concept — sorting repositions every row independently by its own value in the sorted column.** A name row and its own totals row can end up far apart after any column sort, since most columns hold completely different values on each. A hidden group-key column (same value on every row of one section) only gives a way to *recover* the grouping via a later sort-by-key; it doesn't stop the disruptive sort from happening. To actually prevent it, disable sorting via sheet protection (see the next note) rather than relying on the key column alone.

**`openpyxl`'s `SheetProtection` booleans are inverted from what the names suggest: `True` means the action is *disallowed*, matching Excel's Protect Sheet dialog where most checkboxes are unchecked (disallowed) by default.** `sort=True` blocks sorting; `formatCells=False` (not `True`) is what *allows* formatting. Also, protecting a sheet makes every cell read-only by default (`cell.protection.locked` defaults to `True` independently of `SheetProtection`) — explicitly set `cell.protection = Protection(locked=False)` across the used range first, or the whole sheet goes read-only instead of just losing the one blocked action.

## Report Regeneration — Preserving Manual Edits (module.py)

**Every report regeneration must be additive-only toward the previous file — never delete a manual edit or highlight.** `_get_completed_jobs`/`_save_formatted_excel` carry forward *any* highlighted cell (any color, any column, not just yellow on Scheduled End Date) and *any* manually-typed value into a cell the fresh transform left blank. A cell only changes when this run has a legitimate new computed value (fresh source data, or the tool's own schedule-change/late-date coloring) for it — it is never silently blanked or un-highlighted.

**`cell.fill` from an openpyxl workbook is a `StyleProxy`, not a plain `PatternFill`.** Reassigning it directly to a cell in another (or the freshly re-saved) workbook raises `TypeError: unhashable StyleProxy`. Always `copy(cell.fill)` (from `copy import copy`) before storing/reapplying it.
