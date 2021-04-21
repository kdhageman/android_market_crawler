import http.server
import os
import socketserver
import tempfile
import unittest
from threading import Thread

import scrapy
from scrapy.crawler import CrawlerProcess

from crawler.pipelines.util import InfluxDBClient
from crawler.spiders.util import PackageListSpider


class TestSpider(PackageListSpider):
    name = 'test_spider'

    def __init__(self, crawler, base_url):
        super().__init__(crawler=crawler, settings=crawler.settings)
        self.base_url = base_url

    @classmethod
    def from_crawler(cls, crawler):
        base_url = crawler.settings.get("TEST_BASE_URL")

        return cls(crawler, base_url)

    def base_requests(self):
        url = f"{self.base_url}/base_request_1"
        return [scrapy.Request(url, self.parse)]

    def parse(self, response):
        return {}

    def url_by_package(self, pkg):
        return f"{self.base_url}/package/{pkg}"

    def parse_pkg_page(self, response):
        return {"success": True}


class RateLimitHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Retry-After", 2)
        self.end_headers()
        content = f"<html><body><h1>Too Many Requests!</h1></body></html>"
        self.wfile.write(content.encode("utf8"))


def serve_forever(my_server):
    my_server.serve_forever()


def run_server():
    my_server = socketserver.TCPServer(("", 0), RateLimitHandler)
    port = my_server.server_address[1]

    thread = Thread(target=serve_forever, args=(my_server,))
    thread.setDaemon(True)
    thread.start()

    return port


class TestRateLimit(unittest.TestCase):
    def test_rate_limit(self):
        port = run_server()
        print(f"Running server on port {port}")
        base_url = f"http://localhost:{port}"

        # create test package file name
        fp = tempfile.NamedTemporaryFile(delete=False)
        fp.write(b"com.test.package.name\n")
        fp.close()

        settings = dict(
            ITEM_PIPELINES={},
            DOWNLOADER_MIDDLEWARES={
                'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
                'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
                'crawler.middlewares.proxy.HttpProxyMiddleware': 100,
                'crawler.middlewares.stats.StatsMiddleware': 120,
                'crawler.middlewares.duration.DurationMiddleware': 200,
                'scrapy_useragents.downloadermiddlewares.useragents.UserAgentsMiddleware': 500,
                'crawler.middlewares.ratelimit.RatelimitMiddleware': 543
            },
            TEST_BASE_URL=base_url,
            INFLUXDB_CLIENT=InfluxDBClient({}),
            PACKAGE_FILES_ONLY=True,
            PACKAGE_FILES=[fp.name],
            RETRY_HTTP_CODES=[429],
            MEDIA_ALLOW_REDIRECTS=True,
            RETRY_TIMES=20,
        )

        process = CrawlerProcess(settings)
        process.crawl(TestSpider)
        process.start()

        os.unlink(fp.name)


if __name__ == '__main__':
    unittest.main()
