"""
JobBOSS Custom Reports — strip a raw JobBOSS custom-report export down to
its summary lines by hiding the detail rows inside an Excel Table/AutoFilter.

Nothing is deleted: every detail row is still in the sheet, just hidden, so
clearing the filter in Excel brings it all back. This mirrors how a person
would do it by hand (Insert > Table, then filter column A down to just the
label rows) rather than actually removing data. Sorting is disabled (via
unpassworded sheet protection) since a flat table sort would reposition each
row independently and scatter a summary row (e.g. "Employee Total:") away
from the detail/name rows it belongs with.

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
from openpyxl.styles import Alignment, Font, Protection
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
    grand total) -- the individual per-job/work-center detail lines, the
    footnote, and a handful of not-useful-here raw columns are all hidden,
    not deleted.

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

    # 1-indexed columns hidden (not deleted -- same hide-don't-delete
    # treatment as rows) in the stripped output: column A carries the
    # "Employee:"/"Employee Total:" label plumbing the filter runs on, not
    # something worth reading once the employee code/name in B/C are right
    # there. The raw export's unlabeled trailing columns (H-O) are left
    # visible -- not worth the upkeep of tracking which ones to hide for
    # columns nobody reads anyway.
    _HIDDEN_COLUMNS = {1}

    # Rows shown by default. The footnote is deliberately not one of these --
    # it's disclaimer text, not a name or a total, so it stays hidden behind
    # the filter like any other detail row even though it's still one of the
    # values listed in the filter dropdown (see _FOOTNOTE_PREFIX below).
    _VISIBLE_PREFIXES = ('Employee:', 'Employee Total:', 'Report Total:')
    _FOOTNOTE_PREFIX = '********'

    _TOTALS_LABEL = 'TOTALS'
    _YEAR_PATTERN = re.compile(r'^(\d{4})-')

    # Header for the appended group-key column (see strip()) -- must be
    # unique against every entry in _HEADER_ROW for openpyxl's Table to
    # accept it.
    _KEY_COLUMN_HEADER = 'Employee Key'

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

    @staticmethod
    def _autofit_columns(ws, last_col: int) -> None:
        """Size each column (1..last_col) to fit its widest *visible* cell,
        capped at 50 --
        matches the Fix & Export tab's own auto-fit behavior. Run after every
        value (including the relabeled headers and title/group rows) is in
        place, and after row visibility has already been decided.

        Three exclusions, all because a value is on the sheet but never meant
        to set a column's width:
        - Hidden rows: the footnote is genuinely long (~85 characters) and
          spans columns A-C -- without this, autofit blows those columns out
          to fit disclaimer text that's tucked behind the filter, not the
          actual job/employee data anyone is meant to read at a glance.
        - The anchor cell of any merged range (e.g. the title spanning
          B1:G1): Excel's own AutoFit Column Width ignores merged-cell
          content for exactly this reason -- a long title would otherwise
          blow out a single column to fit text that's actually rendered
          across several columns. MergedCell followers already read as
          value=None, so only the anchor needs explicit exclusion.
        - Numeric cells: hours/percentage columns carry full floating-point
          precision (e.g. 114.852138793421) despite each already having its
          own display number_format (e.g. "#,##0.00") that renders them
          much shorter -- str(value) on the raw float wildly overstates
          what Excel actually shows, so numbers are left out and the
          column instead sizes to its header/text content.
        """
        merged_anchors = {(rng.min_row, rng.min_col) for rng in ws.merged_cells.ranges}
        for col_idx in range(1, last_col + 1):
            column_letter = get_column_letter(col_idx)
            max_length = 0
            for cell in ws[column_letter]:
                if ws.row_dimensions[cell.row].hidden:
                    continue
                if (cell.row, cell.column) in merged_anchors:
                    continue
                if isinstance(cell.value, (int, float)):
                    continue
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

    @staticmethod
    def _disable_sorting(ws, last_row: int, last_col: int) -> None:
        """Block Excel's Sort commands (ribbon, and the Sort options inside
        the Table/AutoFilter dropdown) via sheet protection -- a hidden key
        column only gives a way to *recover* from a sort scattering an
        employee's Employee: row away from their own Employee Total: row;
        it can't stop the sort from happening in the first place. Disabling
        sort outright is the only way to actually prevent it.

        No password is set: this is meant to stop an accidental/casual sort
        click, not to secure the file. Anyone who deliberately needs to sort
        can still do so via Review > Unprotect Sheet.

        Every other protectable action (formatting, filtering, inserting/
        deleting rows or columns, etc.) is explicitly left allowed, and
        every existing cell is explicitly unlocked first -- a freshly
        protected sheet defaults every other action to "disallowed" and
        every cell to "locked" unless told otherwise, which would silently
        make the whole sheet read-only instead of just blocking sort.
        """
        unlocked = Protection(locked=False)
        for row in ws.iter_rows(min_row=1, max_row=last_row, min_col=1, max_col=last_col):
            for cell in row:
                cell.protection = unlocked

        ws.protection.sheet = True
        ws.protection.sort = True
        ws.protection.formatCells = False
        ws.protection.formatColumns = False
        ws.protection.formatRows = False
        ws.protection.insertColumns = False
        ws.protection.insertRows = False
        ws.protection.insertHyperlinks = False
        ws.protection.deleteColumns = False
        ws.protection.deleteRows = False
        ws.protection.autoFilter = False
        ws.protection.pivotTables = False
        ws.protection.objects = False
        ws.protection.scenarios = False

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
        if ws is None:
            raise ValueError(f"{input_path} has no active worksheet")
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
        title_cell = ws.cell(row=1, column=title_start_col, value=title)
        title_cell.font = Font(name='Arial', size=14)
        title_cell.alignment = Alignment(horizontal='left')
        ws.row_dimensions[1].height = 18
        if title_end_col > title_start_col:
            ws.merge_cells(start_row=1, start_column=title_start_col, end_row=1, end_column=title_end_col)

        # Row 2: Setup/Run group header.
        for start_col, label in self._GROUP_HEADERS.items():
            end_col = min(start_col + 2, max_col)
            group_cell = ws.cell(row=2, column=start_col, value=label)
            group_cell.font = Font(name='Arial', size=10, bold=True)
            group_cell.alignment = Alignment(horizontal='center')
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

        # An appended, hidden group-key column: every row belonging to one
        # employee's section (their Employee: row, all its detail rows, and
        # their Employee Total: row) gets that employee's code written here.
        # Sorting is disabled outright below (_disable_sorting()) so this
        # isn't the primary defense against an employee's Employee: row
        # (e.g. row 4) getting scattered away from their own Employee Total:
        # row (e.g. row 332) -- it's the fallback for if the sheet is ever
        # deliberately unprotected and sorted anyway: sorting BY this key
        # (a stable sort, so a section's original relative order is kept)
        # re-groups every section correctly, rather than the pairing being
        # only ever inferable from row position.
        key_col = max_col + 1
        key_col_letter = get_column_letter(key_col)
        ws.cell(row=header_row, column=key_col, value=self._KEY_COLUMN_HEADER)

        # Hide every data row whose column-A label isn't a summary line --
        # this is the actual "stripping". Nothing is deleted. The TOTALS
        # marker row has no column-A label of its own (its text is in column
        # B), so it's excluded here and forced visible explicitly below.
        filter_values = set()
        visible_count = 0
        hidden_count = 0
        current_key = ''
        for row_idx in range(header_row + 1, ws.max_row + 1):
            if row_idx == totals_row:
                ws.cell(row=row_idx, column=key_col, value=None)
                continue
            value = ws.cell(row=row_idx, column=1).value
            text = str(value).strip() if value is not None else ''
            if text == 'Employee:':
                current_key = str(ws.cell(row=row_idx, column=2).value or '').strip()
            elif text.startswith('Report Total:') or text.startswith(self._FOOTNOTE_PREFIX):
                current_key = ''
            ws.cell(row=row_idx, column=key_col, value=current_key or None)

            is_shown = self._is_visible_label(value)
            if is_shown or text.startswith(self._FOOTNOTE_PREFIX):
                filter_values.add(str(value))
            if is_shown:
                visible_count += 1
                ws.row_dimensions[row_idx].hidden = False
            else:
                hidden_count += 1
                ws.row_dimensions[row_idx].hidden = True
        if totals_row is not None:
            ws.row_dimensions[totals_row].hidden = False
            visible_count += 1

        # Wrap the header + data rows (plus the appended key column) in an
        # Excel Table with an AutoFilter pre-set to the summary-line values
        # actually present in this run -- reopening in Excel shows the
        # filter dropdown already scoped correctly, not just cosmetically-
        # hidden rows.
        table_ref = f"A{header_row}:{key_col_letter}{ws.max_row}"
        table = Table(displayName='EmployeeEfficiency', ref=table_ref)
        table.tableStyleInfo = TableStyleInfo(
            name='TableStyleLight1', showFirstColumn=False, showLastColumn=False,
            showRowStripes=True, showColumnStripes=False,
        )
        table.autoFilter = AutoFilter(
            ref=table_ref,
            filterColumn=[FilterColumn(colId=0, filters=Filters(filter=sorted(filter_values)))],
        )
        ws.add_table(table)

        self._autofit_columns(ws, key_col)

        # Hide (not delete) the columns not meaningful for this summary view,
        # after autofit so a hidden column still remembers a real width --
        # exactly like a row a person hides in Excel rather than deleting.
        # The key column is plumbing, not something to read, so it's hidden
        # the same way -- still selectable as a sort column by header name
        # if the sheet is ever deliberately unprotected (see
        # _disable_sorting()) to sort it after all.
        for col_idx in (*self._HIDDEN_COLUMNS, key_col):
            ws.column_dimensions[get_column_letter(col_idx)].hidden = True

        self._disable_sorting(ws, ws.max_row, key_col)

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
