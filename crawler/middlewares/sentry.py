from sentry_sdk import capture_message, configure_scope, capture_exception


class SentryMiddleware:
    def process_spider_output(self, response, result, spider):
        if not 200 <= response.status_code < 400:  # all 2xx and 3xx responses are accepted
            capture(msg="failed request", tags=_tags(response, spider))

    def process_spider_exception(self, response, exception, spider):
        if not 200 <= response.status_code < 400:  # all 2xx and 3xx responses are accepted
            capture(exception=exception, tags=_tags(response, spider))


def _tags(response, spider):
    return {
        "url": response.url,
        "status_code": response.status_code,
        "spider": spider.name
    }


def capture(msg="", exception=None, tags={}):
    with configure_scope() as scope:
        for k, v in tags:
            scope.set_tag(k, v)
        if exception:
            capture_exception(exception)
        elif msg:
            capture_message(msg)
