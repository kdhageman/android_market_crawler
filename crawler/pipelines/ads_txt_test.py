import os
import shutil
import tempfile
import unittest

from crawler.item import Meta
from crawler.pipelines.ads_txt import AdsTxtPipeline
from crawler.pipelines.util import TestSpider


class TestAdsTxtPipeline(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_proces_item(self):
        pipeline = AdsTxtPipeline(self.tmpdir)
        spider = TestSpider()

        # website with valid ads.txt
        meta = {
            "pkg_name": "valid",
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

        valid_path = os.path.join(self.tmpdir, "test", "valid", "ads.txt")
        invalid_path = os.path.join(self.tmpdir, "test", "invalid", "ads.txt")

        self.assertTrue(os.path.exists(valid_path))
        self.assertFalse(os.path.exists(invalid_path))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)


if __name__ == '__main__':
    unittest.main()
