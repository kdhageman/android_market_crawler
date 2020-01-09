from crawler.item import Result
from crawler.pipelines.util import InfluxDBClient
from crawler.util import market_from_spider


class InfluxdbMiddleware(object):
    def __init__(self, params):
        self.c = InfluxDBClient(params)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.get("INFLUXDB_PARAMS"))

    def process_item(self, item, spider):
        market = market_from_spider(spider)
        if isinstance(item, Result):
            apk_count = len([0 for d in item['versions'].values() if 'file_path' in d])
            apk_sizes = sum([d.get('file_size', 0) for d in item['versions'].values()])
            version_count = len(item['versions'])

            points = [{
                "measurement": "items",
                "tags": {
                    "market": market
                },
                "fields": {
                    "count": 1,
                    "apks": apk_count,
                    "apk_sizes": apk_sizes,
                    "versions": version_count
                }
            }]
            self.c.write_points(points)

        return item
