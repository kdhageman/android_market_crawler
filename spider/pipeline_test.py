import json
import os
import shutil
import tempfile
import unittest
import scrapy
from pytest_httpserver import HTTPServer

from spider.item import PackageName
from spider.pipeline import DownloadApksPipeline, PackageNamePipeline


class TestSpider(scrapy.Spider):
    def parse(self, response):
        pass

    name = "test_spider"


class TestDownloadPipeline(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_process_item(self):
        p = DownloadApksPipeline(self.tmpdir)

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
                    "date": 0,
                    "dl_link": server.url_for("/test")
                }
            }

            item = dict(
                meta=meta,
                versions=versions
            )

            spider = TestSpider()

            p.process_item(item, spider)

        # check for written file
        fname = f"{version}.apk"
        fpath = os.path.join(self.tmpdir, "test", pkg_name, fname)

        self.assertTrue(os.path.exists(fpath))
        with open(fpath, 'r') as f:
            content = f.read()
            self.assertEqual(json.loads(content), data)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)


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

        for j in range(2): # run twice to ensure it loads existing packages correctly
            self.p.open_spider(self.spider)
            for i in range(2): # run twice to prevent duplicate packages
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
