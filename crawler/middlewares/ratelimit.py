import time

from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

from crawler import util
from crawler.middlewares import sentry
from crawler.util import market_from_spider


class RatelimitMiddleware(RetryMiddleware):
    """
    Middleware for dynamically adjusting querying rate.
    Maintains a backoff time that increments exponentially every time a 429 is seen and is applied to all subsequent request.
    # inspired by https://stackoverflow.com/questions/43630434/how-to-handle-a-429-too-many-requests-response-in-scrapy

    Configured with two parameters:
        default_backoff: int
            the default number of seconds to backoff in case of a 429, in case no Retry-After header is seen
        base_inc: float
            the number of seconds to increment the backoff time on any requests
    """

    def __init__(self, crawler, influxdb_client, default_backoff=600, codes=[429], interval=0):
        super(RatelimitMiddleware, self).__init__(crawler.settings)
        self.crawler = crawler
        self.default_backoff = default_backoff
        self.codes = codes
        self.interval = interval

        self.influxdb_client = influxdb_client
        self.reset_influxdb(crawler.spider)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            crawler,
            crawler.settings.get("INFLUXDB_CLIENT"),
            **crawler.settings.get("RATELIMIT_PARAMS", {})
        )

    def process_response(self, request, response, spider):
        status_code = response.status
        market = market_from_spider(spider)

        if status_code in self.codes:
            proxy = request.meta.get('proxy', None)
            backoff = float(response.headers.get("Retry-After", self.default_backoff))

            tags = {
                'backoff': backoff,
                'spider': spider.name,
                'status': response.status,
                'proxy': proxy
            }
            sentry.capture(msg="hit rate limit", tags=tags)
            self.capture_influxdb(market, response.status, {"backoff": float(backoff)})

            util.PROXY_POOL.backoff(proxy, seconds=backoff)

            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        self.pause(self.interval)
        return response

    def pause(self, t):
        """
        Pause the crawler 't' seconds
        """
        try:
            self.crawler.engine.pause()
            time.sleep(t)
        finally:
            self.crawler.engine.unpause()

    def capture_influxdb(self, market, status, fields):
        point = {
            "measurement": "rate_limiting",
            "tags": {
                "market": market,
                "status": status
            },
            "fields": fields
        }
        self.influxdb_client.add_point(point)

    def reset_influxdb(self, spider):
        """
        Sets all backoff/retry_after to zero
        """
        market = market_from_spider(spider)
        fields = {
            'backoff': float(0),
            'interval': float(0)
        }
        self.capture_influxdb(market, 200, fields)
