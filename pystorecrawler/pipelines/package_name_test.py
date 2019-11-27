import os
import tempfile
import unittest

from pystorecrawler.item import PackageName
from pystorecrawler.pipelines.package_name import PackageNamePipeline
from pystorecrawler.pipelines.util import TestSpider


class TestPackageNamePipeline(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.mktemp()
        self.spider = TestSpider()
        self.p = PackageNamePipeline(self.tmpfile)

    def test_process_item(self):
        # process item
        item = PackageName(
            name="com.example.test"
        )

        for j in range(2):  # run twice to ensure it loads existing packages correctly
            self.p.open_spider(self.spider)
            for i in range(2):  # run twice to prevent duplicate packages
                self.p.process_item(item, self.spider)
            self.p.close_spider(self.spider)

        # test for a single line in the file under test
        with open(self.tmpfile, 'r') as f:
            lines = f.readlines()
            self.assertEqual(1, len(lines))

    def tearDown(self):
        os.remove(self.tmpfile)


if __name__ == '__main__':
    unittest.main()
