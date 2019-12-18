from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message
from sentry_sdk import capture_exception

from crawler.middlewares.sentry import capture

import time


class RatelimitMiddleware(RetryMiddleware):
    """
    Middleware for dynamically adjusting querying rate.
    Maintains a backoff time that slowly increments every time a 429 is seen and is applied to all subsequent request.
    # inspired by https://stackoverflow.com/questions/43630434/how-to-handle-a-429-too-many-requests-response-in-scrapy

    Configured with two parameters:
        default_backoff: int
            the default number of seconds to backoff in case of a 429, in case no Retry-After header is seen
        base_inc: float
            the number of seconds to increment the backoff time on any requests
    """

    def __init__(self, crawler, ratelimit_params, influxdb_params):
        super(RatelimitMiddleware, self).__init__(crawler.settings)
        self.crawler = crawler
        self.default_backoff = ratelimit_params.get("default", 10)
        self.inc = ratelimit_params.get("inc", 0.05)
        self.interval = float(0)
        self.c = InfluxDBClient(**influxdb_params)
        self.reset_influxdb()

    def capture_influxdb(self, spiders={}):
        points = []
        for spider, vals in spiders.items():
            point = {
                "measurement": "rate_limiting",
                "tags": {
                    "spider": spider
                },
                "fields": {
                    "backoff": vals['backoff'],
                    "interval": vals['interval']
                }
            }
            points.append(point)
        try:
            self.c.write_points(points)
        except InfluxDBClientError as e:
            capture_exception(e)

    def reset_influxdb(self):
        """
        Sets all backoff/retry_after to zero
        """
        qry = "SHOW TAG VALUES WITH KEY = spider"
        results = self.c.query(qry)
        spiders = {}
        for result in results:
            for d in result:
                spiders[d['value']] = dict(
                    backoff=float(0),
                    interval=float(0)
                )
        self.capture_influxdb(spiders)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            crawler,
            ratelimit_params=crawler.settings.get("RATELIMIT_PARAMS", {}),  # 50 ms
            influxdb_params=crawler.settings.get("INFLUXDB_PARAMS", {})
        )

    def process_response(self, request, response, spider):
        if response.status == 429:
            retry_after = int(response.headers.get("Retry-After", 0))
            if retry_after:
                backoff = retry_after
                log_msg = f"hit rate limit, waiting for {backoff} seconds (respecting Retry-After header)"
            else:
                backoff = self.default_backoff
                log_msg = f"hit rate limit, waiting for {backoff} seconds"

            self.interval += self.inc

            spider.logger.warning(log_msg)
            spider.logger.warning(f"increased interval to {self.interval} seconds")
            tags = {
                'interval': self.interval,
                'backoff': backoff,
                'spider': spider.name
            }
            capture(msg="hit rate limit", tags=tags)
            self.capture_influxdb({spider.name: {"backoff": backoff, "interval": self.interval}})

            self.pause(backoff)

            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        self.pause(self.interval)
        return response

    def pause(self, t):
        """
        Pause the crawler for t seconds
        Args:
            t: int
                number of seconds to pause crawler
        """
        if t:
            self.crawler.engine.pause()
            time.sleep(t)
            self.crawler.engine.unpause()
