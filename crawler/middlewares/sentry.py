from google.protobuf.message import DecodeError
from playstoreapi.googleplay_pb2 import ResponseWrapper
from scrapy.exceptions import CloseSpider
from sentry_sdk import capture_message, configure_scope, capture_exception
from twisted.internet.error import DNSLookupError

from crawler.util import is_success


class SentryMiddleware:
    def process_spider_input(self, response, spider):
        if not is_success(response.status):  # all 2xx and 3xx responses are accepted
            tags = _response_tags(response, spider)

            # handle protobuf responses specifically, as they return an error message in the body of a 500 response
            if response.status == 500:
                try:
                    err_msg = ResponseWrapper.FromString(response.body).commands.displayErrorMessage
                    e = Exception(err_msg)
                    capture(exception=e, tags=tags)
                    return
                except (DecodeError, AttributeError):
                    pass

            capture(msg="failed request", tags=tags)

    def process_spider_exception(self, response, exception, spider):
        capture(exception=exception, tags=_response_tags(response, spider))

    def process_response(self, request, response, spider):
        return response

    def process_exception(self, request, exception, spider):
        if type(exception) == DNSLookupError:
            # explicitly output
            spider.logger.error(f"dns lookup error for request '{request}': {exception}")
            spider.logger.error(f"request headers: {str(request.headers)}")
            spider.logger.error(f"request meta: {str(request.meta)}")
            raise CloseSpider('dns lookup error')
        capture(exception=exception, tags=_request_tags(request, spider))

def _request_tags(request, spider):
    return {
        "url": request.url,
        "spider": spider.name,
    }


def _response_tags(response, spider):
    res = _request_tags(response.request, spider)
    pkg_name = response.meta.get("meta", {}).get('pkg_name', None)
    res['status_code'] = response.status
    res['pkg_name'] = pkg_name

    return res


def capture(msg="", exception=None, tags={}):
    with configure_scope() as scope:
        for k, v in tags.items():
            scope.set_tag(k, v)
        if exception:
            capture_exception(exception)
        elif msg:
            capture_message(msg)
