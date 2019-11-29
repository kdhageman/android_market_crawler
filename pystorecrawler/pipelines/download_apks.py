import os

from pystorecrawler.item import Meta
from pystorecrawler.pipelines.util import meta_directory, get


class DownloadApksPipeline:
    """
    Retrieves APKs from a set of URLs
    """

    def __init__(self, outdir, timeout):
        self.outdir = outdir
        self.timeout = timeout / 1000  # milliseconds to seconds

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            outdir=crawler.settings.get('CRAWL_ROOTDIR', "/tmp/crawl"),
            timeout=crawler.settings.get("DOWNLOAD_TIMEOUT", 10 * 60 * 1000)
        )

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

        res = item

        meta_dir = meta_directory(item, spider)

        for version, values in item['versions'].items():
            download_url = values.get('download_url', None)
            if download_url:  # in case the download url is empty, ignore the version
                r = get(values['download_url'], self.timeout)
                if not r:
                    spider.logger.warning(f"request timeout for '{values['download_url']}")
                elif r.status_code == 200:
                    apk = r.content

                    fname = f"{version}.apk"
                    fpath = os.path.join(self.outdir, meta_dir, fname)

                    os.makedirs(os.path.dirname(fpath), exist_ok=True)  # ensure directories exist

                    with open(fpath, 'wb') as f:
                        f.write(apk)

                    # add file path to original item
                    values['file_path'] = fpath
                    res['versions'][version] = values
        return res
