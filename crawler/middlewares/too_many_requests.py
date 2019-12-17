from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message
from crawler.middlewares.sentry import capture

import time


class Base429RetryMiddleware(RetryMiddleware):
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
            crawler.settings.get("RATELIMIT_BASE_INC", 0.05),  # 50 ms
            crawler.settings.get("RATELIMIT_DEFAULT_BACKOFF", 10)
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

            self.base_backoff += self.base_inc

            spider.logger.warning(log_msg)
            spider.logger.warning(f"increased base backoff to {self.base_backoff} seconds")
            tags = {
                'backoff': backoff,
                'retry_after': retry_after,
                'spider': spider.name
            }
            capture(msg="hit rate limit", tags=tags)

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
