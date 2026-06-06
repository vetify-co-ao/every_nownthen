import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

os.environ.setdefault("VENDUS_API_KEY", "test-vendus-key")
os.environ.setdefault("SERVICE_ACCOUNT_KEY_PATH", "/tmp/test-service-account.json")
os.environ.setdefault("DASHY_API_KEY", "test-dashy-key")
os.environ["IXLSX_API_KEY"] = ""

import ixlsx


def workbook_bytes():
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
        workbook = Workbook()
        workbook.active["A1"] = "SKU"
        workbook.save(tmp.name)
        return Path(tmp.name).read_bytes()


class FakeResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code
        self.text = (
            content.decode("utf-8", errors="replace")
            if isinstance(content, bytes)
            else str(content)
        )

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")


class RecordingSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return self.response


class EcmTemplateTests(unittest.TestCase):
    def test_fetch_ecm_asset_downloads_export_by_node_id_without_logging_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = RecordingSession(FakeResponse(b"<html>remote</html>"))

            path = ixlsx.fetch_ecm_asset(
                "NODE123",
                "email-template.html",
                "secret-key",
                tmpdir,
                session=session,
            )

            self.assertEqual(Path(path).read_bytes(), b"<html>remote</html>")
            self.assertEqual(
                session.calls[0][0],
                "https://vcrm.lightray.cloud/api/nodes/NODE123/-/export",
            )
            self.assertEqual(session.calls[0][1], {"api_key": "secret-key"})

    def test_resolve_xlsx_template_uses_valid_ecm_workbook(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = RecordingSession(FakeResponse(workbook_bytes()))

            path = ixlsx.resolve_xlsx_template_path(
                api_key="secret-key",
                output_dir=tmpdir,
                session=session,
            )

            self.assertEqual(Path(path).name, "ecm-vetify-template.xlsx")
            self.assertTrue(Path(path).exists())

    def test_resolve_xlsx_template_falls_back_to_local_when_ecm_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            local_template = Path(tmpdir) / "local-template.xlsx"
            local_template.write_bytes(workbook_bytes())
            session = RecordingSession(FakeResponse(b"not an xlsx"))

            with patch.object(ixlsx, "XLSX_TEMPLATE_PATH", str(local_template)):
                path = ixlsx.resolve_xlsx_template_path(
                    api_key="secret-key",
                    output_dir=tmpdir,
                    session=session,
                )

            self.assertEqual(path, str(local_template))

    def test_resolve_email_template_uses_ecm_html_when_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = RecordingSession(FakeResponse(b"<p>Remote template</p>"))

            html = ixlsx.resolve_email_template_html(
                "<p>Default</p>",
                api_key="secret-key",
                output_dir=tmpdir,
                session=session,
            )

            self.assertEqual(html, "<p>Remote template</p>")

    def test_resolve_email_template_falls_back_to_local_when_ecm_unavailable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            local_template = Path(tmpdir) / "email-template.html"
            local_template.write_text("<p>Local template</p>", encoding="utf-8")
            session = RecordingSession(FakeResponse(b"", status_code=500))

            with patch.object(ixlsx, "EMAIL_TEMPLATE_PATH", str(local_template)):
                html = ixlsx.resolve_email_template_html(
                    "<p>Default</p>",
                    api_key="secret-key",
                    output_dir=tmpdir,
                    session=session,
                )

            self.assertEqual(html, "<p>Local template</p>")


if __name__ == "__main__":
    unittest.main()
