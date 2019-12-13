from lxml import etree
import unittest

from apk.analysis import parse_app_links, _assetlinks_domain


class TestAnalysis(unittest.TestCase):
    def test_assetlinks_domain(self):
        cases = [
            ("*money.yandex.ru", "money.yandex.ru"),
            ("*.example.com", "example.com")
        ]
        for inp, expected in cases:
            actual = _assetlinks_domain(inp)
            self.assertEqual(actual, expected)


    def test_parse_app_links(self):
        manxml = etree.parse("resources/AndroidManifest.xml")
        parsed = parse_app_links(manxml)


if __name__ == '__main__':
    unittest.main()
