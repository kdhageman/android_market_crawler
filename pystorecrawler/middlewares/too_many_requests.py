from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

import time

MAX_RETRY_AFTER = 600

# inspired by https://stackoverflow.com/questions/43630434/how-to-handle-a-429-too-many-requests-response-in-scrapy
class IncDec429RetryMiddleware(RetryMiddleware):
    """
    Middleware for dynamically adjusting querying rate.
    Increments and decrements a backoff time when 429 and non-429 responses are seen respectively

    Configured with two parameters:
        inc: int
            the number of seconds to increment the backoff time with when a 429 response is seen
        dec: int
            the number of seconds to decrement the backoff time with when a non-429 response is seen
    """

    def __init__(self, crawler, inc, dec):
        super(IncDec429RetryMiddleware, self).__init__(crawler.settings)
        self.crawler = crawler
        self.inc= inc
        self.dec = dec
        self.cur_backoff = 0

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            crawler,
            crawler.settings.get("RATELIMIT_INC_TIME", 10),
            crawler.settings.get("RATELIMIT_DEC_TIME", 5)
        )

    def process_response(self, request, response, spider):
        if response.status == 429:
            retry_after = int(response.headers.get("Retry-After", 0))
            if retry_after:
                if retry_after > MAX_RETRY_AFTER: # do not wait longer than 10 minutes to back off
                    self.cur_backoff = MAX_RETRY_AFTER
                    log_msg = f"hit rate limit, waiting for {self.cur_backoff} seconds (reduce Retry-After header from {retry_after})"
                else:
                    self.cur_backoff = retry_after
                    log_msg = f"hit rate limit, waiting for {self.cur_backoff} seconds (respecting Retry-After header)"
            else:
                self.cur_backoff += self.inc
                log_msg = f"hit rate limit, waiting for {self.cur_backoff} seconds"
            spider.logger.warning(log_msg)
            self.pause(self.cur_backoff)
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        self.cur_backoff = max(0, self.cur_backoff - self.dec)
        if self.cur_backoff:
            spider.logger.warning(f"slowly reducing backoff, {self.cur_backoff} seconds")
        self.pause(self.cur_backoff)
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

class Base429RetryMiddleware(RetryMiddleware):
    """
    Middleware for dynamically adjusting querying rate.
    Maintains a backoff time that slowly increments every time a 429 is seen and is applied to all subsequent request.

    Configured with two parameters:
        default_backoff: int
            the default number of seconds to backoff in case of a 429, in case no Retry-After header is seen
        base_inc: float
            the number of seconds to increment the backoff time on any requests
    """

    def __init__(self, crawler, base_inc, default_backoff):
        super(Base429RetryMiddleware, self).__init__(crawler.settings)
        self.crawler = crawler
        self.default_backoff = default_backoff
        self.base_inc = base_inc
        self.base_backoff = 0

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            crawler,
            crawler.settings.get("RATELIMIT_BASE_INC", 0.05), # 50 ms
            crawler.settings.get("RATELIMIT_DEFAULT_BACKOFF", 10)
        )

    def process_response(self, request, response, spider):
        if response.status == 429:
            retry_after = int(response.headers.get("Retry-After", 0))
            if retry_after:
                if retry_after > MAX_RETRY_AFTER:
                    backoff = MAX_RETRY_AFTER
                    log_msg = f"hit rate limit, waiting for {backoff} seconds (reduce Retry-After header from {retry_after})"
                else:
                    backoff = retry_after
                    log_msg = f"hit rate limit, waiting for {backoff} seconds (respecting Retry-After header)"
            else:
                backoff = self.default_backoff
                log_msg = f"hit rate limit, waiting for {backoff} seconds"
            self.base_backoff += self.base_inc
            spider.logger.warning(log_msg)
            spider.logger.warning(f"increased base backoff to {self.base_backoff} seconds")

            self.pause(backoff)
            reason = response_status_message(response.status)
            return self._retry(request, reason, spider) or response
        self.pause(self.base_backoff)
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