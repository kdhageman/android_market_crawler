import os

import requests
from requests import HTTPError
from sentry_sdk import capture_exception

from crawler.item import Meta
from crawler.pipelines.util import get_directory

FNAME = "ads.txt"


class AdsTxtPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            outdir=crawler.settings.get('CRAWL_ROOTDIR')
        )

    def __init__(self, outdir):
        self.outdir = outdir

    def process_item(self, item, spider):
        if not isinstance(item, Meta):
            return item

        developer_website = item.get("meta", {}).get("developer_website", "")

        if developer_website:
            ads_txt_url = f"{developer_website}/ads.txt"
            resp = requests.get(ads_txt_url, timeout=2)
            try:
                resp.raise_for_status()

                meta_dir = get_directory(item['meta'], spider)
                fpath = os.path.join(self.outdir, meta_dir, FNAME)

                os.makedirs(os.path.dirname(fpath), exist_ok=True)  # ensure directories exist

                with open(fpath, "wb") as f:
                    f.write(resp.content)

                item['meta']['ads_txt_path'] = fpath

            except HTTPError as e:
                capture_exception(e)
        return item