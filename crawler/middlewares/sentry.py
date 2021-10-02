from google.protobuf.message import DecodeError
from playstoreapi.googleplay_pb2 import ResponseWrapper
from scrapy.exceptions import CloseSpider
from sentry_sdk import capture_message, configure_scope, capture_exception
from twisted.internet.error import DNSLookupError

from crawler.util import is_success


class SentryMiddleware:
    def process_spider_input(self, response, spider):
        if not is_success(response.status):  # all 2xx and 3xx responses are accepted
            tags = _tags(response, spider)

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
        if not is_success(response.status):  # all 2xx and 3xx responses are accepted

            # TODO: remove this hack!
            spider.logger.debug(f"caught exception manually for request '{response.request.url}': {exception}")
            if type(exception) == DNSLookupError:
                raise CloseSpider('saw DNS lookup error')

            capture(exception=exception, tags=_tags(response, spider))


def _tags(response, spider):
    pkg_name = response.meta.get("meta", {}).get('pkg_name', None)
    return {
        "pkg_name": pkg_name,
        "url": response.url,
        "status_code": response.status,
        "spider": spider.name
    }


def capture(msg="", exception=None, tags={}):
    with configure_scope() as scope:
        for k, v in tags.items():
            scope.set_tag(k, v)
        if exception:
            capture_exception(exception)
        elif msg:
            capture_message(msg)
