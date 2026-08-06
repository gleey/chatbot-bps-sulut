"""Tests untuk cari_link_otomatis — fuzzy matching kategori BPS."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import cari_link_otomatis


class TestCariLink(unittest.TestCase):

    def test_exact_match_alias(self):
        _, link = cari_link_otomatis("kependudukan")
        self.assertIn("subject=519", link)

    def test_exact_match_full(self):
        _, link = cari_link_otomatis("pertanian kehutanan perikanan")
        self.assertIn("subject=557", link)

    def test_alias_inflasi(self):
        _, link = cari_link_otomatis("inflasi")
        self.assertIn("subject=536", link)

    def test_alias_pdrb(self):
        _, link = cari_link_otomatis("pdrb")
        self.assertIn("subject=530", link)

    def test_alias_ekspor(self):
        _, link = cari_link_otomatis("ekspor")
        self.assertIn("subject=535", link)

    def test_fuzzy_match(self):
        _, link = cari_link_otomatis("data penduduk sulut")
        self.assertIn("subject=519", link)

    def test_fuzzy_match_pariwisata(self):
        _, link = cari_link_otomatis("wisata")
        self.assertIn("subject=561", link)

    def test_fallback_homepage(self):
        _, link = cari_link_otomatis("xyz tidak ada kategori ini")
        self.assertEqual(link, "https://sulut.bps.go.id")

    def test_empty_string(self):
        _, link = cari_link_otomatis("")
        self.assertEqual(link, "https://sulut.bps.go.id")

    def test_returns_kategori_name(self):
        kategori, link = cari_link_otomatis("pertanian")
        self.assertIsNotNone(kategori)
        self.assertIn("subject=557", link)

    def test_substring_match(self):
        _, link = cari_link_otomatis("transportasi")
        self.assertIn("subject=560", link)

    def test_case_insensitive(self):
        _, link = cari_link_otomatis("PARIWISATA")
        self.assertIn("subject=561", link)


if __name__ == "__main__":
    unittest.main()
