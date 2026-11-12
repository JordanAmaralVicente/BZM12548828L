import unittest

from crawler.classify import classify, parse_brl

CASES = [
    # (título, preço, loja, esperado)
    ("Console Sony PlayStation 5, SSD 825GB, Controle Sem Fio DualSense + 2 Jogos Digitais, Edição Digital", 4230.57, "kabum", "ps5-digital"),
    ("Console Sony PlayStation 5, Com Leitor de Discos + Jogo Marvel's Wolverine, PS5", 4999, "kabum", "ps5-disco"),
    ("Console PlayStation 5 Pro Sony, SSD 2TB, Com Controle Sem Fio DualSense, Branco", 7399, "kabum", "ps5-pro"),
    ("PlayStation®5 Pro", 7399, "amazon", "ps5-pro"),
    ("PlayStation®5 + God of War Ragnarök", 5319.9, "amazon", "ps5-disco"),
    ("PlayStation®5 Slim Edição Digital", 4369.9, "amazon", "ps5-digital"),
    ("Bundle GTA VI + PlayStation 5 Slim Digital 825 GB - Pacote Astro Bot e Gran Turismo 7", 4908.9, "amazon", "combo-digital"),
    ("Bundle GTA VI + PlayStation 5 Slim Disk Pacote Astro Bot e Gran Turismo 7", 5650.91, "amazon", "combo-disco"),
    ("Jogo Grand Theft Auto GTA VI, PS5 - TT000272PS5", 418.41, "kabum", "gta6-padrao"),
    ("Grand Theft Auto VI - PS5 - Versão Standard - Code In Box", 404.99, "carrefour", "gta6-padrao"),
    ("Grand Theft Auto VI", 449.9, "psstore", "gta6-padrao"),
    ("Grand Theft Auto VI: Ultimate Edition", 549.9, "psstore", "gta6-ultimate"),
    # descartes
    ("Grand Theft Auto VI: Melhoria Ultimate Edition", 100, "psstore", None),
    ("Bundle GTA VI PlayStation 5 + Controle sem fio PlayStation DualSense Techno Red", 948.9, "amazon", None),
    ("Sony PlayStation 5 Slim Digital Console 825GB - International Version", 4019, "amazon", None),
    ("PlayStation 5 Slim Digital Edition Console + Blue Controller Bundle (KSA version)", 5509.9, "amazon", None),
    ("Suporte Para Controle Ps5 E XBOX Gta Vi", 180.7, "kabum", None),
    ("Jogo Gta V 5, Grand Theft Auto 5, Playstation 5 - Mídia Física", 267.3, "kabum", None),
    ("SSD Externo Sandisk Extreme 2TB Usb Playstation 5", 3424.41, "kabum", None),
    ("Playstation Portal Para Console Ps5 Reprodutor Remoto", 1799.06, "kabum", None),
    ("Console Playstation 4 1 Tb Edição Limitada Days Of Play - Cinza", 3599, "kabum", None),
    ("Leitor de Disco Para Playstation 5 Slim, PS5 Pro Sony, Edição digital", 649, "kabum", None),
    ("Console PlayStation 5 Slim Usado", 3000, "mercadolivre", None),
]


class ClassifyTest(unittest.TestCase):
    def test_cases(self):
        for title, price, store, expected in CASES:
            with self.subTest(title=title):
                self.assertEqual(classify(title, price, store), expected)

    def test_parse_brl(self):
        self.assertEqual(parse_brl("R$\xa04.277,07"), 4277.07)
        self.assertEqual(parse_brl("R$449,90"), 449.9)
        self.assertEqual(parse_brl("7.399"), 7399.0)


if __name__ == "__main__":
    unittest.main()
