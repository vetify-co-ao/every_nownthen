import unittest

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


if __name__ == "__main__":
    unittest.main()
