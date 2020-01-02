from enum import Enum

from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message
from sentry_sdk import capture_exception

from crawler.middlewares import sentry

import time

from crawler.util import market_from_spider, is_success, InfluxDBClient


class Status(Enum):
    EXPONENTIAL = 1
    INCREASING = 2
    DECREASING = 3


class _TimeWindow:
    def __init__(self, window_size):
        """
        Args:
            window_size: float in seconds
        """
        self.window_size = window_size
        self._t = None

    def start(self):
        self._t = time.time()

    @property
    def passed(self):
        if self._t:
            return self._t + self.window_size <= time.time()
        return False


class _ExponentialInterval:
    def __init__(self, inc_start, epsilon):
        self.status = Status.EXPONENTIAL
        self._interval = float(0)
        self.inc_start = float(inc_start)
        self.epsilon = epsilon
        self.lower = 0
        self.upper = 0

    def inc(self):
        """
        Increases the interval, depending on the state (exponential or other)
        Returns: float, diff in interval value
        """
        diff = 0
        self.lower = self._interval
        if self.status == Status.EXPONENTIAL:
            # exponential increase
            if not self._interval:
                self._interval = self.inc_start
                diff = self.inc_start
            else:
                diff = self._interval
                self._interval *= 2
        else:
            # binary search
            self.status == Status.INCREASING
            diff = (self.upper - self._interval) / 2
            self._interval += diff
        return diff

    def dec(self):
        """
        Decreases the interval, depending on the state (exponential or other)
        Returns: float, diff in interval value
        """
        if not self._interval:
            return 0
        self.upper = self._interval
        diff = (self._interval - self.lower) / 2
        if diff <= self.epsilon:
            return 0
        self._interval -= diff
        self.status = Status.DECREASING
        return diff

    def get(self):
        return self._interval


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

    def __init__(self, crawler, influxdb_params, inc_start=0.1, time_window_size=1000, default_backoff=600, epsilon=0.1):
        super(RatelimitMiddleware, self).__init__(crawler.settings)
        self.crawler = crawler
        self.default_backoff = default_backoff

        self.interval = _ExponentialInterval(inc_start, epsilon)
        self.window = _TimeWindow(time_window_size)

        self.c = InfluxDBClient(influxdb_params)
        self.reset_influxdb(crawler.spider)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            crawler,
            crawler.settings.get("INFLUXDB_PARAMS", {}),
            **crawler.settings.get("RATELIMIT_PARAMS", {})
        )

    def process_response(self, request, response, spider):
        status_code = response.status
        market = market_from_spider(spider)
        if status_code in [429, 403, 503]:
            backoff = float(response.headers.get("Retry-After", self.default_backoff))
            self.interval.inc()
            spider.logger.warning(f"increased interval to {self.interval.get()} seconds")

            tags = {
                'interval': self.interval.get(),
                'backoff': backoff,
                'spider': spider.name,
                'status': response.status
            }
            sentry.capture(msg="hit rate limit", tags=tags)
            self.capture_influxdb(market, response.status, {"backoff": float(backoff), "interval": self.interval.get()})

            if backoff > self.interval.get():
                self.pause(backoff)
            else:
                self.pause(self.interval.get())
            self.window.start()

            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        elif is_success(status_code):
            if self.window.passed:
                if self.interval.dec():
                    spider.logger.warning(f"decreased interval to {self.interval.get()} seconds")
                    self.capture_influxdb(market, response.status, {"interval": self.interval.get()})
                self.window.start()
        self.pause(self.interval.get())
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
