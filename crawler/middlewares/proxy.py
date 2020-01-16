from crawler import util
from crawler.util import init_proxy_pool


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
        proxy = util.PROXY_POOL.get_proxy()
        request.meta['proxy'] = f"http://{proxy}"
