import os

from pystorecrawler.item import Meta
from pystorecrawler.pipelines.util import meta_directory, get

class DownloadIconPipeline:
    """
    Downloads and stores the icon of an app store
    """
    def __init__(self, outdir, timeout):
        self.outdir = outdir
        self.timout = timeout

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            outdir=crawler.settings.get("CRAWL_ROOTDIR"),
            timeout=crawler.settings.get("DOWNLOAD_TIMEOUT")
        )

    def process_item(self, item, spider):
        """
        Downloads icon and stores it on disk, according to the following file structure:
        {outdir}/{market}/{pkg_name}/icon.{ext}

        Args:
            item: dict of download URLs and store meta data
            spider: spider that crawled the market
        """
        if not isinstance(item, Meta):
            return item

        res = item

        url = item['meta']['icon_url']
        r = get(url, self.timout)
        if not r:
            spider.logger.warning(f"request timeout for '{url}")
        elif r.status_code == 200:
            meta_dir = meta_directory(item, spider)

            fpath = os.path.join(self.outdir, meta_dir, "icon.ico")

            with open(fpath, 'wb') as f:
                f.write(r.content)

            res['meta']['icon_path'] = fpath

        return res

