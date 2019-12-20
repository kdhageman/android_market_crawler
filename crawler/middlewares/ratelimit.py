from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message
from sentry_sdk import capture_exception

from crawler.middlewares.sentry import capture

import time

from crawler.util import market_from_spider, is_success


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

    def __init__(self, crawler, ratelimit_params, influxdb_params):
        super(RatelimitMiddleware, self).__init__(crawler.settings)
        self.crawler = crawler
        self.default_backoff = float(ratelimit_params.get("default_backoff", 10))
        self.base_inc = 0.02
        self.exp_inc = self.base_inc
        self.interval = float(0)
        self.upper_limit_interval = 0  # upper interval were converging towards
        self.lower_limit_interval = 0  # lower interval were converging towards
        self.tstart = time.time()  # start time of current delta-slot
        self.ok_window_duration = ratelimit_params.get("ok_window_duration", 10)  # window duration in seconds
        self.epsilon = float(ratelimit_params.get("epsilon", 1))  # stop reducing interval when almost converged with limit interval, epsilon defines what
        self.first_ok = False

        self.c = InfluxDBClient(**influxdb_params)
        self.reset_influxdb(crawler.spider)

    def capture_influxdb(self, market, status, fields):
        points = [{
            "measurement": "rate_limiting",
            "tags": {
                "market": market,
                "status": status
            },
            "fields": fields
        }]
        try:
            self.c.write_points(points)
        except (InfluxDBClientError, InfluxDBServerError) as e:
            print(e)
            capture_exception(e)

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

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            crawler,
            ratelimit_params=crawler.settings.get("RATELIMIT_PARAMS", {}),  # 50 ms
            influxdb_params=crawler.settings.get("INFLUXDB_PARAMS", {})
        )

    def process_response(self, request, response, spider):
        if response.status in [429, 403]:
            self.lower_limit_interval = max(self.interval, self.lower_limit_interval)
            self.first_ok = True

            if not self.upper_limit_interval:
                # exponential backoff when there is no known upper limit
                self.interval += self.exp_inc
                self.exp_inc *= 2  # exponential interval
            else:
                # there is an known upper limit, so converge to it
                self.interval += (self.upper_limit_interval - self.interval) / 2

            retry_after = float(response.headers.get("Retry-After", 0))
            backoff = retry_after if retry_after else self.default_backoff

            spider.logger.warning(f"increased interval to {self.interval} seconds")
            tags = {
                'interval': self.interval,
                'backoff': backoff,
                'spider': spider.name,
                'status': response.status
            }
            capture(msg="hit rate limit", tags=tags)
            market = market_from_spider(spider)
            self.capture_influxdb(market, response.status, {"backoff": float(backoff), "interval": self.interval})

            self.pause(backoff)

            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response

        if is_success(response.status):
            self.exp_inc = self.base_inc  # reset interval increment val
            if self.first_ok:
                self.first_ok = False
                # first OK response after rate limiting
                self.tstart = time.time()
            elif time.time() - self.tstart >= self.ok_window_duration:
                # converge towards
                diff = (self.interval - self.lower_limit_interval) / 2
                if diff > self.epsilon:
                    self.upper_limit_interval = min(self.upper_limit_interval,
                                                    self.interval) if self.upper_limit_interval else self.interval
                    self.interval -= diff
                    self.tstart = time.time()
                    market = market_from_spider(spider)
                    self.capture_influxdb({market, response.status, {"interval": self.interval}})
                    spider.logger.warning(f"decreased interval to {self.interval} seconds")

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
