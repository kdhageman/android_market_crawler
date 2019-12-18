import statsd

from crawler.item import Meta


class StatsdMiddleware(object):
    def __init__(self, host, port):
        self.c = statsd.StatsClient(host, port, prefix='scrape')

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            host=crawler.settings.get('STATSD_HOST'),
            port=crawler.settings.getint('STATSD_PORT')
        )

    def process_item(self, item, spider):
        if not isinstance(item, Meta):
            return item

        market = item['meta']['market']

        apk_count = len([0 for d in item['versions'].values() if 'file_path' in d])

        self.c.incr(f"{market}.items")
        self.c.incr(f"{market}.apk", count=apk_count)
        return item
