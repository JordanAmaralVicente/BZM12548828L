import unittest
from datetime import date, datetime, timedelta

from crawler.signals import black_friday, compute


def series(prices, start=datetime(2026, 9, 1, 9)):
    return [{"ts": (start + timedelta(hours=12 * i)).isoformat(), "price": p,
             "store": "kabum", "url": "", "title": ""} for i, p in enumerate(prices)]


class SignalTest(unittest.TestCase):
    def test_black_friday(self):
        self.assertEqual(black_friday(2026), date(2026, 11, 27))
        self.assertEqual(black_friday(2025), date(2025, 11, 28))

    def test_collecting(self):
        self.assertEqual(compute(series([4000, 3900]))["signal"], "COLETANDO")

    def test_new_low_is_buy(self):
        self.assertEqual(compute(series([4500] * 20 + [4100]))["signal"], "COMPRA")

    def test_above_average_waits(self):
        self.assertEqual(compute(series([4000] * 20 + [4300]))["signal"], "AGUARDE")

    def test_normal_is_neutral(self):
        s = compute(series([4000, 4200] * 10 + [4150]))
        self.assertEqual(s["signal"], "NEUTRO", s["reason"])

    def test_black_friday_near_waits(self):
        s = compute(series([4000, 4200] * 10 + [4150], start=datetime(2026, 11, 2, 9)))
        self.assertEqual(s["signal"], "AGUARDE")
        self.assertIn("Black Friday", s["reason"])


if __name__ == "__main__":
    unittest.main()
