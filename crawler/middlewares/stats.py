class StatsMiddleware:
    def __init__(self, crawler):
        self.crawler = crawler
        self.task = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_response(self, request, response, spider):
        resp_codes = self.crawler.stats.get_value("response_codes", default={})
        resp_codes[response.status] = resp_codes.get(response.status, 0) + 1
        self.crawler.stats.set_value("response_codes", resp_codes)

        return response
