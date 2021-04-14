from datetime import datetime


def report_endtime(request, spider, exception=None):
    start_time = request.meta.get('__request_start_time', None)
    if not start_time:
        spider.logger.debug(f"Failed to find start time of request {request.url}")
        return
    end_time = datetime.now()
    passed = end_time - start_time
    if exception:
        spider.logger.debug(f"Took {passed} to process {request.url}, but resulted in an exception:\n\n{exception}")
    else:
        spider.logger.debug(f"Took {passed} to process {request.url}")


class DurationMiddleware:
    def process_request(self, request, spider):
        request.meta['__request_start_time'] = datetime.now()

    def process_response(self, request, response, spider):
        report_endtime(request, spider)
        return response

    def process_exception(self, request, exception, spider):
        report_endtime(request, spider, exception=exception)
