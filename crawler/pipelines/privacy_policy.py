import os

from sentry_sdk import capture_exception
from twisted.internet import defer
from twisted.web._newclient import ResponseFailed

from crawler.item import Result
from crawler.util import get_directory, random_proxy, HttpClient, RequestException

FNAME = "privacy_policy.html"


class PrivacyPolicyPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        client = HttpClient(crawler)
        return cls(
            client=client,
            outdir=crawler.settings.get('CRAWL_ROOTDIR')
        )

    def __init__(self, client, outdir):
        self.client = client
        self.outdir = outdir

    @defer.inlineCallbacks
    def process_item(self, item, spider):
        if not isinstance(item, Result):
            return item

        privacy_policy_url = item['meta'].get("privacy_policy_url", "")

        if privacy_policy_url:
            try:
                resp = yield self.client.get(privacy_policy_url, timeout=5, proxies=random_proxy())
                item['meta']['privacy_policy_status'] = resp.code
                if resp.code >= 400:
                    raise RequestException

                meta_dir = get_directory(item['meta'], spider)
                fpath = os.path.join(self.outdir, meta_dir, FNAME)

                os.makedirs(os.path.dirname(fpath), exist_ok=True)  # ensure directories exist

                with open(fpath, "wb") as f:
                    content = yield resp.content()
                    f.write(content)

                item['meta']['privacy_policy_path'] = fpath
            except (RequestException, ResponseFailed) as e:
                capture_exception(e)
        defer.returnValue(item)