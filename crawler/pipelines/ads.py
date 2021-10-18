import os
import shutil
import tempfile
from urllib.parse import urlparse

import scrapy
from publicsuffixlist import PublicSuffixList
from scrapy.pipelines.files import FilesPipeline

from crawler.middlewares.sentry import capture
from crawler.util import get_directory, sha256

CONTENT_TYPE = "text/plain;charset=utf-8"


class AdsPipeline(FilesPipeline):
    def __init__(self, settings):
        self.tmpdir = tempfile.mkdtemp()
        super().__init__(self.tmpdir, settings=settings)
        self.root_dir = settings.get('CRAWL_ROOTDIR', "/tmp/crawl")
        self.psl = PublicSuffixList()

    def close_spider(self, spider):
        # delete temporary directory when closing spider
        shutil.rmtree(self.tmpdir)

    @classmethod
    def from_settings(cls, settings):
        return cls(
            settings=settings
        )

    def get_media_requests(self, item, info):
        developer_website = item.get("meta", {}).get("developer_website", "")
        if not developer_website:
            return
        parsed_url = urlparse(developer_website)
        root_domain = self.psl.privatesuffix(parsed_url.hostname)
        if not root_domain:
            return
        paths = ["/app-ads.txt", "/ads.txt"]
        for path in paths:
            url = parsed_url._replace(netloc=root_domain, path=path).geturl()
            item['download_timeout'] = 3
            info.spider.logger.debug(f"scheduling (app-)ads.txt from '{url}'")
            yield scrapy.Request(url, meta=item)

    def media_failed(self, failure, request, info):
        pass

    def item_completed(self, results, item, info):
        meta_dir = get_directory(item['meta'], info.spider)

        for success, resultdata in results:
            if success:
                try:
                    path = urlparse(resultdata['url']).path
                    if path == '/app-ads.txt':
                        fname_prefix = 'app_ads'
                        key = 'app_ads_path'
                    elif path == '/ads.txt':
                        fname_prefix = 'ads'
                        key = 'ads_path'
                    else:
                        continue

                    tmp_filepath = os.path.join(self.tmpdir, resultdata['path'])
                    with open(tmp_filepath, 'r') as f:
                        content = f.read()
                    digest = sha256(bytes(content, 'utf-8'))

                    output_fname = f"{fname_prefix}.{digest}.txt"
                    output_fpath = os.path.join(self.root_dir, meta_dir, output_fname)

                    with open(output_fpath, "wb") as f:
                        f.write(bytes(content, 'utf-8'))

                    os.remove(tmp_filepath)
                    item['meta'][key] = output_fpath
                except Exception as e:
                    capture(exception=e)
        return item
