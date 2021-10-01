import os
import scrapy
from scrapy.pipelines.files import FilesPipeline

from crawler.middlewares.sentry import capture, _tags

try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

from crawler.util import get_directory, sha256, get_identifier


class DownloadApksPipeline(FilesPipeline):
    """
    Retrieves APKs from a set of URLs
    """

    def __init__(self, settings):
        self.root_dir = settings.get('CRAWL_ROOTDIR', "/tmp/crawl")
        self.dst_dir = os.path.join(self.root_dir, "apks")
        try:
            os.makedirs(self.dst_dir, exist_ok=True)
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
        identifier = get_identifier(item['meta'])

        for version, values in item['versions'].items():
            if values.get("skip", False):
                item['versions'][version]['file_success'] = -1
                continue
            download_url = values.get('download_url', None)
            headers = values.get("headers", None)
            cookies = values.get("cookies", None)
            if download_url:
                info.spider.logger.debug(f"scheduling download for '{identifier}' from '{download_url}'")
                yield scrapy.Request(download_url, headers=headers, cookies=cookies, meta={'meta': item['meta'], 'version': version}, priority=100)

    def media_failed(self, failure, request, info):
        """Handler for failed downloads"""
        info.spider.logger.debug(f"failed to download from '{request.url}': {failure}")
        tags = _tags(request,info.spider)
        capture(exception=failure, tags=tags)
        return super().media_failed(self, failure, request, info)

    def item_completed(self, results, item, info):
        identifier = get_identifier(item['meta'])

        if len(results) == 0:
            info.spider.logger.debug(f"had no APKs to download for '{identifier}'")
            return item

        info.spider.logger.debug(f"finished APK downloading for '{identifier}'")
        versions = item.get("versions", {})
        versions_list = list(versions.items())

        for i in range(len(results)):
            success, resultdata = results[i]
            version, values = versions_list[i]
            values['file_success'] = int(success)

            if success:  # True if download successful
                src_path = os.path.join(self.root_dir, resultdata['path'])
                if os.path.exists(src_path):
                    with open(src_path, 'rb') as f:
                        digest = sha256(f)

                    # move file to the correct location, based on its hash
                    dst_path = os.path.join(self.dst_dir, f"{digest}.apk")
                    os.rename(src_path, dst_path)

                    values['file_path'] = dst_path
                    values['file_md5'] = resultdata['checksum']
                    values['file_size'] = os.path.getsize(dst_path)
                    values['file_sha256'] = digest
                else:
                    # download successful, but the file does not exist
                    info.spider.logger.debug(f"failed to store downloaded APK for '{identifier}' to '{src_path}'")
            item['versions'][version] = values

        return item
