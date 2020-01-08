import statsd

from crawler.item import Result


class StatsdMiddleware(object):
    def __init__(self, params):
        params['prefix'] = "scrape"
        self.c = statsd.StatsClient(**params)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            params=crawler.settings.get('STATSD_PARAMS'),
        )

    def process_item(self, item, spider):
        if not isinstance(item, Result):
            return item

        market = item['meta']['market']

        apk_count = len([0 for d in item['versions'].values() if 'file_path' in d])

        self.c.incr(f"{market}.items")
        self.c.incr(f"{market}.apk", count=apk_count)
        return item
