import os
import shutil
import tempfile
import unittest

from crawler.item import Meta
from crawler.pipelines.ads import AdsPipeline
from crawler.pipelines.util import TestSpider


class TestAdsTxtPipeline(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_proces_item(self):
        pipeline = AdsPipeline(self.tmpdir)
        spider = TestSpider()

        # website with valid ads.txt
        meta = {
            "pkg_name": "ads_only",
            "developer_website": "http://www.businessinsider.com/"
        }
        m = Meta(meta=meta)
        pipeline.process_item(m, spider)

        # website with valid app-ads.txt
        meta = {
            "pkg_name": "app_ads_only",
            "developer_website": "https://outfit7.com/"
        }
        m = Meta(meta=meta)
        pipeline.process_item(m, spider)

        # website with invalid ads.txt (text/html instead of text/plain)
        meta = {
            "pkg_name": "invalid",
            "developer_website": "http://kefirgames.ru/en"
        }
        m = Meta(meta=meta)
        pipeline.process_item(m, spider)

        self.assertTrue(self.exists("app_ads_only", "app-ads.txt"))
        self.assertFalse(self.exists("app_ads_only", "ads.txt"))

        self.assertFalse(self.exists("ads_only", "app-ads.txt"))
        self.assertTrue(self.exists("ads_only", "ads.txt"))

        self.assertFalse(self.exists("invalid", "app-ads.txt"))
        self.assertFalse(self.exists("invalid", "ads.txt"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def exists(self, pkg, fname):
        fpath = os.path.join(self.tmpdir, "test", pkg, fname)
        return os.path.exists(fpath)

if __name__ == '__main__':
    unittest.main()
