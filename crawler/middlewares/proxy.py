import random
from crawler import util


class HttpProxyMiddleware:

    def __init__(self, proxies=[]):
        util._PROXIES = proxies
        self.proxies = proxies

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            proxies=crawler.settings.getlist("HTTP_PROXIES")
        )

    def process_request(self, request, spider):
        if self.proxies:
            proxy = random.choice(self.proxies)
            request.meta['proxy'] = proxy
