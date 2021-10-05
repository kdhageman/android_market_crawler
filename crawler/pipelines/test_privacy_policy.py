import shutil
import tempfile
from unittest import TestCase

from scrapy import signals
from scrapy.http import Response, HtmlResponse, TextResponse
from scrapy.utils.signal import disconnect_all
from twisted.internet import defer

from crawler.pipelines.privacy_policy import PrivacyPolicyPipeline
from crawler.util import TestSpider


def _mocked_download_func(request, info):
    return Response(url=request.url, status=200, body=bytes("test", 'utf-8'), request=request)


class TestPrivacyPolicyPipeline(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

        settings = {
            'CRAWL_ROOTDIR': self.tmpdir
        }
        self.pipe = PrivacyPolicyPipeline(settings)
        self.pipe.download_func = _mocked_download_func
        self.spider = TestSpider()

    @defer.inlineCallbacks
    def test_get_media_requests(self):
        self.pipe.open_spider(self.spider)

        item = dict(
            meta=dict(
                pkg_name="com.text.example",
                privacy_policy_url="http://localhost/privacy_policy.html"  # does not matter
            )
        )
        # TODO: make this yield work
        res = yield self.pipe.process_item(item, self.spider)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

        for name, signal in vars(signals).items():
            if not name.startswith('_'):
                disconnect_all(signal)
