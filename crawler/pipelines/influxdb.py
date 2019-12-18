import statsd
from influxdb import InfluxDBClient

from crawler.item import Meta


class InfluxdbMiddleware(object):
    def __init__(self, host, port, username, password, database, ssl):
        self.c = InfluxDBClient(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            ssl=ssl
        )
        self.counters = {
            "count": 0,
            "apks": 0,
            "apk_sizes": 0,
            "versions": 0
        }

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            host=crawler.settings.get('INFLUXDB_HOST'),
            port=crawler.settings.getint('INFLUXDB_PORT'),
            username=crawler.settings.get('INFLUXDB_USER'),
            password=crawler.settings.get('INFLUXDB_PASSWORD'),
            database=crawler.settings.get('INFLUXDB_DATABASE'),
            ssl=crawler.settings.get('INFLUXDB_SSL')
        )

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
