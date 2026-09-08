# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
#     "openpyxl",
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
#     # Newer wheels require ARM instructions unavailable in the runtime baseline.
#     "cryptography<47",
# ]
# ///
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from models import BulletinData
from renderers import build_email_message, build_xlsx, render_html
from sources import (
    AntboxClient,
    DashyClient,
    VendusClient,
    load_announcements,
    load_cargo,
    load_products,
    load_recipients,
)

VCRM_API_URL = "https://vcrm.lightray.cloud/api"
VPIM_API_URL = "https://vpim.lightray.cloud/api"
VSCO_API_URL = "https://vsco.lightray.cloud/api"
XLSX_TEMPLATE_NODE_ID = "DJBTl5Ls"
HTML_TEMPLATE_NODE_ID = "G64RDgSJ"
IMPERSONATED_EMAIL = "comercial@vetify.co.ao"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


@dataclass(frozen=True)
class Config:
    vendus_api_key: str
    vcrm_api_key: str
    vpim_api_key: str
    dashy_api_key: str
    vsco_api_key: str
    service_account_key_path: Path | None
    output_dir: Path
    test_emails: list[str]


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def load_config() -> Config:
    service_account = os.environ.get("SERVICE_ACCOUNT_KEY_PATH", "").strip()
    return Config(
        vendus_api_key=_required_env("VENDUS_API_KEY"),
        vcrm_api_key=_required_env("VCRM_API_KEY"),
        vpim_api_key=_required_env("VPIM_API_KEY"),
        dashy_api_key=os.environ.get("DASHY_API_KEY", "").strip(),
        vsco_api_key=os.environ.get("VSCO_API_KEY", "").strip(),
        service_account_key_path=Path(service_account) if service_account else None,
        output_dir=Path(os.environ.get("IXLSX_OUTPUT_DIR", "/tmp")),
        test_emails=sorted(
            {
                value.strip().lower()
                for value in os.environ.get("IXLSX_TEST_EMAILS", "").split(",")
                if value.strip()
            }
        ),
    )


def issue_number(publication_date: dt.date) -> int:
    week = publication_date.isocalendar().week
    return week * 2 - (1 if publication_date.weekday() < 3 else 0)


def subject_for(bulletin: BulletinData, test: bool = False) -> str:
    prefix = "[TEST] " if test else ""
    return (
        f"{prefix}Boletim Bissemanal Vetify · N.º {bulletin.issue_number} · "
        f"{bulletin.publication_date.strftime('%d/%m/%Y')}"
    )


def build_bulletin(
    config: Config, publication_date: dt.date
) -> tuple[BulletinData, AntboxClient]:
    vcrm = AntboxClient(VCRM_API_URL, config.vcrm_api_key)
    vpim = AntboxClient(VPIM_API_URL, config.vpim_api_key)

    recipients = load_recipients(vcrm)
    announcements = load_announcements(vcrm, publication_date)
    vendus_records = VendusClient(config.vendus_api_key).products()
    if not vendus_records:
        raise RuntimeError("Vendus returned no products")

    anomalies: list[str] = []
    degradations: list[str] = []
    expiries = {}
    if config.dashy_api_key:
        try:
            expiries = DashyClient(config.dashy_api_key).future_expiries(
                publication_date
            )
        except (
            requests.RequestException,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            degradations.append(f"Dashy unavailable; expiry dates omitted: {error}")
    else:
        degradations.append("DASHY_API_KEY not configured; expiry dates omitted")

    products, product_anomalies = load_products(vpim, vendus_records, expiries)
    anomalies.extend(product_anomalies)

    recent_arrivals = []
    in_transit = []
    if config.vsco_api_key:
        try:
            vsco = AntboxClient(VSCO_API_URL, config.vsco_api_key)
            recent_arrivals, in_transit = load_cargo(vsco, publication_date)
        except (
            requests.RequestException,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            degradations.append(f"VSCO unavailable; cargo sections omitted: {error}")
    else:
        degradations.append("VSCO_API_KEY not configured; cargo sections omitted")

    bulletin = BulletinData(
        publication_date=publication_date,
        issue_number=issue_number(publication_date),
        recipients=recipients,
        products=products,
        announcements=announcements,
        recent_arrivals=recent_arrivals,
        in_transit=in_transit,
        anomalies=anomalies,
        degradations=degradations,
    )
    return bulletin, vcrm


def generate_artifacts(
    config: Config,
    bulletin: BulletinData,
    vcrm: AntboxClient,
) -> tuple[Path, Path, str, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    date_text = bulletin.publication_date.isoformat()
    xlsx_template = (
        config.output_dir / f".vcrm-{XLSX_TEMPLATE_NODE_ID}-{date_text}.xlsx"
    )
    html_template = (
        config.output_dir / f".vcrm-{HTML_TEMPLATE_NODE_ID}-{date_text}.html"
    )
    xlsx_output = config.output_dir / f"Vetify-Encomendas-{date_text}.xlsx"
    html_output = config.output_dir / f"Boletim-Bissemanal-Vetify-{date_text}.html"
    report_output = config.output_dir / f"Boletim-Bissemanal-Vetify-{date_text}.json"

    try:
        vcrm.export(XLSX_TEMPLATE_NODE_ID, xlsx_template)
        vcrm.export(HTML_TEMPLATE_NODE_ID, html_template)
        build_xlsx(xlsx_template, xlsx_output, bulletin)
        rendered_html = render_html(html_template.read_text(encoding="utf-8"), bulletin)
        html_output.write_text(rendered_html, encoding="utf-8")
    finally:
        xlsx_template.unlink(missing_ok=True)
        html_template.unlink(missing_ok=True)

    report = {
        "publicationDate": date_text,
        "issueNumber": bulletin.issue_number,
        "recipientCount": len(bulletin.recipients),
        "productCount": len(bulletin.products),
        "featuredCount": sum(product.featured for product in bulletin.products),
        "announcementCount": len(bulletin.announcements),
        "recentArrivalCount": len(bulletin.recent_arrivals),
        "inTransitCount": len(bulletin.in_transit),
        "anomalies": bulletin.anomalies,
        "degradations": bulletin.degradations,
        "templates": {
            "xlsx": XLSX_TEMPLATE_NODE_ID,
            "html": HTML_TEMPLATE_NODE_ID,
            "source": "VCRM",
        },
    }
    report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return xlsx_output, html_output, rendered_html, report_output


def create_gmail_service(config: Config):
    path = config.service_account_key_path
    if not path or not path.is_file():
        raise RuntimeError("SERVICE_ACCOUNT_KEY_PATH must point to a readable JSON key")
    credentials = Credentials.from_service_account_file(
        path,
        scopes=GMAIL_SCOPES,
        subject=IMPERSONATED_EMAIL,
    )
    return build("gmail", "v1", credentials=credentials)


def send_message(gmail_service, message) -> str:
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    response = (
        gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
    )
    message_id = response.get("id") if isinstance(response, dict) else None
    if not message_id:
        raise RuntimeError("Gmail did not return a message ID")
    return str(message_id)


def run(mode: str, publication_date: dt.date | None = None) -> dict:
    config = load_config()
    publication_date = (
        publication_date or dt.datetime.now(ZoneInfo("Africa/Luanda")).date()
    )
    if mode == "send" and publication_date.weekday() not in {0, 3}:
        raise RuntimeError("Production delivery is allowed only on Monday or Thursday")

    bulletin, vcrm = build_bulletin(config, publication_date)
    if mode == "send" and not bulletin.recipients:
        raise RuntimeError("VCRM returned no eligible recipients")
    if mode == "test" and not config.test_emails:
        raise RuntimeError("IXLSX_TEST_EMAILS is required in test mode")

    xlsx_path, html_path, rendered_html, report_path = generate_artifacts(
        config, bulletin, vcrm
    )
    result = {
        "mode": mode,
        "xlsx": str(xlsx_path),
        "html": str(html_path),
        "report": str(report_path),
        "recipients": len(bulletin.recipients),
    }

    if mode == "dry-run":
        eml_path = (
            config.output_dir
            / f"Boletim-Bissemanal-Vetify-{publication_date.isoformat()}.eml"
        )
        message = build_email_message(
            bulletin.recipients,
            subject_for(bulletin),
            rendered_html,
            xlsx_path,
            simulation=True,
        )
        eml_path.write_bytes(message.as_bytes())
        result["eml"] = str(eml_path)
        return result

    recipients = config.test_emails if mode == "test" else bulletin.recipients
    message = build_email_message(
        recipients,
        subject_for(bulletin, test=mode == "test"),
        rendered_html,
        xlsx_path,
    )
    result["messageId"] = send_message(create_gmail_service(config), message)
    return result


def cli(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        mode = "send"
    elif arguments == ["--dry-run"]:
        mode = "dry-run"
    elif arguments == ["test", "all_e2e"]:
        mode = "test"
    else:
        print("Usage: ixlsx.py [--dry-run | test all_e2e]", file=sys.stderr)
        return 2
    result = run(mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
