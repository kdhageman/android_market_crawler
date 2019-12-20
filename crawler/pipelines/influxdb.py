from influxdb import InfluxDBClient

from crawler.item import Meta, PackageName
from crawler.util import market_from_spider


class InfluxdbMiddleware(object):
    def __init__(self, params):
        self.c = InfluxDBClient(**params)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(params=crawler.settings.get("INFLUXDB_PARAMS"))

    def process_item(self, item, spider):
        market = market_from_spider(spider)
        if isinstance(item, Meta):
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

        elif isinstance(item, PackageName):
            market = market_from_spider(spider)

            points = [{
                "measurement": "items",
                "tags": {
                    "market": market
                },
                "fields": {
                    "package_names": 1,
                }
            }]
            self.c.write_points(points)

        return item
