import os
import re

import requests


class DownloadApksPipeline:
    """
    Retrieves APKs from a set of URLs
    """

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            outdir=crawler.settings.get('APK_OUTDIR')
        )

    def __init__(self, outdir):
        self.outdir = outdir

    def process_item(self, item, spider):
        """
        Downloads APKs and stores them on disk, according to the following file structure:
        {outdir}/{market}/{pkg_name}/{version}.apk

        TODO: ensure EVERY item has these fields in their meta data OR handle missing fields correctly

        Args:
            item: dict of download URLs and store meta data
            spider: spider that crawled the market
        """
        meta = item['meta']
        version = meta['version']
        pkg_name = meta['pkg_name']
        market = spider.name
        m = re.search("(.*)_spider", market)
        if m:
            market = m.group(1)

        for url in item.get("download_urls", []):
            r = requests.get(url, allow_redirects=True)
            if r.status_code == 200:
                apk = r.content

                fname = f"{version}.apk"
                fpath = os.path.join(self.outdir, market, pkg_name, fname)

                os.makedirs(os.path.dirname(fpath), exist_ok=True)

                with open(fpath, 'wb') as f:
                    f.write(apk)
        return item
