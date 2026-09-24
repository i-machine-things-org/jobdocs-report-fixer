# jobdocs-report-fixer

An external JobDocs plugin providing the **Report Fixer** tab, with two independent workflows:

- **Fix & Export** — transforms Excel job reports to match a template layout. Tracks schedule changes, adds notes for date modifications, and exports formatted Excel files with highlighting.
- **JobBOSS Custom Reports** — strips a raw JobBOSS custom-report export (e.g. `LR_EmployeeEfficiency.xlsx`) down to its summary lines by hiding the detail rows in an Excel Table/AutoFilter. Nothing is deleted, so clearing the filter in Excel brings the detail back.

## Features

- Load a source job report (e.g., `retech_jobRpt.xls`) and a delivery schedule
- Map source columns to a template layout automatically
- Preview customer mappings and resolve unmatched customers via alias persistence
- Export a fixed, formatted `.xlsx` with highlighted changes and date-change notes
- Regenerating a report never erases manual work: any cell highlighting (any color, any column) and any value typed by hand into a blank cell on the last report carry forward automatically
- **JobBOSS Custom Reports** — pick a report type, browse to the raw export, and strip it down to its "Employee:" / "Employee Total:" / "Report Total:" summary lines. New report types are added by registering another handler in `jobboss_reports.py`; nothing else needs to change.

## Requirements

- JobDocs with external plugin support
- Python packages: `pandas`, `openpyxl`, `xlrd` (installed automatically via `requirements.txt`)

## Setup

1. Clone or copy this folder into JobDocs' plugins directory, so `module.py` sits directly inside it:
   ```text
   <JobDocs>/plugins/
   └── jobdocs-report-fixer/
       └── module.py
   ```
   Where `<JobDocs>/plugins/` is:
   - **Running from source**: the `plugins/` folder alongside `main.py` in the JobDocs repo checkout.
   - **Embedded/installed build**: `{app}/plugins/`, a sibling of the `app/` and `runtime/` folders.
   - **Flatpak**: `$XDG_DATA_HOME/plugins` (falls back to `~/.var/app/<flatpak id>/data/plugins`).

   A directory junction/symlink to this repo works fine and is the easiest way to develop against
   a local JobDocs checkout without copying files on every change.
2. Restart JobDocs — the **Report Fixer** tab appears automatically.

## Usage

### Fix & Export

1. **Template Path** — Browse to your `.xlsx` template file.
2. **Source Report** — Browse to the source job report (`.xls` / `.xlsx`).
3. **Delivery Schedule** — Browse to the delivery schedule file.
4. **Customer** — Select a customer from the detected list.
5. **Preview** — Review the column mapping and customer matches.
6. **Fix & Export** — Generate the formatted output file.

### JobBOSS Custom Reports

1. **Report Type** — Select the report type (auto-selected once a matching raw file is chosen).
2. **Raw Report File** — Drag and drop the raw JobBOSS export onto the tab, or click Browse
   (`.xls` / `.xlsx`).
3. **Strip Report...** — Prompts with a Save As dialog (defaulting to `<name>.stripped.xlsx` next
   to the source), then hides every row except the summary lines (job/work-center detail rows are
   preserved on the sheet, just hidden behind the table filter) and saves the result there.
4. **Open Output Folder** — Jump straight to the saved file.

## Plugin Structure

```text
jobdocs-report-fixer/
├── __init__.py
├── module.py            # ReportingModule(BaseModule) -- both inner tabs
├── jobboss_reports.py   # JobBOSS Custom Reports transform logic (no Qt dependency)
├── requirements.txt
├── ui/
│   └── reporting_tab.ui # Fix & Export tab layout (JobBOSS Custom Reports is built in Python)
├── tests/
│   └── test_jobboss_reports.py
└── .claude/
    ├── CLAUDE.md
    ├── CODING_NOTES.md
    ├── settings.json
    └── hooks/
        └── pre_commit_sp_check.py
```

## Development

This plugin is forked from [jobdocs-plugin-template](https://github.com/i-machine-things/jobdocs-plugin-template).
Changes to shared template files (`.claude/CLAUDE.md`,
`settings.json`, `hooks/`, `README.md` structure) must be PR'd back to the template
repo before or alongside merging here.

See `.claude/CLAUDE.md` for the full branching, commit, and review workflow.

> **Note:** The pre-commit coding-notes hook (`.claude/hooks/pre_commit_sp_check.py`) is triggered
> via Claude Code's `PreToolUse` hook, not by a standard `git commit` hook. It runs when
> Claude Code executes a `git commit` bash command. Plain `git commit` from a terminal
> bypasses it by design — the check is Claude-only.
