from urllib.parse import urlparse

from crawler import util
from crawler.util import init_proxy_pool, NoProxiesError


class HttpProxyMiddleware:

    def __init__(self, crawler, proxies=[]):
        init_proxy_pool(crawler, proxies)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            crawler,
            proxies=crawler.settings.getlist("HTTP_PROXIES")
        )

    def process_request(self, request, spider):
        try:
            host = urlparse(request.url).hostname
            proxy = util.PROXY_POOL.get_proxy()
            # do not proxy towards localhost
            if host not in ["127.0.0.1", "::1", "localhost"]:
                request.meta['proxy'] = f"http://{proxy}"
        except NoProxiesError:
            pass
