import os
from urllib.parse import urlparse

import requests
from publicsuffixlist import PublicSuffixList
from requests import HTTPError, Timeout
from sentry_sdk import capture_exception

from crawler.item import Meta
from crawler.util import get_directory, random_proxy

CONTENT_TYPE = "text/plain;charset=utf-8"


class AdsPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            outdir=crawler.settings.get('CRAWL_ROOTDIR')
        )

    def __init__(self, outdir):
        self.outdir = outdir
        self.psl = PublicSuffixList()

    def process_item(self, item, spider):
        if not isinstance(item, Meta):
            return item

        developer_website = item.get("meta", {}).get("developer_website", "")
        if not developer_website:
            return item
        parsed_url = urlparse(developer_website)
        root_domain = self.psl.privatesuffix(parsed_url.hostname)
        if not root_domain:
            return item

        # retrieve both app-ads.txt and ads.txt
        for key, path, fname in [("app_ads_path", "/app-ads.txt", "app-ads.txt"), ("ads_path", "/ads.txt", "ads.txt")]:
            parsed_url = parsed_url._replace(netloc=root_domain, path=path)

            ads_txt_url = parsed_url.geturl()
            headers = {
                "Content-Type": CONTENT_TYPE
            }

            try:
                resp = requests.get(ads_txt_url, timeout=5, headers=headers, proxies=random_proxy())
                resp.raise_for_status()
                if not "text/plain" in resp.headers.get("Content-Type", "").lower():
                    return item

                meta_dir = get_directory(item['meta'], spider)
                fpath = os.path.join(self.outdir, meta_dir, fname)

                os.makedirs(os.path.dirname(fpath), exist_ok=True)  # ensure directories exist

                with open(fpath, "wb") as f:
                    f.write(resp.content)

                item['meta'][key] = fpath
            except (HTTPError, Timeout) as e:
                capture_exception(e)
        return item
