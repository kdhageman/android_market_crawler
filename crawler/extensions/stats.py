from scrapy import signals
from scrapy.exceptions import NotConfigured
from twisted.internet import task

from crawler.util import market_from_spider, InfluxDBClient


class InfluxdbLogs(object):
    def __init__(self, crawler, influxdbclient, interval=60.0):
        self.crawler = crawler
        self.c = influxdbclient
        self.interval = interval
        self.task = None

    @classmethod
    def from_crawler(cls, crawler):
        interval = crawler.settings.getfloat('LOGSTATS_INTERVAL')
        if not interval:
            raise NotConfigured
        c = InfluxDBClient(crawler.settings.get("INFLUXDB_PARAMS"))
        o = cls(crawler, c, interval)

        crawler.signals.connect(o.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(o.spider_closed, signal=signals.spider_closed)
        return o

    def spider_opened(self, spider):
        self.task = task.LoopingCall(self.log, spider)
        self.task.start(self.interval)

    def log(self, spider):
        resp_codes = self.crawler.stats.get_value("response_codes")
        if not resp_codes:
            return
        market = market_from_spider(spider)
        points = []
        for resp_code, count in resp_codes.items():
            point = {
                "measurement": "response_codes",
                "tags": {
                    "market": market,
                    "response_code": resp_code
                },
                "fields": {
                    "count": count
                }
            }
            points.append(point)
        self.c.write_points(points)
        self.crawler.stats.set_value("response_codes", {})

    def spider_closed(self, spider, reason):
        if self.task and self.task.running:
            self.task.stop()
