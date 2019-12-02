import os
import scrapy
from scrapy.pipelines.files import FilesPipeline

try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

from pystorecrawler.pipelines.util import get_directory, sha256


class DownloadApksPipeline(FilesPipeline):
    """
    Retrieves APKs from a set of URLs
    """

    def __init__(self, settings):
        self.outdir = settings.get('CRAWL_ROOTDIR', "/tmp/crawl")
        super().__init__(self.outdir, settings=settings)

    @classmethod
    def from_settings(cls, settings):
        return cls(
            settings=settings
        )

    def file_path(self, request, response=None, info=None):
        item = request.meta
        dir = get_directory(item['meta'], info.spider)
        version = item['version']
        version = version.replace(" ", "_")
        fname = f"{version}.apk"
        return os.path.join(dir, fname)

    def get_media_requests(self, item, info):
        for version, values in item['versions'].items():
            download_url = values.get('download_url', None)
            if download_url:
                yield scrapy.Request(download_url, meta={'meta': item['meta'], 'version': version}, priority=100)

    def item_completed(self, results, item, info):
        versions_list = list(item['versions'].items())

        for i in range(len(results)):
            success, resultdata = results[i]
            if success: # True if download successful
                version, values = versions_list[i]
                path = os.path.join(self.outdir, resultdata['path'])
                values['file_path'] = path
                values['file_md5'] = resultdata['checksum']

                with open(path, 'rb') as f:
                    values['file_sha256'] = sha256(f)

                item['versions'][version] = values
        return item
