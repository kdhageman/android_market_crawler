import os
import scrapy
from scrapy.pipelines.files import FilesPipeline
from pystorecrawler.pipelines.util import get_directory, sha256


class DownloadIconPipeline(FilesPipeline):
    """
    Downloads and stores the icon of an app store
    """
    def __init__(self, settings):
        self.outdir = settings.get("CRAWL_ROOTDIR", "/tmp/crawl")
        super().__init__(self.outdir, settings=settings)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            crawler.settings
        )

    def file_path(self, request, response=None, info=None):
        item = request.meta
        dir = get_directory(item['meta'], info.spider)
        return os.path.join(dir, "icon.ico")

    def get_media_requests(self, item, info):
        icon_url = item['meta'].get('icon_url', None)
        if icon_url:
            yield scrapy.Request(icon_url, meta={'meta': item['meta']})

    def item_completed(self, results, item, info):
        if results:
            success, resultdata = results[0]
            if success:
                path = os.path.join(self.outdir, resultdata['path'])
                item['meta']['icon_path'] = path
                item['meta']['icon_md5'] = resultdata['checksum']
                with open(path, 'rb') as f:
                    item['meta']['icon_sha256'] = sha256(f)
        return item
