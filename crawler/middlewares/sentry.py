from sentry_sdk import capture_message, configure_scope, capture_exception

from crawler.util import is_success


class SentryMiddleware(object):
    def process_spider_input(self, response, spider):
        if not is_success(response.status):  # all 2xx and 3xx responses are accepted
            capture(msg="failed request", tags=_tags(response, spider))

    def process_spider_exception(self, response, exception, spider):
        if not is_success(response.status):  # all 2xx and 3xx responses are accepted
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
