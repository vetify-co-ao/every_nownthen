# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
#     "openpyxl",
#     "google-api-python-client",
#     "google-auth",
#     "google-auth-httplib2",
# ]
# ///
import base64
import datetime
import json
import os
import shutil
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openpyxl import load_workbook

# --- Configuration Constants ---

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Bundled assets (versioned with the script)
XLSX_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "vetify-template.xlsx")
EMAIL_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "email-template.html")

# Vendus API
VENDUS_API_KEY = os.environ["VENDUS_API_KEY"]
VENDUS_API_BASE_URL = "https://www.vendus.pt/ws/v1.2"
VENDUS_PRODUCTS_ENDPOINT = "products"
VENDUS_CLIENTS_ENDPOINT = "clients"

# Output
OUTPUT_DIR = os.environ.get("IXLSX_OUTPUT_DIR", "/tmp")

# Gmail API
SERVICE_ACCOUNT_KEY_PATH = os.environ["SERVICE_ACCOUNT_KEY_PATH"]
IMPERSONATED_EMAIL = "comercial@vetify.co.ao"
GMAIL_API_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://mail.google.com/",
]

# Email content
EMAIL_FROM = "Vetify <comercial@vetify.co.ao>"
REPLY_TO = "encomendas@vetify.co.ao"
EMAIL_SUBJECT_TEMPLATE = "Oferta Vetify %s"

# E2E test recipients (comma-separated env var)
TEST_EMAILS = [
    e.strip() for e in os.environ.get("IXLSX_TEST_EMAILS", "").split(",") if e.strip()
]

# Excel layout
EXCEL_SHEET_NAME = "Sheet1"
EXCEL_FIRST_DATA_ROW = 5
EXCEL_REF_COLUMN_LETTER = "A"
EXCEL_DATE_CELL = "D2"
EXCEL_STOCK_STATUS_COLUMN_LETTER = "C"
EXCEL_NET_PRICE_COLUMN_LETTER = "D"
EXCEL_DUE_DATE_COLUMN_LETTER = "I"


# --- Vendus API Functions ---
def get_vendus_data(endpoint, params=None):
    """Fetches data from a Vendus API endpoint."""
    if params is None:
        params = {}
    url = f"{VENDUS_API_BASE_URL}/{endpoint}/?api_key={VENDUS_API_KEY}"

    query_params = []
    for key, value in params.items():
        query_params.append(f"{key}={value}")
    if query_params:
        url += "&" + "&".join(query_params)

    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Vendus data from {endpoint}: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from Vendus {endpoint}: {e}")
        print(f"Response text: {response.text}")
        raise


def get_inventory():
    """Fetches product inventory from Vendus."""
    print("Fetching inventory from Vendus...")
    params = {"per_page": "500"}
    records = get_vendus_data(VENDUS_PRODUCTS_ENDPOINT, params)

    inventory_list = []
    if records:
        for record in records:
            qty = 0
            if (
                record.get("stock")
                and record["stock"].get("stores")
                and len(record["stock"]["stores"]) > 0
            ):
                qty = record["stock"]["stores"][0].get("stock", 0)

            net_price_str = record.get("prices", {}).get("net", "0")
            try:
                net_price = float(net_price_str)
            except ValueError:
                print(
                    f"Warning: Could not parse net price '{net_price_str}' for product {record.get('reference')}. Using 0.0."
                )
                net_price = 0.0

            inventory_list.append(
                {
                    "ProductId": record.get("reference"),
                    "Qty": qty,
                    "NetPrice": net_price,
                }
            )
    print(f"Fetched {len(inventory_list)} inventory items.")
    return inventory_list


def get_client_emails():
    """Fetches active client emails from Vendus."""
    print("Fetching client emails from Vendus...")
    params = {"per_page": "500"}
    clients = get_vendus_data(VENDUS_CLIENTS_ENDPOINT, params)

    emails = []
    if clients:
        for client in clients:
            if client.get("status") == "active" and client.get("email"):
                emails.append(client["email"])
    print(f"Fetched {len(emails)} client emails.")
    return emails


# --- XLSX Building Function ---
def build_xlsx_file(inventory):
    """Builds the XLSX file from a template and inventory data."""
    print(f"Building XLSX file from template: {XLSX_TEMPLATE_PATH}...")
    if not os.path.exists(XLSX_TEMPLATE_PATH):
        print(f"Error: XLSX template file not found at {XLSX_TEMPLATE_PATH}")
        raise FileNotFoundError(f"XLSX template file not found: {XLSX_TEMPLATE_PATH}")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"Created output directory: {OUTPUT_DIR}")

    today_date_str_filename = datetime.date.today().strftime("%Y-%m-%d")
    today_date_str_cell = datetime.date.today().strftime("%d/%m/%Y")

    output_filename = f"Vetify-{today_date_str_filename}.xlsx"
    output_filepath = os.path.join(OUTPUT_DIR, output_filename)

    try:
        shutil.copy(XLSX_TEMPLATE_PATH, output_filepath)

        workbook = load_workbook(output_filepath)
        sheet = workbook[EXCEL_SHEET_NAME]

        sheet[EXCEL_DATE_CELL] = today_date_str_cell

        inventory_map = {item["ProductId"]: item for item in inventory}

        row_index = EXCEL_FIRST_DATA_ROW
        while True:
            ref_cell_addr = f"{EXCEL_REF_COLUMN_LETTER}{row_index}"
            product_ref = sheet[ref_cell_addr].value

            if not product_ref:
                break

            if product_ref in inventory_map:
                product_data = inventory_map[product_ref]
                qty = product_data.get("Qty", 0)

                stock_status_msg = "EM STOCK"
                if qty <= 0:
                    stock_status_msg = "ESGOTADO"
                elif qty < 20:
                    stock_status_msg = "ULTIMAS UNIDADES"
                sheet[f"{EXCEL_STOCK_STATUS_COLUMN_LETTER}{row_index}"] = (
                    stock_status_msg
                )

                sheet[f"{EXCEL_NET_PRICE_COLUMN_LETTER}{row_index}"] = product_data.get(
                    "NetPrice", 0.0
                )

                if qty <= 0:
                    sheet[f"{EXCEL_DUE_DATE_COLUMN_LETTER}{row_index}"] = ""

            row_index += 1

        workbook.save(output_filepath)
        print(f"XLSX file successfully built and saved to: {output_filepath}")
        return output_filepath
    except Exception as e:
        print(f"Error building XLSX file: {e}")
        raise


# --- Gmail API Functions ---
def create_gmail_service():
    """Creates and returns an authorized Gmail API service instance."""
    print("Initializing Gmail API service...")
    if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
        print(
            f"Error: Service account key file not found at {SERVICE_ACCOUNT_KEY_PATH}"
        )
        raise FileNotFoundError(
            f"Service account key file not found: {SERVICE_ACCOUNT_KEY_PATH}"
        )

    try:
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_KEY_PATH,
            scopes=GMAIL_API_SCOPES,
            subject=IMPERSONATED_EMAIL,
        )
        service = build("gmail", "v1", credentials=creds)
        print("Gmail API service initialized successfully.")
        return service
    except Exception as e:
        print(f"Error creating Gmail service: {e}")
        raise


def build_email_message(bcc_emails, subject, html_body_content, attachment_path):
    """Builds the email MIME payload for Gmail API delivery."""
    message = MIMEMultipart()
    message["bcc"] = ", ".join(bcc_emails)
    message["reply-to"] = REPLY_TO
    message["from"] = EMAIL_FROM
    message["subject"] = subject

    message.attach(MIMEText(html_body_content, "html"))

    if attachment_path and os.path.exists(attachment_path):
        try:
            with open(attachment_path, "rb") as attachment_file:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment_file.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(attachment_path)}"',
            )
            message.attach(part)
            print(f"Attachment {os.path.basename(attachment_path)} added to email.")
        except Exception as e:
            print(f"Error attaching file {attachment_path}: {e}")
    else:
        print(
            f"Warning: Attachment path {attachment_path} not found or not specified. Sending email without attachment."
        )

    return message


def send_email(gmail_service, to_emails, subject, html_body_content, attachment_path):
    """Sends an email with attachment using Gmail API."""
    if not to_emails:
        print("No recipients provided. Skipping email send.")
        return

    print(f"Preparing to send email to {len(to_emails)} recipients...")

    message = build_email_message(
        to_emails, subject, html_body_content, attachment_path
    )
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    gmail_message_body = {"raw": raw_message}

    try:
        sent_message = (
            gmail_service.users()
            .messages()
            .send(userId="me", body=gmail_message_body)
            .execute()
        )
        print(f"Email sent successfully! Message ID: {sent_message['id']}")
    except HttpError as error:
        print(f"An HTTP error occurred while sending email: {error}")
        error_details = error.resp.get("content", "{}")
        try:
            error_json = json.loads(error_details.decode("utf-8"))
            print(f"Error details: {json.dumps(error_json, indent=2)}")
        except json.JSONDecodeError:
            print(f"Raw error content: {error_details}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred while sending email: {e}")
        raise


# --- Test E2E Function ---
def test_all_e2e(test_email_recipient):
    """Runs an end-to-end test, sending the email only to test addresses."""
    print("Starting E2E test for iXLSX script...")
    if not test_email_recipient:
        print("IXLSX_TEST_EMAILS env var is empty. Aborting E2E test.")
        return
    try:
        inventory = get_inventory()

        if not inventory:
            print("No inventory data fetched for E2E test. Aborting.")
            return

        xlsx_filepath = build_xlsx_file(inventory)
        if not xlsx_filepath:
            print("Failed to build XLSX file for E2E test. Aborting.")
            return

        if not os.path.exists(EMAIL_TEMPLATE_PATH):
            print(
                f"Warning (E2E Test): Email body template not found at {EMAIL_TEMPLATE_PATH}. Using default body."
            )
            email_html_body = "<p>This is a test email with the attached XLSX file.</p>"
        else:
            with open(EMAIL_TEMPLATE_PATH, "r", encoding="utf-8") as f:
                email_html_body = f.read()

        current_date_subject = datetime.date.today().strftime("%Y-%m-%d")
        email_subject = f"[TEST] {EMAIL_SUBJECT_TEMPLATE % current_date_subject}"

        gmail_service = create_gmail_service()

        send_email(
            gmail_service,
            test_email_recipient,
            email_subject,
            email_html_body,
            xlsx_filepath,
        )

        print("iXLSX E2E test finished successfully.")

    except FileNotFoundError as e:
        print(f"Configuration Error (E2E Test): A required file was not found: {e}")
    except Exception as e:
        print(f"An error occurred during E2E test execution: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("E2E test execution ended.")


# --- Main Script Logic ---
def main():
    print("Starting iXLSX script...")
    try:
        inventory = get_inventory()
        client_emails = get_client_emails()

        if not inventory:
            print("No inventory data fetched. Aborting.")
            return

        final_email_list = sorted(
            list(set(email.lower() for email in client_emails if email))
        )
        print(f"Total unique emails to send to: {len(final_email_list)}.")

        if not final_email_list:
            print("No email recipients. Aborting email send.")
            return

        xlsx_filepath = build_xlsx_file(inventory)
        if not xlsx_filepath:
            print("Failed to build XLSX file. Aborting.")
            return

        if not os.path.exists(EMAIL_TEMPLATE_PATH):
            print(
                f"Error: Email body template not found at {EMAIL_TEMPLATE_PATH}. Using default body."
            )
            email_html_body = "<p>Please find the attached XLSX file.</p>"
        else:
            with open(EMAIL_TEMPLATE_PATH, "r", encoding="utf-8") as f:
                email_html_body = f.read()

        current_date_subject = datetime.date.today().strftime("%Y-%m-%d")
        email_subject = EMAIL_SUBJECT_TEMPLATE % current_date_subject

        gmail_service = create_gmail_service()

        send_email(
            gmail_service,
            final_email_list,
            email_subject,
            email_html_body,
            xlsx_filepath,
        )

        print("iXLSX script finished successfully.")

    except FileNotFoundError as e:
        print(f"Configuration Error: A required file was not found: {e}")
    except Exception as e:
        print(f"An error occurred during script execution: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("Script execution ended.")


if __name__ == "__main__":
    print("=== iXLSX configuration ===")
    print(f"VENDUS_API_KEY: {'*' * 8 if VENDUS_API_KEY else 'Not set'}")
    print(f"XLSX_TEMPLATE_PATH: {XLSX_TEMPLATE_PATH}")
    print(f"EMAIL_TEMPLATE_PATH: {EMAIL_TEMPLATE_PATH}")
    print(f"SERVICE_ACCOUNT_KEY_PATH: {SERVICE_ACCOUNT_KEY_PATH}")
    print(f"OUTPUT_DIR: {OUTPUT_DIR}")
    print("===========================")

    import sys

    if len(sys.argv) >= 3 and sys.argv[1] == "test" and sys.argv[2] == "all_e2e":
        test_all_e2e(TEST_EMAILS)
    elif len(sys.argv) > 1:
        print("Invalid arguments")
    else:
        main()
