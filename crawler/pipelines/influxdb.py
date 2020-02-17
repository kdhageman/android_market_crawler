from scrapy import signals
from twisted.internet import task

from crawler.item import Result
from crawler.util import market_from_spider


class InfluxdbPipeline:
    def __init__(self, influxdb_client):
        self.influxdb_client = influxdb_client
        self.task = None

    @classmethod
    def from_crawler(cls, crawler):
        o = cls(crawler.settings.get("INFLUXDB_CLIENT"))

        crawler.signals.connect(o.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(o.spider_closed, signal=signals.spider_closed)

        return o

    def spider_opened(self, spider):
        self.task = task.LoopingCall(self.influxdb_client._send, spider)
        self.task.start(5, now=False)  # send to influxdb every 30 secs

    def spider_closed(self, spider, reason):
        if self.task and self.task.running:
            self.task.stop()

    def process_item(self, item, spider):
        market = market_from_spider(spider)
        if isinstance(item, Result):
            apk_count = len([0 for d in item['versions'].values() if 'file_path' in d])
            apk_sizes = sum([d.get('file_size', 0) for d in item['versions'].values()])
            version_count = len(item['versions'])

            point = {
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
            }
            self.influxdb_client.add_point(point)

        return item
