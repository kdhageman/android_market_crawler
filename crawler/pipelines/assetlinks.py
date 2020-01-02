import json
from json import JSONDecodeError

from requests import RequestException
from sentry_sdk import capture_exception

from crawler.item import Meta
from crawler.util import random_proxy, HttpClient


class AssetLinksPipeline:
    """
    Download /.well-known/assetlink.json
    """

    def __init__(self, client):
        self.client = client
        self.seen = {}

    @classmethod
    def from_crawler(cls, crawler):
        client = HttpClient(crawler)
        return cls(client)

    def process_item(self, item, spider):
        if not isinstance(item, Meta):
            return item

        for version, dat in item['versions'].items():
            for domain in dat.get("analysis", {}).get("assetlink_domains", {}):
                try:
                    al = self.seen[domain]
                except KeyError:
                    try:
                        url = f"https://{domain}/.well-known/assetlinks.json"
                        resp = self.client.get(url, timeout=5, proxies=random_proxy())
                        if resp.status_code != 404:
                            resp.raise_for_status()
                        if "application/json" not in resp.headers.get("Content-Type", ["application/json"]):
                            continue
                        al = parse_result(resp.text)
                        self.seen[domain] = al
                    except RequestException as e:
                        capture_exception(e)
                        continue
                    except JSONDecodeError:
                        continue

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
