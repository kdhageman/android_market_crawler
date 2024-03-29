import json
import os
import shutil
import tempfile
import unittest

from pytest_httpserver import HTTPServer
from twisted.internet.defer import inlineCallbacks

from crawler.pipelines.download_apks import DownloadApksPipeline
from crawler.util import TestSpider


class TestDownloadPipeline(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    @inlineCallbacks
    def test_process_item(self):
        settings = {
            'CRAWL_ROOTDIR': self.tmpdir
        }
        p = DownloadApksPipeline(settings)

        spider = TestSpider()
        p.open_spider(spider)

        # process item
        with HTTPServer() as server:
            data = {"test": "data"}
            server.expect_request("/test").respond_with_json(data)

            version = "1.0.0"
            pkg_name = "com.example.test"
            meta = dict(
                version=version,
                pkg_name=pkg_name
            )
            versions = {
                version: {
                    "timestamp": 0,
                    "download_url": server.url_for("/test")
                }
            }
            item = dict(
                meta=meta,
                versions=versions
            )

            _ = yield p.process_item(item, spider)

        # check for written file
        fname = f"{version}.apk"
        fpath = os.path.join(self.tmpdir, "test", pkg_name, fname)

        self.assertTrue(os.path.exists(fpath))
        with open(fpath, 'r') as f:
            content = f.read()
            self.assertEqual(json.loads(content), data)
        print("Test done!")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)


if __name__ == '__main__':
    unittest.main()
