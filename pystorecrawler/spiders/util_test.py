import unittest

from pystorecrawler.spiders.util import version_name


class TestUtil(unittest.TestCase):
    def test_version_name(self):
        versions = [
            "1",
        ]

        vn = version_name("1", versions)
        self.assertEqual("1 (2)", vn)

        versions.append(vn)

        vn = version_name("1", versions)
        self.assertEqual("1 (3)", vn)


if __name__ == '__main__':
    unittest.main()
