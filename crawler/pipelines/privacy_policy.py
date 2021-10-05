import os
from datetime import datetime
import scrapy
from scrapy.pipelines.files import FilesPipeline

from crawler.middlewares.sentry import _response_tags, capture
from crawler.util import get_directory


class PrivacyPolicyPipeline(FilesPipeline):
    def __init__(self, settings):
        self.root_dir = settings.get('CRAWL_ROOTDIR', "/tmp/crawl")
        super().__init__(self.root_dir, settings=settings)

    @classmethod
    def from_settings(cls, settings):
        return cls(
            settings=settings
        )

    def file_path(self, request, response=None, info=None, *, item=None):
        ts = datetime.now().strftime("%s")
        meta_dir = get_directory(item['meta'], info.spider)
        fname = f"privacy_policy.{ts}.html"
        fpath = os.path.join(self.root_dir, meta_dir, fname)
        return fpath

    def media_failed(self, failure, request, info):
        """Handler for failed downloads"""
        info.spider.logger.debug(f"failed to download from '{request.url}': {failure}")
        tags = _response_tags(request, info.spider)
        capture(exception=failure, tags=tags)
        return super().media_failed(self, failure, request, info)

    def get_media_requests(self, item, info):
        privacy_policy_url = item['meta'].get('privacy_policy_url')
        if privacy_policy_url:
            info.spider.logger.debug(f"scheduling download privacy policy from '{privacy_policy_url}'")
            item['download_timeout'] = 5
            yield scrapy.Request(privacy_policy_url, meta=item)

    def item_completed(self, results, item, info):
        if len(results) != 1:
            info.spider.logger.debug("collected more than one privacy policy, using first only")
        success, resultdata = results[0]
        if success:
            item['meta']['privacy_policy_path'] = resultdata['path']
            item['meta']['privacy_policy_status'] = 200
        else:
            # TODO: set correct HTTP status
            item['meta']['privacy_policy_status'] = 1000
        return item
