import os
import shutil
import tempfile
import unittest

from crawler.item import PackageName
from crawler.pipelines.package_name import PackageNamePipeline
from crawler.pipelines.util import TestSpider


class TestPackageNamePipeline(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.spider = TestSpider()
        self.p = PackageNamePipeline(self.tmpdir)

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
        fname = "test-packages.csv"
        fpath = os.path.join(self.tmpdir, fname)

        with open(fpath, 'r') as f:
            lines = f.readlines()
            self.assertEqual(1, len(lines))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)


if __name__ == '__main__':
    unittest.main()
