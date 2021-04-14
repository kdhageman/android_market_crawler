from datetime import datetime


def report_endtime(request, spider, exception=None):
    start_time = request.meta['__request_start_time']
    end_time = datetime.now()
    passed = end_time - start_time
    if exception:
        spider.logger.debug(f"Took {passed} to process {request.url}, but resulted in an exception:\n\n{exception}")
    else:
        spider.logger.debug(f"Took {passed} to process {request.url}")


class DurationMiddleware:
    def process_request(self, request, spider):
        request.meta['__request_start_time'] = datetime.now()
        return request

    def process_response(self, request, response, spider):
        report_endtime(request, spider)
        return response

    def process_exception(self, request, exception, spider):
        report_endtime(request, spider, exception=exception)