import os
from datetime import datetime

from sentry_sdk import capture_exception
from twisted.internet import defer

from crawler import util
from crawler.util import get_directory, HttpClient, RequestException


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
        privacy_policy_url = item['meta'].get("privacy_policy_url", "")

        if privacy_policy_url:
            try:
                resp = yield self.client.get(privacy_policy_url, timeout=5, proxies=util.PROXY_POOL.get_proxy_as_dict())
                item['meta']['privacy_policy_status'] = resp.code
                if resp.code >= 400:
                    raise RequestException

                meta_dir = get_directory(item['meta'], spider)
                ts = datetime.now().strftime("%s")
                fname = f"privacy_policy.{ts}.html"
                fpath = os.path.join(self.outdir, meta_dir, fname)

                os.makedirs(os.path.dirname(fpath), exist_ok=True)  # ensure directories exist

                with open(fpath, "wb") as f:
                    content = yield resp.content()
                    f.write(content)

                item['meta']['privacy_policy_path'] = fpath
            except Exception as e:
                capture_exception(e)
        defer.returnValue(item)