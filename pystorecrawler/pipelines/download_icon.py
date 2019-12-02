import os

from urllib3.exceptions import HTTPError

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
        try:
            r = get(url, self.timout)
            if r.status_code == 200:
                meta_dir = meta_directory(item, spider)

                fpath = os.path.join(self.outdir, meta_dir, "icon.ico")

                os.makedirs(os.path.dirname(fpath), exist_ok=True)  # ensure directories exist

                with open(fpath, 'wb') as f:
                    f.write(r.content)

                res['meta']['icon_path'] = fpath
            else:
                spider.logger.warning(f"got non-200 HTTP response for '{url}': {r.status_code}")
        except HTTPError as e:
            spider.logger.warning(f"error during HTTP request: {e}")
        except TimeoutError as e:
            spider.logger.warning(f"{e}")
        return res

