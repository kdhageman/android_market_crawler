from urllib.parse import urlparse

from crawler import util
from crawler.util import init_proxy_pool, NoProxiesError, _is_valid


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
            if _is_valid(proxy) and host not in ["127.0.0.1", "::1", "localhost"]:
                request.meta['proxy'] = f"http://{proxy}"
            else:
                request.meta['proxy'] = None
        except NoProxiesError:
            pass
