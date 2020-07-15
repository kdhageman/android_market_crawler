import os
import scrapy
from scrapy.pipelines.files import FilesPipeline

from crawler.item import Result

try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

from crawler.util import get_directory, sha256


class DownloadApksPipeline(FilesPipeline):
    """
    Retrieves APKs from a set of URLs
    """

    def __init__(self, settings):
        self.root_dir = settings.get('CRAWL_ROOTDIR', "/tmp/crawl")
        self.dst_dir = os.path.join(self.root_dir, "apks")
        try:
            os.mkdir(self.dst_dir)
        except FileExistsError:
            pass

        super().__init__(self.root_dir , settings=settings)

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
        if not isinstance(item, Result):
            return

        for version, values in item['versions'].items():
            if values.get("skip", False):
                item['versions'][version]['file_success'] = -1
            download_url = values.get('download_url', None)
            if download_url:
                info.spider.logger.debug(f"Scheduling download of '{download_url}'")
                yield scrapy.Request(download_url, meta={'meta': item['meta'], 'version': version}, priority=100)

    def item_completed(self, results, item, info):
        info.spider.logger.debug(f"Finished downloading")
        versions = item.get("versions", {})
        versions_list = list(versions.items())

        for i in range(len(results)):
            success, resultdata = results[i]
            version, values = versions_list[i]
            values['file_success'] = int(success)

            if success:  # True if download successful
                src_path = os.path.join(self.root_dir, resultdata['path'])
                with open(src_path, 'rb') as f:
                    digest = sha256(f)

                # move file to the correct location, based on its hash
                dst_path = os.path.join(self.dst_dir, f"{digest}.apk")
                os.rename(src_path, dst_path)

                values['file_path'] = dst_path
                values['file_md5'] = resultdata['checksum']
                values['file_size'] = os.path.getsize(dst_path)
                values['file_sha256'] = digest

            item['versions'][version] = values
        return item
