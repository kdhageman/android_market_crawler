import json
import os
import shutil
import tempfile
from urllib.parse import urlparse

import scrapy
from scrapy.pipelines.files import FilesPipeline


class AssetLinksPipeline(FilesPipeline):
    """
    Download /.well-known/assetlink.json
    """

    def __init__(self, settings):
        self.tmpdir = tempfile.mkdtemp()
        super().__init__(self.tmpdir, settings=settings)

        self.seen = {}

    def close_spider(self, spider):
        # delete temporary directory when closing spider
        shutil.rmtree(self.tmpdir)

    @classmethod
    def from_settings(cls, settings):
        return cls(
            settings=settings
        )

    def get_media_requests(self, item, info):
        for version, dat in item['versions'].items():
            for domain in dat.get("analysis", {}).get("assetlink_domains", {}):
                if domain not in self.seen:
                    if len(domain.split(".")) > 1:
                        url = f"https://{domain}/.well-known/assetlinks.json"
                        item['download_timeout'] = 5
                        info.spider.logger.debug(f"scheduling asset links from '{url}'")
                        yield scrapy.Request(url, meta=item)
                    else:
                        info.spider.logger.debug(f"ignoring assetlink domain '{domain}' because it appears to be invalid")

    def item_completed(self, results, item, info):
        for success, resultdata in results:
            if success:
                try:
                    domain = urlparse(resultdata['url']).hostname
                    fpath = os.path.join(self.tmpdir, resultdata['path'])
                    with open(fpath, 'r') as f:
                        file_content = f.read()
                        self.seen[domain] = parse_result(file_content)
                    os.remove(fpath)
                except Exception as e:
                    info.spider.logger.warn(f"failed to extract assetlinks from file: {e}")

        for version, dat in item['versions'].items():
            for domain in dat.get("analysis", {}).get("assetlink_domains", {}).keys():
                al = self.seen.get(domain, None)
                dat['analysis']['assetlink_domains'][domain] = al
                if al:
                    dat['analysis']['assetlink_status'][domain] = 200
            item['versions'][version] = dat
        return item


def parse_result(raw):
    res = {}
    statements = json.loads(raw)
    for statement in statements:
        target = statement.get('target', {})
        if target.get("namespace", "") == "android_app":
            pkg_name = target.get("package_name", "")
            fps = target.get("sha256_cert_fingerprints", "")
            fps = [fp.lower().replace(":", "") for fp in fps]
            res[pkg_name] = fps
    return res
