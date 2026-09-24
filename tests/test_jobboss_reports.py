"""Tests for jobboss_reports.py -- pure openpyxl logic, no Qt/JobDocs involved.

Uses small, entirely synthetic workbooks (fake employee names, fake job
numbers) built in-memory -- never the real JobBOSS exports this feature was
built against.
"""

import openpyxl
import pytest

from jobboss_reports import (
    EmployeeEfficiencyHandler,
    REPORT_HANDLERS,
    get_handler_for_filename,
)

_HEADER = [
    'WC Oper', 'Est Hrs', 'Adj E Hrs', 'Act Hrs', '% Eff', 'Quantity',
    'Est Hrs', 'Adj E Hrs', 'Act Hrs', '% Eff', None, None, None, None, None,
]


def _detail_row(job='10001', wc='CNC MILL', op='OP1'):
    return [job, wc, op, 1, 1, 1, 100, 0, None, '/', 'ea', 1, 1, 1, 100]


def _period_row(period='2024-JAN'):
    """A period-code row (indirect time), the source of the derived title's
    fiscal-year range -- e.g. "2024-JAN", "2025-DEC"."""
    return [period, 'INDIRECT', 'INDIRECT', None, None, 0, None, 1, None, '/', 'ea', None, None, 5, 0]


def _employee_block(code, name, num_detail_rows=2, periods=()):
    rows = [['Employee:', code, name, 'Type:', 'Shop', None, None, None, None, None, None, None, None, None, None]]
    for period in periods:
        rows.append(_period_row(period))
    for i in range(num_detail_rows):
        rows.append(_detail_row(job=f'{10000 + i}'))
    rows.append(['Employee Total: ', 10, 10, 100, 20, 20, 100, 5, 30, '', '', None, None, None, None])
    return rows


def _build_workbook(tmp_path, employees, filename='FAKE_EmployeeEfficiency.xlsx'):
    """employees: list of (code, name, num_detail_rows) or
    (code, name, num_detail_rows, periods) tuples."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(_HEADER)
    for entry in employees:
        code, name, count = entry[0], entry[1], entry[2]
        periods = entry[3] if len(entry) > 3 else ()
        for row in _employee_block(code, name, count, periods):
            ws.append(row)
    ws.append(['Report Total:', 99, 99, 100, 199, 199, 100, 50, 300, '', '', None, None, None, None])
    ws.append([
        '********: fake footnote for testing.', None, None, None, None, None,
        None, None, None, None, None, None, None, None, None,
    ])

    path = tmp_path / filename
    wb.save(path)
    return path


class TestGetHandlerForFilename:
    @pytest.mark.parametrize('filename', [
        'LR_EmployeeEfficiency.xlsx',
        'lr_employeeefficiency.xls',
        'LR EmployeeEfficiency 2026-09-24.xlsx',
        'EmployeeEfficiency.xlsx',
        'lr-employee-efficiency.xlsx',
    ])
    def test_matches_expected_filenames(self, filename):
        handler = get_handler_for_filename(filename)
        assert isinstance(handler, EmployeeEfficiencyHandler)

    @pytest.mark.parametrize('filename', [
        'SH_DeliverySchedule.xlsx',
        'retech_jobRpt.xls',
        'random_report.xlsx',
    ])
    def test_does_not_match_unrelated_filenames(self, filename):
        assert get_handler_for_filename(filename) is None

    def test_registry_contains_at_least_the_employee_efficiency_handler(self):
        assert any(isinstance(h, EmployeeEfficiencyHandler) for h in REPORT_HANDLERS)


class TestEmployeeEfficiencyStrip:
    """Layout produced by strip(): row 1 = title (derived from data), row 2 =
    Setup/Run group header, row 3 = column headers, row 4+ = employee blocks,
    a TOTALS marker row directly above Report Total, then the footnote.
    """

    def _load(self, path):
        wb = openpyxl.load_workbook(path)
        return wb, wb.active

    def test_no_rows_are_deleted(self, tmp_path):
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 2), ('EMPB', 'FAKE, EMPLOYEE B', 3)])
        out = tmp_path / 'out.xlsx'
        wb_before, ws_before = self._load(src)
        rows_before = ws_before.max_row
        wb_before.close()

        handler = EmployeeEfficiencyHandler()
        handler.strip(src, out)

        wb_after, ws_after = self._load(out)
        # 3 rows are inserted above everything else (title, group header,
        # TOTALS marker) -- no original row is ever removed.
        assert ws_after.max_row == rows_before + 3
        wb_after.close()

    def test_detail_rows_are_hidden_summary_rows_are_not(self, tmp_path):
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 2)])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb, ws = self._load(out)
        visibility = {}
        for row_idx in range(1, ws.max_row + 1):
            col_a = ws.cell(row=row_idx, column=1).value
            col_b = ws.cell(row=row_idx, column=2).value
            hidden = ws.row_dimensions[row_idx].hidden
            visibility[row_idx] = (col_a, col_b, hidden)

        # 1=title, 2=group header, 3=column header, 4=Employee:,
        # 5-6=detail (hidden), 7=Employee Total:, 8=TOTALS marker,
        # 9=Report Total:, 10=footnote.
        assert visibility[4][0] == 'Employee:'
        assert visibility[4][2] is False
        assert visibility[5][2] is True
        assert visibility[6][2] is True
        assert visibility[7][0].startswith('Employee Total:')
        assert visibility[7][2] is False
        assert visibility[8][1] == 'TOTALS'
        assert visibility[8][2] is False
        assert visibility[9][0] == 'Report Total:'
        assert visibility[9][2] is False
        # The footnote is disclaimer text, not a name or a total -- it stays
        # hidden behind the filter like any other detail row, even though
        # it's still one of the values listed in the filter dropdown.
        assert visibility[10][0].startswith('********')
        assert visibility[10][2] is True
        wb.close()

    def test_works_regardless_of_employee_names_or_row_counts(self, tmp_path):
        # Different names, different number of employees, different detail-row
        # counts per employee -- the handler must not hardcode any of this.
        src = _build_workbook(tmp_path, [
            ('ZZZ1', 'FAKE, PERSON ONE', 1),
            ('ZZZ2', 'FAKE, PERSON TWO', 5),
            ('ZZZ3', 'FAKE, PERSON THREE', 0),
        ])
        out = tmp_path / 'out.xlsx'
        result = EmployeeEfficiencyHandler().strip(src, out)

        # 3 Employee: + 3 Employee Total: + 1 Report Total: + 1 TOTALS
        # marker = 8 visible; the footnote joins the hidden detail rows.
        assert result.visible_rows == 8
        assert result.hidden_rows == 1 + 5 + 0 + 1  # detail rows + footnote

    def test_group_header_row_inserted_with_merged_setup_and_run_labels(self, tmp_path):
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1)])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb, ws = self._load(out)
        assert ws.cell(row=2, column=2).value == 'SETUP'
        assert ws.cell(row=2, column=5).value == 'RUN'
        merged = {str(r) for r in ws.merged_cells.ranges}
        assert 'B2:D2' in merged
        assert 'E2:G2' in merged
        wb.close()

    def test_totals_marker_inserted_directly_above_report_total(self, tmp_path):
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1), ('EMPB', 'FAKE, EMPLOYEE B', 3)])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb, ws = self._load(out)
        report_total_row = next(
            r for r in range(1, ws.max_row + 1)
            if str(ws.cell(row=r, column=1).value or '').startswith('Report Total:')
        )
        assert ws.cell(row=report_total_row - 1, column=2).value == 'TOTALS'
        assert ws.row_dimensions[report_total_row - 1].hidden is False
        wb.close()

    def test_header_row_has_unique_non_empty_labels(self, tmp_path):
        # openpyxl's Table requires unique headers -- the raw export repeats
        # "Est Hrs"/"Adj E Hrs"/"Act Hrs"/"% Eff" for both Setup and Run
        # blocks, and leaves the last five columns blank.
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1)])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb, ws = self._load(out)
        header_values = [ws.cell(row=3, column=c).value for c in range(1, ws.max_column + 1)]
        assert all(v for v in header_values), "no header cell should be blank"
        assert len(header_values) == len(set(header_values)), "header cells must be unique"
        wb.close()

    def test_table_and_filter_are_created(self, tmp_path):
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1), ('EMPB', 'FAKE, EMPLOYEE B', 1)])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb, ws = self._load(out)
        assert 'EmployeeEfficiency' in ws.tables
        table = ws.tables['EmployeeEfficiency']
        assert table.ref == f"A3:O{ws.max_row}"
        filter_values = set(table.autoFilter.filterColumn[0].filters.filter)
        assert filter_values == {
            'Employee:', 'Employee Total: ', 'Report Total:',
            '********: fake footnote for testing.',
        }
        wb.close()

    def test_never_touches_the_real_source_file(self, tmp_path):
        # strip() must be non-destructive to the input -- output goes to a
        # separate path, exactly like the Report Fixer tab's existing
        # source-vs-output separation.
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1)])
        original_bytes = src.read_bytes()
        out = tmp_path / 'out.xlsx'

        EmployeeEfficiencyHandler().strip(src, out)

        assert src.read_bytes() == original_bytes

    def test_title_and_group_header_are_styled(self, tmp_path):
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1, ['2025-JAN'])])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb, ws = self._load(out)
        title_cell = ws.cell(row=1, column=2)
        assert title_cell.font.size == 14
        assert ws.row_dimensions[1].height == 18
        group_cell = ws.cell(row=2, column=2)
        assert group_cell.font.bold is True
        assert group_cell.alignment.horizontal == 'center'
        wb.close()

    def test_columns_are_autofit_to_content(self, tmp_path):
        # A default/unset column width in openpyxl reads back as None -- every
        # column actually holding data must come out with an explicit width
        # sized to its content, not left at Excel's default.
        src = _build_workbook(tmp_path, [
            ('EMPA', 'FAKE, EMPLOYEE WITH A VERY LONG NAME INDEED', 1),
        ])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb, ws = self._load(out)
        width_a = ws.column_dimensions['A'].width
        width_c = ws.column_dimensions['C'].width  # holds the long employee name
        assert width_a is not None and width_a > 0
        assert width_c is not None and width_c > width_a
        wb.close()

    def test_autofit_ignores_merged_title_cell_text(self, tmp_path):
        # The title spans B1:G1 and is much longer than any real column B
        # value -- Excel's own AutoFit ignores merged-cell content for
        # exactly this reason, and so must this, or column B balloons to fit
        # a title that's actually rendered across six columns, not one.
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1, ['2025-JAN'])])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb, ws = self._load(out)
        title_length = len(ws.cell(row=1, column=2).value)
        width_b = ws.column_dimensions['B'].width
        assert width_b < title_length
        wb.close()

    def test_autofit_ignores_numeric_cell_precision(self, tmp_path):
        # Hours/percentage cells carry full floating-point precision (e.g.
        # 114.852138793421 in an Employee Total row) despite already having
        # their own display number_format -- str(value) on the raw float
        # would wildly overstate what Excel actually renders.
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1)])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb, ws = self._load(out)
        # Employee Total row (visible) holds long-precision floats in D/E;
        # neither column should be inflated to fit their raw repr length.
        assert ws.column_dimensions['D'].width < 15
        assert ws.column_dimensions['E'].width < 15
        wb.close()


class TestHiddenColumns:
    """Column A (the "Employee:"/"Employee Total:" label plumbing) and the
    raw export's unlabeled trailing columns are hidden, not deleted -- same
    treatment as the hidden detail rows.
    """

    def test_expected_columns_are_hidden(self, tmp_path):
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1)])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb = openpyxl.load_workbook(out)
        ws = wb.active
        hidden = {c for c, dim in ws.column_dimensions.items() if dim.hidden}
        assert hidden == {'A', 'H', 'I', 'J', 'K', 'O'}
        wb.close()

    def test_visible_columns_are_not_hidden(self, tmp_path):
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1)])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb = openpyxl.load_workbook(out)
        ws = wb.active
        for letter in ('B', 'C', 'D', 'E', 'F', 'G', 'L', 'M', 'N'):
            dim = ws.column_dimensions.get(letter)
            assert dim is None or not dim.hidden, f"column {letter} should not be hidden"
        wb.close()

    def test_hidden_column_still_has_a_real_width(self, tmp_path):
        # Hiding a column via Excel doesn't erase its stored width -- only
        # deleting it would. Confirms hidden columns go through the same
        # autofit pass as visible ones, not a zero/blank width.
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1)])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb = openpyxl.load_workbook(out)
        ws = wb.active
        assert ws.column_dimensions['A'].width is not None
        assert ws.column_dimensions['A'].width > 0
        wb.close()


class TestDerivedTitle:
    """The report title (row 1) is computed from the fiscal-year range found
    in the data's period-code rows -- never a hardcoded year, so this same
    handler keeps working correctly on next year's export without a code change.
    """

    def _title(self, tmp_path, employees):
        src = _build_workbook(tmp_path, employees)
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)
        wb = openpyxl.load_workbook(out)
        title = wb.active.cell(row=1, column=2).value
        wb.close()
        return title

    def test_single_year(self, tmp_path):
        title = self._title(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1, ['2025-JAN', '2025-DEC'])])
        assert title == 'Employee Efficiency 2025'

    def test_year_range_across_employees(self, tmp_path):
        title = self._title(tmp_path, [
            ('EMPA', 'FAKE, EMPLOYEE A', 1, ['2024-NOV']),
            ('EMPB', 'FAKE, EMPLOYEE B', 1, ['2025-JAN', '2025-DEC']),
        ])
        assert title == 'Employee Efficiency 2024 - 2025'

    def test_no_period_rows_falls_back_to_generic_title(self, tmp_path):
        title = self._title(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1)])
        assert title == 'Employee Efficiency'

    def test_title_merged_across_setup_and_run_columns(self, tmp_path):
        src = _build_workbook(tmp_path, [('EMPA', 'FAKE, EMPLOYEE A', 1, ['2025-JAN'])])
        out = tmp_path / 'out.xlsx'
        EmployeeEfficiencyHandler().strip(src, out)

        wb = openpyxl.load_workbook(out)
        ws = wb.active
        merged = {str(r) for r in ws.merged_cells.ranges}
        assert 'B1:G1' in merged
        wb.close()
