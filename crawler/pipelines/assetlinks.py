import json

import requests

from crawler.item import Meta


class AssetLinksPipeline:
    """
    Download /.well-known/assetlink.json
    """

    def __init__(self):
        self.seen = {}

    def process_item(self, item, spider):
        if not isinstance(item, Meta):
            return item

        for version, dat in item['versions'].items():
            for domain in dat.get("analysis", {}).get("assetlink_domains", {}):
                try:
                    al = self.seen[domain]
                except KeyError:
                    url = f"https://{domain}/.well-known/assetlinks.json"
                    resp = requests.get(url, timeout=5)
                    if resp.status_code != 200:
                        continue
                    if not "application/json" in resp.headers.get("Content-Type"):
                        continue
                    al = parse_result(resp.text)
                    self.seen[domain] = al

                dat['analysis']['assetlink_domains'][domain] = al
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
