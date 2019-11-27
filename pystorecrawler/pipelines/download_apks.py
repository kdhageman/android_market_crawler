import os

import requests

from pystorecrawler.pipelines.util import get_identifier, market_from_spider, meta_directory
from pystorecrawler.item import Meta


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

        Args:
            item: dict of download URLs and store meta data
            spider: spider that crawled the market
        """
        if not isinstance(item, Meta):
            return item

        meta_dir = meta_directory(item, spider)

        for version, values in item['versions'].items():
            r = requests.get(values['dl_link'], allow_redirects=True)
            if r.status_code == 200:
                apk = r.content

                fname = f"{version}.apk"
                fpath = os.path.join(self.outdir, meta_dir, fname)

                os.makedirs(os.path.dirname(fpath), exist_ok=True)

                with open(fpath, 'wb') as f:
                    f.write(apk)
        return item