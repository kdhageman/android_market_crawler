import json
from json import JSONDecodeError

from sentry_sdk import capture_exception
from twisted.internet import defer

from crawler.item import Result
from crawler.util import random_proxy, HttpClient, RequestException, response_has_content_type


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

    @defer.inlineCallbacks
    def process_item(self, item, spider):
        if not isinstance(item, Result):
            return item

        for version, dat in item['versions'].items():
            for domain in dat.get("analysis", {}).get("assetlink_domains", {}):
                status = 0
                try:
                    al = self.seen[domain]
                except KeyError:
                    try:
                        url = f"https://{domain}/.well-known/assetlinks.json"
                        resp = yield self.client.get(url, timeout=5, proxies=random_proxy())
                        status = resp.code
                        if resp.code >= 400:
                            raise RequestException

                        if response_has_content_type(resp, "application/json", default=True):
                            continue
                        txt = yield resp.text()
                        al = parse_result(txt)
                        self.seen[domain] = al
                    except JSONDecodeError:
                        continue
                    except Exception as e:
                        capture_exception(e)
                        continue
                dat['analysis']['assetlink_domains'][domain] = al
                dat['analysis']['assetlink_status'][domain] = status
            item['versions'][version] = dat
        defer.returnValue(item)


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
