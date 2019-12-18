import statsd
from influxdb import InfluxDBClient

from crawler.item import Meta


class InfluxdbMiddleware(object):
    def __init__(self, params):
        self.c = InfluxDBClient(**params)
        self.counters = {
            "count": 0,
            "apks": 0,
            "apk_sizes": 0,
            "versions": 0
        }

    @classmethod
    def from_crawler(cls, crawler):
        return cls(params=crawler.settings.get("INFLUXDB_PARAMS"))

    def process_item(self, item, spider):
        if not isinstance(item, Meta):
            return item

        market = item['meta']['market']
        apk_count = len([0 for d in item['versions'].values() if 'file_path' in d])
        apk_sizes = sum([d.get('file_size', 0) for d in item['versions'].values()])
        version_count = len(item['versions'])

        self.counters['count'] += 1
        self.counters['apks'] += apk_count
        self.counters['apk_sizes'] += apk_sizes
        self.counters['versions'] += version_count

        points = [
            {
                "measurement": "items",
                "tags": {
                    "market": market
                },
                "fields": {
                    "count": self.counters['count'],
                    "apks": self.counters['apks'],
                    "apk_sizes": self.counters['apk_sizes'],
                    "versions": self.counters['versions']
                }
            },
        ]

        self.c.write_points(points)

        return item
