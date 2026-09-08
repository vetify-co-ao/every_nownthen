import datetime as dt
from pathlib import Path
from unittest.mock import patch

import pytest

import ixlsx
from models import BulletinData, Product


def config(tmp_path):
    return ixlsx.Config(
        vendus_api_key="vendus",
        vcrm_api_key="vcrm",
        vpim_api_key="vpim",
        dashy_api_key="",
        vsco_api_key="",
        service_account_key_path=None,
        output_dir=tmp_path,
        test_emails=["test@example.com"],
    )


def bulletin(publication_date):
    return BulletinData(
        publication_date=publication_date,
        issue_number=ixlsx.issue_number(publication_date),
        recipients=["client@example.com"],
        products=[
            Product(
                sku="SKU",
                slug="sku",
                title="Product",
                description="",
                availability="EM STOCK",
                net_price=10,
                vat_rate=0,
                expiry=None,
                categories="Category",
                subcategories="",
                brand="Brand",
                department="Product",
                featured=False,
                image_url="",
            )
        ],
        announcements=[],
    )


def test_issue_number_uses_odd_monday_and_even_thursday():
    assert ixlsx.issue_number(dt.date(2026, 9, 7)) == 73
    assert ixlsx.issue_number(dt.date(2026, 9, 10)) == 74


def test_config_requires_vcrm_vpim_and_vendus(monkeypatch):
    monkeypatch.delenv("VCRM_API_KEY", raising=False)
    monkeypatch.setenv("VPIM_API_KEY", "vpim")
    monkeypatch.setenv("VENDUS_API_KEY", "vendus")

    with pytest.raises(RuntimeError, match="VCRM_API_KEY"):
        ixlsx.load_config()


def test_dry_run_never_calls_gmail_and_writes_simulated_eml(tmp_path):
    publication_date = dt.date(2026, 9, 8)
    data = bulletin(publication_date)
    xlsx_path = tmp_path / "order.xlsx"
    html_path = tmp_path / "bulletin.html"
    report_path = tmp_path / "report.json"
    xlsx_path.write_bytes(b"xlsx")
    html_path.write_text("<p>Bulletin</p>", encoding="utf-8")
    report_path.write_text("{}", encoding="utf-8")

    with (
        patch.object(ixlsx, "load_config", return_value=config(tmp_path)),
        patch.object(ixlsx, "build_bulletin", return_value=(data, object())),
        patch.object(
            ixlsx,
            "generate_artifacts",
            return_value=(xlsx_path, html_path, "<p>Bulletin</p>", report_path),
        ),
        patch.object(ixlsx, "create_gmail_service") as gmail,
    ):
        result = ixlsx.run("dry-run", publication_date)

    assert Path(result["eml"]).is_file()
    assert gmail.call_count == 0
    assert b"X-Vetify-Simulation: true" in Path(result["eml"]).read_bytes()


def test_production_send_is_rejected_outside_schedule(tmp_path):
    with (
        patch.object(ixlsx, "load_config", return_value=config(tmp_path)),
        pytest.raises(RuntimeError, match="Monday or Thursday"),
    ):
        ixlsx.run("send", dt.date(2026, 9, 8))


def test_remote_template_failure_aborts_without_fallback(tmp_path):
    class BrokenVcrm:
        def export(self, node_id, target):
            raise RuntimeError("remote unavailable")

    with pytest.raises(RuntimeError, match="remote unavailable"):
        ixlsx.generate_artifacts(
            config(tmp_path), bulletin(dt.date(2026, 9, 7)), BrokenVcrm()
        )

    assert not list(tmp_path.glob("*.html"))
    assert not list(tmp_path.glob("*.xlsx"))
