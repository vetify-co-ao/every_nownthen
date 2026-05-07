import importlib
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("VENDUS_API_KEY", "test-vendus-key")
os.environ.setdefault("SERVICE_ACCOUNT_KEY_PATH", "/tmp/test-service-account.json")

import ixlsx


class BuildEmailMessageTests(unittest.TestCase):
    def test_bulk_email_uses_bcc_without_to_header(self):
        message = ixlsx.build_email_message(
            ["first@example.com", "second@example.com"],
            "Oferta Vetify 2026-04-21",
            "<p>Hello</p>",
            None,
        )

        self.assertIsNone(message.get("to"))
        self.assertEqual(message["bcc"], "first@example.com, second@example.com")
        self.assertEqual(message["reply-to"], ixlsx.REPLY_TO)
        self.assertEqual(message["from"], ixlsx.EMAIL_FROM)
        self.assertEqual(message["subject"], "Oferta Vetify 2026-04-21")

    def test_sender_config_ignores_environment_overrides(self):
        with patch.dict(
            os.environ,
            {
                "VENDUS_API_KEY": "test-vendus-key",
                "SERVICE_ACCOUNT_KEY_PATH": "/tmp/test-service-account.json",
                "IMPERSONATED_EMAIL": "env-user@example.com",
                "EMAIL_FROM": "Env Sender <env-user@example.com>",
                "REPLY_TO": "env-reply@example.com",
                "EMAIL_SUBJECT_TEMPLATE": "Env Subject %s",
            },
            clear=True,
        ):
            reloaded = importlib.reload(ixlsx)

        self.assertEqual(reloaded.IMPERSONATED_EMAIL, "comercial@vetify.co.ao")
        self.assertEqual(reloaded.EMAIL_FROM, "Vetify <comercial@vetify.co.ao>")
        self.assertEqual(reloaded.REPLY_TO, "encomendas@vetify.co.ao")
        self.assertEqual(reloaded.EMAIL_SUBJECT_TEMPLATE, "Oferta Vetify %s")

    def test_impersonated_email_does_not_need_environment_variable(self):
        with patch.dict(
            os.environ,
            {
                "VENDUS_API_KEY": "test-vendus-key",
                "SERVICE_ACCOUNT_KEY_PATH": "/tmp/test-service-account.json",
            },
            clear=True,
        ):
            reloaded = importlib.reload(ixlsx)

        self.assertEqual(reloaded.IMPERSONATED_EMAIL, "comercial@vetify.co.ao")


if __name__ == "__main__":
    unittest.main()
