from scrapy import signals
from twisted.internet import task

from crawler.item import Result
from crawler.util import market_from_spider


class InfluxdbPipeline:
    def __init__(self, influxdb_client):
        self.influxdb_client = influxdb_client
        self.tasks = []

    @classmethod
    def from_crawler(cls, crawler):
        o = cls(crawler.settings.get("INFLUXDB_CLIENT"))

        crawler.signals.connect(o.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(o.spider_closed, signal=signals.spider_closed)

        return o

    def spider_opened(self, spider):
        tasks = []
        t = task.LoopingCall(self.influxdb_client.send, spider)  # send to influxdb every 5 secs
        t.start(5, now=False)
        tasks.append(t)

        t = task.LoopingCall(self.write_active_downloads, spider)
        t.start(0.5, now=False)  # probe active download ever 500ms

        tasks.append(t)

        self.tasks = tasks

    def spider_closed(self, spider, reason):
        for t in self.tasks:
            if t.running:
                t.stop()
        self.influxdb_client.close()

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

    def write_active_downloads(self, spider):
        market = market_from_spider(spider)
        point = {
            "measurement": "items",
            "tags": {
                "market": market
            },
            "fields": {
                "count": 1,
                "active_downloads": len(spider.crawler.engine.downloader.active)
            }
        }
        self.influxdb_client.add_point(point)
