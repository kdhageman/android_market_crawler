import json
from json import JSONDecodeError

from sentry_sdk import capture_exception
from twisted.internet import defer

from crawler import util
from crawler.item import Result
from crawler.util import HttpClient, RequestException, response_has_content_type


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
        """
        Fetches the assetlink.json from the domains extracted from the Manifest.xml from the .apk.
        Example URL:
        - https://money.yandex.ru/.well-known/assetlinks.json (successful)
        - https://example.org/.well-known/assetlinks.json (404 not found)
        - https://{domain}/.well-known/assetlinks.json (wrong response type) # TODO: find an example link that returns the wrong response type
        """
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
                        resp = yield self.client.get(url, timeout=5, proxies=util.PROXY_POOL.get_proxy_as_dict())
                        status = resp.code
                        if status >= 400:
                            raise RequestException

                        if not response_has_content_type(resp, "application/json"):
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
