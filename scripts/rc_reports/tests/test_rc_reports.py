import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

os.environ.setdefault("DASHY_API_KEY", "test-dashy-key")
os.environ.setdefault("RC_REPORTS_EMAIL_TO", "recipient@example.com")
os.environ.setdefault("SERVICE_ACCOUNT_KEY_PATH", "/tmp/test-service-account.json")

import rc_reports


class PeriodTests(unittest.TestCase):
    def test_calculate_period_uses_28_day_inclusive_windows(self):
        base_date = dt.date(2026, 1, 1)

        period = rc_reports.calculate_period(2, base_date)

        self.assertEqual(period.start, dt.date(2026, 1, 29))
        self.assertEqual(period.end, dt.date(2026, 2, 25))

    def test_calculate_period_rejects_out_of_range_number(self):
        with self.assertRaises(ValueError):
            rc_reports.calculate_period(14, dt.date(2026, 1, 1))

    def test_period_start_date_uses_month_day_with_current_year(self):
        start = rc_reports.period_start_date_for_year(2027, "01-01")

        self.assertEqual(start, dt.date(2027, 1, 1))

    def test_auto_mode_runs_period_1_thirty_days_after_start_day(self):
        period = rc_reports.calculate_auto_period(
            dt.date(2026, 1, 31), "01-01"
        )

        self.assertEqual(period, rc_reports.ReportPeriod(1, dt.date(2026, 1, 1), dt.date(2026, 1, 28)))

    def test_auto_mode_runs_period_6_on_june_20(self):
        period = rc_reports.calculate_auto_period(
            dt.date(2026, 6, 20), "01-01"
        )

        self.assertEqual(period, rc_reports.ReportPeriod(6, dt.date(2026, 5, 21), dt.date(2026, 6, 17)))

    def test_auto_mode_runs_period_13_on_december_30(self):
        period = rc_reports.calculate_auto_period(
            dt.date(2026, 12, 30), "01-01"
        )

        self.assertEqual(period, rc_reports.ReportPeriod(13, dt.date(2026, 12, 3), dt.date(2026, 12, 30)))

    def test_auto_mode_returns_none_when_no_report_is_scheduled(self):
        self.assertIsNone(
            rc_reports.calculate_auto_period(dt.date(2026, 2, 1), "01-01")
        )


class FakeDashyClient:
    def __init__(self):
        self.products = [
            {
                "sku": "RC-Z",
                "product_name": "ROYAL CANIN ZETA 2KG",
                "brand": "Royal Canin",
                "rc_weight": "2",
            },
            {
                "sku": "RC-A",
                "product_name": "ROYAL CANIN ALPHA 1.5KG",
                "brand": "Royal Canin",
                "rc_weight": 1.5,
            },
            {
                "sku": "RC-NO-MOVE",
                "product_name": "ROYAL CANIN NO MOVE 4KG",
                "brand": "Royal Canin",
                "rc_weight": 4,
            },
            {
                "sku": "VI-OTHER",
                "product_name": "OTHER BRAND PRODUCT",
                "brand": "Virbac",
                "rc_weight": None,
            },
        ]
        self.sales_by_sku = {
            "RC-Z": {"revenue_aoa": 91213.1, "units_sold": 3},
            "RC-A": {"revenue_aoa": 182426.2, "units_sold": 4},
            "RC-NO-MOVE": {"revenue_aoa": 0, "units_sold": 0},
        }
        self.stock = {
            "RC-Z": 0,
            "RC-A": 8,
            "RC-NO-MOVE": 0,
        }

    def list_products(self):
        return self.products

    def get_sales_by_sku(self, start_date, end_date, brand="Royal Canin", limit=100):
        return self.sales_by_sku

    def get_stock_on_date(self, sku, snapshot_date):
        return self.stock[sku]

    def get_usd_rate_on_date(self, snapshot_date):
        return 912.131


class ReportRowsTests(unittest.TestCase):
    def test_build_report_rows_filters_sorts_and_calculates_values(self):
        period = rc_reports.ReportPeriod(1, dt.date(2026, 1, 1), dt.date(2026, 1, 28))

        rows = rc_reports.build_report_rows(FakeDashyClient(), period)

        self.assertEqual([row.sku for row in rows], ["RC-A", "RC-Z"])
        self.assertEqual(rows[0].product_name, "ROYAL CANIN ALPHA 1.5KG")
        self.assertEqual(rows[0].stock_on_hand, 8)
        self.assertAlmostEqual(rows[0].sales_usd, 200.0, places=2)
        self.assertAlmostEqual(rows[0].sales_kg, 6.0)
        self.assertEqual(rows[1].stock_on_hand, 0)
        self.assertAlmostEqual(rows[1].sales_usd, 100.0, places=2)
        self.assertAlmostEqual(rows[1].sales_kg, 6.0)


class WorkbookTests(unittest.TestCase):
    def test_write_report_copies_template_and_writes_rows(self):
        period = rc_reports.ReportPeriod(1, dt.date(2026, 1, 1), dt.date(2026, 1, 28))
        rows = [
            rc_reports.ReportRow("RC-A", "ROYAL CANIN ALPHA", 8, 200.0, 6.0, 4, 182426.2),
            rc_reports.ReportRow("RC-Z", "ROYAL CANIN ZETA", 0, 100.0, 6.0, 3, 91213.1),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = rc_reports.write_report_workbook(
                rc_reports.XLSX_TEMPLATE_PATH,
                Path(tmpdir),
                period,
                rows,
            )

            workbook = load_workbook(output_path)
            sheet = workbook[rc_reports.EXCEL_SHEET_NAME]

        self.assertEqual(sheet["A1"].value, "SKU")
        self.assertEqual(sheet["A2"].value, "RC-A")
        self.assertEqual(sheet["B2"].value, "ROYAL CANIN ALPHA")
        self.assertEqual(sheet["C2"].value, 8)
        self.assertEqual(sheet["D2"].value, 200.0)
        self.assertEqual(sheet["E2"].value, 6.0)
        self.assertEqual(sheet["A3"].value, "RC-Z")
        self.assertIsNone(sheet["A4"].value)


class EmailMessageTests(unittest.TestCase):
    def test_build_email_message_uses_to_header_and_attachment(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx") as attachment:
            attachment.write(b"workbook")
            attachment.flush()

            message = rc_reports.build_email_message(
                ["recipient@example.com"],
                "Royal Canin Report P1",
                "<p>Hello</p>",
                Path(attachment.name),
            )

        self.assertEqual(message["to"], "recipient@example.com")
        self.assertEqual(message["reply-to"], rc_reports.REPLY_TO)
        self.assertEqual(message["from"], rc_reports.EMAIL_FROM)
        self.assertEqual(message["subject"], "Royal Canin Report P1")
        self.assertEqual(len(message.get_payload()), 2)


class DashyClientTests(unittest.TestCase):
    def test_get_stock_on_date_returns_zero_when_snapshot_date_missing(self):
        client = rc_reports.DashyClient("test-key", session=FakeSession())

        stock = client.get_stock_on_date("RC-A", dt.date(2026, 1, 28))

        self.assertEqual(stock, 0)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = "{}"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        return FakeResponse({"x": ["2026-01-27"], "series": {"stock_qty": [12]}})


if __name__ == "__main__":
    unittest.main()
