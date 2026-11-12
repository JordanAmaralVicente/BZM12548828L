import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import crawler.notify as n

SIG = {"signal": "COMPRA", "price": 3999.0, "store": "kabum", "reason": "Menor preço já registrado.",
       "avg30": 4300.5, "min": 3999.0, "url": "https://www.kabum.com.br/produto/1"}


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, password):
        self.user, self.password = user, password

    def send_message(self, msg):
        FakeSMTP.sent.append((self.host, self.user, self.password, msg))


class NotifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = mock.patch.object(n, "STATE_JSON", Path(self.tmp.name) / "state.json")
        self.state.start()
        FakeSMTP.sent.clear()

    def tearDown(self):
        self.state.stop()
        self.tmp.cleanup()

    def test_alert_only_once(self):
        n.STATE_JSON.write_text('{"ps5-digital": {"signal": "NEUTRO", "min": 4200}}')
        self.assertEqual(len(n.build_alerts({"ps5-digital": SIG})), 1)
        self.assertEqual(n.build_alerts({"ps5-digital": SIG}), [])

    def test_send_email(self):
        env = {"EMAIL_USER": "remetente@gmail.com", "EMAIL_APP_PASSWORD": "abcd efgh ijkl mnop",
               "EMAIL_TO": "destino@example.com", "GITHUB_REPOSITORY": "Fulano/precos-ps5"}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(n.smtplib, "SMTP_SSL", FakeSMTP):
            n.send_email(n.build_alerts({"ps5-digital": SIG}))
        host, user, pw, msg = FakeSMTP.sent[0]
        self.assertEqual((host, user, pw), ("smtp.gmail.com", "remetente@gmail.com", "abcdefghijklmnop"))
        self.assertEqual(msg["To"], "destino@example.com")
        self.assertIn("COMPRA: PS5 Edição Digital", msg["Subject"])
        body = msg.get_content()
        self.assertIn("R$ 3.999,00 na Kabum", body)
        self.assertIn("https://fulano.github.io/precos-ps5/", body)

    def test_no_credentials_does_not_send(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(n.smtplib, "SMTP_SSL", FakeSMTP):
            n.send_email(["x\ny"])
        self.assertEqual(FakeSMTP.sent, [])


if __name__ == "__main__":
    unittest.main()
