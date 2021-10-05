import os
from urllib.parse import urlparse

from publicsuffixlist import PublicSuffixList
from sentry_sdk import capture_exception
from twisted.internet import defer

from crawler import util
from crawler.pipelines.util import timed
from crawler.util import get_directory, HttpClient, RequestException, response_has_content_type, ContentTypeError, \
    sha256

CONTENT_TYPE = "text/plain;charset=utf-8"


class AdsPipeline:
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
        self.psl = PublicSuffixList()

    @timed("AdsPipeline")
    @defer.inlineCallbacks
    def process_item(self, item, spider):
        """
        Fetches the /app-ads.txt and /ads.txt from the developer website of a given package
        Example URL:
        - http://whisperarts.com/app-ads.txt (successful)
        - https://example.org/app-ads.txt (404 not found)
        """

        developer_website = item.get("meta", {}).get("developer_website", "")
        if not developer_website:
            return item
        parsed_url = urlparse(developer_website)
        root_domain = self.psl.privatesuffix(parsed_url.hostname)
        if not root_domain:
            return item

        # retrieve both app-ads.txt and ads.txt
        for key, status_key, path, fname_prefix in [
            ("app_ads_path", "app_ads_status", "/app-ads.txt", "app_ads"),
            ("ads_path", "ads_status", "/ads.txt", "ads")
        ]:
            parsed_url = parsed_url._replace(netloc=root_domain, path=path)

            ads_txt_url = parsed_url.geturl()
            headers = {
                "Content-Type": CONTENT_TYPE
            }

            try:
                resp = yield self.client.get(ads_txt_url, timeout=5, headers=headers, proxies=util.PROXY_POOL.get_proxy_as_dict())
                item['meta'][status_key] = resp.code
                if resp.code >= 400:
                    raise RequestException
                if not response_has_content_type(resp, "text/plain"):
                    raise ContentTypeError

                meta_dir = get_directory(item['meta'], spider)

                content = yield resp.content()
                digest = sha256(content)

                fname = f"{fname_prefix}.{digest}.txt"
                fpath = os.path.join(self.outdir, meta_dir, fname)

                os.makedirs(os.path.dirname(fpath), exist_ok=True)  # ensure directories exist

                with open(fpath, "wb") as f:
                    f.write(content)

                item['meta'][key] = fpath
            except ContentTypeError:
                pass
            except Exception as e:
                capture_exception(e)

        defer.returnValue(item)
