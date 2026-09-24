"""
JobBOSS Custom Reports — strip a raw JobBOSS custom-report export down to
its summary lines by hiding the detail rows inside an Excel Table/AutoFilter.

Nothing is deleted: every detail row is still in the sheet, just hidden, so
clearing the filter in Excel brings it all back. This mirrors how a person
would do it by hand (Insert > Table, then filter column A down to just the
label rows) rather than actually removing data.

Each JobBOSS custom report type has its own fixed column layout (that's the
report definition in JobBOSS, not something that varies run to run), so a
new report type is supported by adding another ReportHandler subclass and
registering it in REPORT_HANDLERS -- nothing else needs to change.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.filters import AutoFilter, FilterColumn, Filters
from openpyxl.worksheet.table import Table, TableStyleInfo


@dataclass
class StripResult:
    visible_rows: int
    hidden_rows: int
    output_path: Path


class ReportHandler:
    """Interface for a single JobBOSS custom-report stripping handler."""

    report_id: str = ''
    display_name: str = ''

    def matches(self, filename: str) -> bool:
        """Return True if this handler knows how to strip the given filename."""
        raise NotImplementedError

    def strip(self, input_path: Path, output_path: Path) -> StripResult:
        """Read input_path, write the stripped workbook to output_path."""
        raise NotImplementedError


class EmployeeEfficiencyHandler(ReportHandler):
    """Strips a JobBOSS LR_EmployeeEfficiency export down to just each
    employee's name line and their "Employee Total" line (plus the report
    grand total and its footnote) -- the individual per-job/work-center
    detail lines are hidden, not deleted.

    The report's column layout is fixed (Setup hours in columns B-D, Run
    hours in columns E-G) -- only the row *count*, the employee names, and
    the fiscal-year period covered change between runs. Row visibility is
    decided by matching the label text in column A ("Employee:",
    "Employee Total:", "Report Total:", the footnote), never by a specific
    employee name, and the title row's year range is read from the data's
    own period-code rows ("2025-DEC", "2026-JAN", ...) rather than
    hardcoded -- so this same handler keeps working, unmodified, on next
    year's export.
    """

    report_id = 'lr_employee_efficiency'
    display_name = 'Employee Efficiency (LR_EmployeeEfficiency)'

    # 1-indexed start column -> group label, each spanning 3 columns (matches
    # the report's Setup/Run block layout).
    _GROUP_HEADERS = {2: 'SETUP', 5: 'RUN'}

    _HEADER_ROW = [
        'WC Oper', 'Adj E Hrs', 'Act Hrs', ' % Eff ” ', 'Adj E Hrs2', 'Act Hrs2', '% Eff ”',
        'Column2', 'Column1', 'Column3', 'Column6', 'Column7', 'Column8', 'Column9', 'Column10',
    ]

    _VISIBLE_PREFIXES = ('Employee:', 'Employee Total:', 'Report Total:', '********')

    _TOTALS_LABEL = 'TOTALS'
    _YEAR_PATTERN = re.compile(r'^(\d{4})-')

    def matches(self, filename: str) -> bool:
        stem = Path(filename).stem.lower()
        for ch in ('_', ' ', '-'):
            stem = stem.replace(ch, '')
        return 'employeeefficiency' in stem

    @classmethod
    def _is_visible_label(cls, value) -> bool:
        if value is None:
            return False
        text = str(value).strip()
        return any(text.startswith(prefix) for prefix in cls._VISIBLE_PREFIXES)

    @classmethod
    def _derive_title(cls, ws) -> str:
        """Build the report title from the fiscal-year range actually present
        in the data (period-code rows like "2025-DEC", "2026-JAN" in column
        A), rather than a hardcoded year that would go stale on every future
        run of this same report.
        """
        years = set()
        for row_idx in range(1, ws.max_row + 1):
            value = ws.cell(row=row_idx, column=1).value
            if value is None:
                continue
            match = cls._YEAR_PATTERN.match(str(value).strip())
            if match:
                years.add(int(match.group(1)))
        if not years:
            return 'Employee Efficiency'
        if len(years) == 1:
            return f'Employee Efficiency {years.pop()}'
        return f'Employee Efficiency {min(years)} - {max(years)}'

    def strip(self, input_path: Path, output_path: Path) -> StripResult:
        wb = load_workbook(input_path)
        ws = wb.active
        max_col = ws.max_column

        # Derive the title before any row is inserted/moved.
        title = self._derive_title(ws)

        # Insert a TOTALS marker directly above the Report Total row (found
        # in original, pre-insertion coordinates) before anything else shifts.
        report_total_row = None
        for row_idx in range(1, ws.max_row + 1):
            value = ws.cell(row=row_idx, column=1).value
            if value is not None and str(value).strip().startswith('Report Total:'):
                report_total_row = row_idx
                break
        if report_total_row is not None:
            ws.insert_rows(report_total_row)
            totals_row = report_total_row
        else:
            totals_row = None

        # Insert the Setup/Run group-header row, then the title row, above
        # the original column-header row -- both always land at row 1/2,
        # pushing every row below (including totals_row) down by one each.
        #
        # Deliberately no merge_cells() calls interleaved with these inserts:
        # openpyxl's insert_rows() does NOT shift already-existing merged-cell
        # ranges, only cell values -- merging into row 1 and then inserting
        # another row above it again leaves that merge stuck at row 1 instead
        # of moving to row 2. All merges are created below, only after every
        # insert has happened and row numbers are final.
        ws.insert_rows(1)
        if totals_row is not None:
            totals_row += 1
        ws.insert_rows(1)
        if totals_row is not None:
            totals_row += 1

        # Row 1: title, spanning the same columns as the Setup+Run blocks
        # combined.
        title_start_col = min(self._GROUP_HEADERS)
        title_end_col = min(max(self._GROUP_HEADERS) + 2, max_col)
        ws.cell(row=1, column=title_start_col, value=title)
        if title_end_col > title_start_col:
            ws.merge_cells(start_row=1, start_column=title_start_col, end_row=1, end_column=title_end_col)

        # Row 2: Setup/Run group header.
        for start_col, label in self._GROUP_HEADERS.items():
            end_col = min(start_col + 2, max_col)
            ws.cell(row=2, column=start_col, value=label)
            if end_col > start_col:
                ws.merge_cells(start_row=2, start_column=start_col, end_row=2, end_column=end_col)

        # TOTALS marker (single cell, no merge needed).
        if totals_row is not None:
            ws.cell(row=totals_row, column=2, value=self._TOTALS_LABEL)

        # Relabel the column-header row (now row 3) with fixed, unique names.
        # openpyxl's Table requires unique, non-empty headers, and the raw
        # export repeats "Est Hrs"/"Adj E Hrs"/"Act Hrs"/"% Eff" for both the
        # Setup and Run blocks.
        header_row = 3
        for col_idx, label in enumerate(self._HEADER_ROW[:max_col], start=1):
            ws.cell(row=header_row, column=col_idx, value=label)

        # Hide every data row whose column-A label isn't a summary line --
        # this is the actual "stripping". Nothing is deleted. The TOTALS
        # marker row has no column-A label of its own (its text is in column
        # B), so it's excluded here and forced visible explicitly below.
        visible_values = set()
        visible_count = 0
        hidden_count = 0
        for row_idx in range(header_row + 1, ws.max_row + 1):
            if row_idx == totals_row:
                continue
            value = ws.cell(row=row_idx, column=1).value
            if self._is_visible_label(value):
                visible_count += 1
                visible_values.add(str(value))
                ws.row_dimensions[row_idx].hidden = False
            else:
                hidden_count += 1
                ws.row_dimensions[row_idx].hidden = True
        if totals_row is not None:
            ws.row_dimensions[totals_row].hidden = False
            visible_count += 1

        # Wrap the header + data rows in an Excel Table with an AutoFilter
        # pre-set to the summary-line values actually present in this run --
        # reopening in Excel shows the filter dropdown already scoped
        # correctly, not just cosmetically-hidden rows.
        last_col_letter = get_column_letter(max_col)
        table_ref = f"A{header_row}:{last_col_letter}{ws.max_row}"
        table = Table(displayName='EmployeeEfficiency', ref=table_ref)
        table.tableStyleInfo = TableStyleInfo(
            name='TableStyleLight1', showFirstColumn=False, showLastColumn=False,
            showRowStripes=True, showColumnStripes=False,
        )
        table.autoFilter = AutoFilter(
            ref=table_ref,
            filterColumn=[FilterColumn(colId=0, filters=Filters(filter=sorted(visible_values)))],
        )
        ws.add_table(table)

        output_path = Path(output_path)
        wb.save(output_path)
        wb.close()

        return StripResult(visible_rows=visible_count, hidden_rows=hidden_count, output_path=output_path)


REPORT_HANDLERS: List[ReportHandler] = [
    EmployeeEfficiencyHandler(),
]


def get_handler_for_filename(filename: str) -> Optional[ReportHandler]:
    """Return the first registered handler that recognizes this filename, or None."""
    for handler in REPORT_HANDLERS:
        if handler.matches(filename):
            return handler
    return None
