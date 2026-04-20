# jobdocs-report-fixer

An external JobDocs plugin that transforms Excel job reports to match a template layout. Tracks schedule changes, adds notes for date modifications, and exports formatted Excel files with highlighting.

## Features

- Load a source job report (e.g., `retech_jobRpt.xls`) and a delivery schedule
- Map source columns to a template layout automatically
- Preview customer mappings and resolve unmatched customers via alias persistence
- Export a fixed, formatted `.xlsx` with highlighted changes and date-change notes

## Requirements

- JobDocs with external plugin support
- Python packages: `pandas`, `openpyxl` (installed automatically via `requirements.txt`)

## Setup

1. Clone or copy this folder alongside `JobDocs/` (sibling directory):
   ```text
   H:\Jobdocs\
   ├── JobDocs\
   └── jobdocs-report-fixer\
   ```
2. In JobDocs Settings, set **Plugins Folder** to the parent directory (`H:\Jobdocs\`).
3. Restart JobDocs — the **Report Fixer** tab appears automatically.

## Usage

1. **Template Path** — Browse to your `.xlsx` template file.
2. **Source Report** — Browse to the source job report (`.xls` / `.xlsx`).
3. **Delivery Schedule** — Browse to the delivery schedule file.
4. **Customer** — Select a customer from the detected list.
5. **Preview** — Review the column mapping and customer matches.
6. **Fix & Export** — Generate the formatted output file.

## Plugin Structure

```text
jobdocs-report-fixer/
├── __init__.py
├── module.py          # ReportingModule(BaseModule)
├── requirements.txt
├── ui/
│   └── report_tab.ui
└── .claude/
    ├── CLAUDE.md
    ├── S&P.md
    ├── settings.json
    └── hooks/
        └── pre_commit_sp_check.py
```

## Development

This plugin is forked from [jobdocs-plugin-template](../jobdocs-plugin-template).
Changes to shared template files (`.claude/CLAUDE.md`, `.claude/S&P.md` structure,
`settings.json`, `hooks/`, `README.md` structure) must be PR'd back to the template
repo before or alongside merging here.

See `.claude/CLAUDE.md` for the full branching, commit, and review workflow.

> **Note:** The pre-commit S&P hook (`.claude/hooks/pre_commit_sp_check.py`) is triggered
> via Claude Code's `PreToolUse` hook, not by a standard `git commit` hook. It runs when
> Claude Code executes a `git commit` bash command. Plain `git commit` from a terminal
> bypasses it by design — the check is Claude-only.
