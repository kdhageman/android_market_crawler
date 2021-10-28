from scrapy.exceptions import NotConfigured
from twisted.internet import task
from crawler.util import market_from_spider
import logging
import pprint

from twisted.internet.task import LoopingCall
from scrapy import signals

logger = logging.getLogger(__name__)


class InfluxdbLogs(object):
    def __init__(self, crawler, influxdbclient, interval=60.0):
        self.crawler = crawler
        self.influxdb_client = influxdbclient
        self.interval = interval
        self.task = None

    @classmethod
    def from_crawler(cls, crawler):
        interval = crawler.settings.getfloat('LOGSTATS_INTERVAL')
        if not interval:
            raise NotConfigured
        influxdb_client = crawler.settings.get("INFLUXDB_CLIENT")
        o = cls(crawler, influxdb_client, interval)

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

        # heartbeat
        point = {
            "measurement": "heartbeat",
            "tags": {
                "market": market,
            },
            "fields": {
                "count": 1
            }
        }
        points.append(point)

        self.influxdb_client.add_points(points)
        self.crawler.stats.set_value("response_codes", {})

    def spider_closed(self, spider, reason):
        if self.task and self.task.running:
            self.task.stop()


class _LoopingExtension:
    def setup_looping_task(self, task, crawler, interval):
        self._interval = interval
        self._task = LoopingCall(task)
        crawler.signals.connect(self.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(self.spider_closed, signal=signals.spider_closed)

    def spider_opened(self):
        self._task.start(self._interval, now=False)

    def spider_closed(self):
        if self._task.running:
            self._task.stop()


class MonitorDownloadsExtension(_LoopingExtension):
    """
    Enable this extension to periodically log a number of active downloads.
    """
    def __init__(self, crawler, interval):
        self.crawler = crawler
        self.setup_looping_task(self.monitor, crawler, interval)

    @classmethod
    def from_crawler(cls, crawler):
        # fixme: 0 should mean NotConfigured
        interval = crawler.settings.getfloat("MONITOR_DOWNLOADS_INTERVAL", 10.0)
        return cls(crawler, interval)

    def monitor(self):
        active_downloads = len(self.crawler.engine.downloader.active)
        logger.info("Active downloads: {}".format(active_downloads))


class DumpStatsExtension(_LoopingExtension):
    """
    Enable this extension to log Scrapy stats periodically, not only
    at the end of the crawl.
    """
    def __init__(self, crawler, interval):
        self.stats = crawler.stats
        self.setup_looping_task(self.print_stats, crawler, interval)

    def print_stats(self):
        stats = self.stats.get_stats()
        logger.info("Scrapy stats:\n" + pprint.pformat(stats))

    @classmethod
    def from_crawler(cls, crawler):
        interval = crawler.settings.getfloat("DUMP_STATS_INTERVAL", 60.0)
        # fixme: 0 should mean NotConfigured
        return cls(crawler, interval)
