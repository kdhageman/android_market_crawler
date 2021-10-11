from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message


class StatuscodeMiddleware(RetryMiddleware):
    def process_response(self, request, response, spider):
        status_code = response.status
        if status_code >= 300:
            # error code
            try:
                reason = response_status_message(response.status)
                return spider.process_response(request, response, reason)
            except AttributeError as e:
                # for those spiders that miss the implementation of handle_spider_output
                pass
        return response
