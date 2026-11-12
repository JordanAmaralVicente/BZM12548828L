import unittest

from crawler.main import best_deals


def offer(store, price):
    return {"store": store, "price": price, "title": "", "url": f"https://{store}/x"}


class DealsTest(unittest.TestCase):
    def test_separate_beats_combo(self):
        deals = best_deals({
            "ps5-digital": [offer("amazon", 4169.0), offer("kabum", 4230.57)],
            "gta6-padrao": [offer("carrefour", 404.99), offer("kabum", 418.41)],
            "combo-digital": [offer("amazon", 4908.9)],
        })
        d = deals[0]
        self.assertEqual(d["best"]["type"], "separado")
        self.assertEqual(d["best"]["total"], 4573.99)
        self.assertEqual([i["store"] for i in d["best"]["items"]], ["amazon", "carrefour"])
        self.assertEqual(d["alt"]["type"], "combo")

    def test_combo_beats_separate(self):
        deals = best_deals({
            "ps5-disco": [offer("kabum", 4999.0)],
            "gta6-padrao": [offer("psstore", 449.9)],
            "combo-disco": [offer("amazon", 5100.0)],
        })
        self.assertEqual(deals[0]["best"]["type"], "combo")
        self.assertEqual(deals[0]["alt"]["total"], 5448.9)

    def test_missing_game_uses_combo_only(self):
        deals = best_deals({"ps5-pro": [offer("amazon", 7399.0)], "combo-pro": [offer("amazon", 7800.0)]})
        self.assertEqual(deals[0]["best"]["type"], "combo")
        self.assertIsNone(deals[0]["alt"])


if __name__ == "__main__":
    unittest.main()
