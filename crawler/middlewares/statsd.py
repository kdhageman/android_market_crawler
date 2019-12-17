import statsd

from crawler.middlewares.util import is_success
from crawler.pipelines.util import market_from_spider


class StatsdMiddleware:
    def __init__(self, host, port):
        self.c = statsd.StatsClient(host, port, prefix='scrape')

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            host=crawler.settings.get('STATSD_HOST'),
            port=crawler.settings.getint('STATSD_PORT')
        )

    def process_response(self, request, response, spider):
        status = "ok" if is_success(response.status) else "failed"
        market = market_from_spider(spider)
        for suffix in [status, "total"]:
            self.c.incr(f"{market}.{suffix}")
        return response
