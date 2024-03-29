import argparse
import logging
import os
import re
import sys
import time
from multiprocessing import Process

import sentry_sdk
import yaml
from scrapy.crawler import CrawlerProcess

sys.path.append(os.path.abspath('.'))
from crawler.pipelines.util import InfluxDBClient
from crawler.util import market_from_spider
from crawler.spiders.apkmirror import ApkMirrorSpider
from crawler.spiders.apkmonk import ApkMonkSpider
from crawler.spiders.baidu import BaiduSpider
from crawler.spiders.fdroid import FDroidSpider
from crawler.spiders.gplay import GooglePlaySpider, AuthRenewServer
from crawler.spiders.huawei import HuaweiSpider
from crawler.spiders.mi import MiSpider
from crawler.spiders.slideme import SlideMeSpider
from crawler.spiders.tencent import TencentSpider
from crawler.spiders.threesixty import ThreeSixtySpider
from crawler.spiders.nine_game import NineGameSpider
from scripts.util import merge

ALL_SPIDERS = [
    ApkMirrorSpider,
    ApkMonkSpider,
    BaiduSpider,
    FDroidSpider,
    HuaweiSpider,
    MiSpider,
    SlideMeSpider,
    TencentSpider,
    ThreeSixtySpider,
    GooglePlaySpider,
    NineGameSpider
]


def _load_user_agents(path):
    try:
        with open(path, "r") as f:
            return [l.strip() for l in f.readlines()]
    except:
        return [
            "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; FSL 7.0.6.01001)"
        ]


def _load_proxies(path):
    try:
        with open(path, "r") as f:
            return [l.strip() for l in f.readlines()]
    except:
        return []


def spider_by_name(name):
    """
    Returns an instance of a spider for the given name
    Args:
        name: str

    Returns:
        scrapy.Spider
    """
    spider = None
    for s in ALL_SPIDERS:
        if market_from_spider(s) == name:
            spider = s
            break
    if not spider:
        raise Exception("Unknown spider")
    return spider


class YamlException(Exception):
    def __init__(self, required_field):
        msg = f"Invalid YAML file: missing '{required_field}'"
        super().__init__(msg)


def get_settings(config, spidername, logdir):
    """
    Return a dictionary used as settings for Scrapy crawling
    Args:
        config: dict
            Configuration dictionary read from YAML file

    Returns: dict
        Scrapy settings
    """
    output = config.get("output", None)
    if not output:
        raise YamlException("output")

    rootdir = output.get("rootdir", "/tmp/crawl")

    input = config.get("input", None)
    if not input:
        raise YamlException("input")

    package_files = input.get("package_files", [])
    retrieve_package_files = input.get("from_package_files", False)
    retrieve_base_requests = input.get("from_base_requests", False)
    retrieve_from_db = input.get("from_db", False)

    scrapy = config.get("scrapy", None)
    if not scrapy:
        raise YamlException("scrapy")

    concurrent_requests = scrapy.get('concurrent_requests', 1)
    concurrent_requests_per_domain = scrapy.get('concurrent_requests_per_domain', 1)
    depth_limit = scrapy.get('depth_limit', 2)
    item_count = scrapy.get('item_count', 10)
    log_level = scrapy.get("log_level", "INFO")
    pause_interval = scrapy.get("pause_interval")
    telnet = scrapy.get("telnet", {})
    telnet_user = telnet.get("username", None)
    telnet_password = telnet.get("password", None)
    recursive = scrapy.get("recursive", False)

    ratelimit = scrapy.get("ratelimit", None)
    if not ratelimit:
        raise YamlException("scrapy/ratelimit")

    resumation = scrapy.get("resumation", None)
    if not resumation:
        raise YamlException("scrapy/resumation")

    resumation_enabled = resumation.get("enabled", True)
    jobdir = resumation.get("jobdir", "./jobdir")
    jobdir = os.path.join(jobdir, spidername)

    downloads = config.get("downloads", None)
    if not downloads:
        raise YamlException("downloads")

    apk_enabled = downloads.get("apk", True)
    icon_enabled = downloads.get("icon", True)

    statsd = config.get("statsd", {})

    influxdb = config.get("influxdb", {})
    influxdb_client = InfluxDBClient(influxdb)

    gplay = config.get("googleplay", {})
    if not gplay:
        raise YamlException("googleplay")

    apkmirror = config.get("apkmirror", {})

    database = config.get("database", {})
    if not database:
        raise YamlException("database")

    log_file = os.path.join(logdir, f"{spidername}.log")

    splash = scrapy.get("splash", {})
    splash_enabled = splash.get("enabled", False)
    splash_url = splash.get("url", None)

    item_pipelines = {
        'crawler.pipelines.add_universal_meta.AddUniversalMetaPipeline': 100,
        'crawler.pipelines.database.PreDownloadVersionPipeline': 111,
        'crawler.pipelines.download_apks.DownloadApksPipeline': 200 if apk_enabled else None,
        'crawler.pipelines.download_icon.DownloadIconPipeline': 210 if icon_enabled else None,
        'crawler.pipelines.influxdb.InfluxdbPipeline': 300,
        'crawler.pipelines.ads.AdsPipeline': 500,
        'crawler.pipelines.privacy_policy.PrivacyPolicyPipeline': 501,
        'crawler.pipelines.analyze_apks.AnalyzeApkPipeline': 700,
        'crawler.pipelines.assetlinks.AssetLinksPipeline': 800,
        'crawler.pipelines.database.PostDownloadPipeline': 900,
        'crawler.pipelines.database.PostDownloadPackagePipeline': 901,
        # 'crawler.pipelines.output_meta.WriteMetaFilePipeline': 1000,
        'crawler.pipelines.log.LogPipeline': 1100
    }

    downloader_middlewares = {
        'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
        'crawler.middlewares.sentry.SentryMiddleware': 1,
        'crawler.middlewares.status_code.StatuscodeMiddleware': 2,
        'crawler.middlewares.proxy.HttpProxyMiddleware': 100,
        'crawler.middlewares.stats.StatsMiddleware': 120,
        'crawler.middlewares.duration.DurationMiddleware': 200,
        'scrapy_useragents.downloadermiddlewares.useragents.UserAgentsMiddleware': 500,
        'crawler.middlewares.ratelimit.RatelimitMiddleware': 543,
    }
    if splash_enabled:
        downloader_middlewares['scrapy_splash.SplashCookiesMiddleware'] = 723
        downloader_middlewares['scrapyjs.SplashMiddleware'] = 725
        downloader_middlewares['scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware'] = 810


    spider_middlewares = {
        'crawler.middlewares.sentry.SentryMiddleware': 1,
        'scrapy.spidermiddlewares.httperror.HttpErrorMiddleware': 3,
        'scrapy_splash.SplashDeduplicateArgsMiddleware': 100
    }

    extensions = {
        'crawler.extensions.stats.InfluxdbLogs': 100,
        'crawler.extensions.stats.DumpStatsExtension': 101,
        'crawler.extensions.stats.MonitorDownloadsExtension': 102
    }

    user_agents = _load_user_agents(args.user_agents_file)
    proxies = _load_proxies(args.proxies_file)

    settings = dict(
        LOG_LEVEL=log_level,
        LOGSTATS_INTERVAL=5.0,
        DOWNLOADER_MIDDLEWARES=downloader_middlewares,
        SPIDER_MIDDLEWARES=spider_middlewares,
        EXTENSIONS=extensions,
        USER_AGENTS=user_agents,
        ITEM_PIPELINES=item_pipelines,
        CONCURRENT_REQUESTS=concurrent_requests,
        CONCURRENT_REQUESTS_PER_DOMAIN=concurrent_requests_per_domain,
        DEPTH_LIMIT=depth_limit,
        CLOSESPIDER_ITEMCOUNT=item_count,
        # AUTOTHROTTLE_ENABLED=True,
        # AUTOTHROTTLE_START_DELAY=0,
        RETRY_TIMES=0,
        RETRY_HTTP_CODES=[429],  # also retry rate limited requests
        MEDIA_ALLOW_REDIRECTS=True,
        HTTP_PROXIES=proxies,
        DOWNLOAD_WARNSIZE=0,
        DNSCACHE_SIZE=100000,
        TELNETCONSOLE_USERNAME="scrapy",
        TELNETCONSOLE_PASSWORD="scrapy",
        # DUPEFILTER_DEBUG=True,
        PAUSE_INTERVAL=pause_interval,
        RETRY_ENABLED=False,
        COOKIES_ENABLED=True,
        SPLASH_URL=splash_url,
        # custom settings
        CRAWL_ROOTDIR=rootdir,
        DOWNLOAD_TIMEOUT=120,
        DOWNLOAD_MAXSIZE=0,
        RATELIMIT_PARAMS=ratelimit,
        RETRIEVE_PACKAGE_FILES=retrieve_package_files,
        RETRIEVE_BASE_REQUESTS=retrieve_base_requests,
        RETRIEVE_FROM_DB=retrieve_from_db,
        PACKAGE_FILES=package_files,
        STATSD_PARAMS=statsd,
        INFLUXDB_CLIENT=influxdb_client,
        GPLAY_PARAMS=gplay,
        APKMIRROR_PARAMS=apkmirror,
        DATABASE_PARAMS=database,
        RECURSIVE=recursive,
        APK_ENABLED=apk_enabled,
    )
    if splash_enabled:
        settings['DUPEFILTER_CLASS'] = 'scrapyjs.SplashAwareDupeFilter'
        settings['HTTPCACHE_STORAGE'] = 'scrapy_splash.SplashAwareFSCacheStorage'

    proxies = _load_proxies(args.proxies_file)

    if telnet_user:
        settings['TELNETCONSOLE_USERNAME'] = telnet_user

    if telnet_password:
        settings['TELNETCONSOLE_PASSWORD'] = telnet_password

    if scrapy.get("log_to_file", True):
        settings['LOG_FILE'] = log_file

    if resumation_enabled:
        settings['JOBDIR'] = jobdir

    return settings


def main(config, spidername, logdir):
    dsn = config.get("sentry", {}).get("dsn", "")
    if dsn:
        sentry_sdk.init(dsn)

    settings = get_settings(config, spidername, logdir)

    spider = spider_by_name(spidername)

    if spider == GooglePlaySpider:
        server = AuthRenewServer()
        server_process = Process(target=server.start)
        server_process.start()

        # wait for HTTP server to start
        time.sleep(3)

        settings['GPLAY_PARAMS']['server_port'] = server.port

    process = CrawlerProcess(settings)
    process.crawl(spider)
    process.start()  # the script will block here until the crawling is finished

    if spider == GooglePlaySpider:
        server_process.terminate()
        server_process.join(timeout=0.1)


class ItemMessageFilter(logging.Filter):
    def filter(self, record):
        # The message that logs the item actually has raw % operators in it,
        # which Scrapy presumably formats later on
        match = re.search(r'(Scraped from %\(src\)s)\n%\(item\)s', record.msg)
        if match:
            # Make the message everything but the item itself
            record.msg = match.group(1)
        # Don't actually want to filter out this record, so always return 1
        return 1


if __name__ == "__main__":
    for namespace, level in [
        ("androguard", logging.ERROR),
        ("scrapy.core.downloader.handlers.http11", logging.ERROR),
        ("scrapy.spidermiddlewares.httperror", logging.WARNING),
        ("urllib3.connectionpool", logging.INFO),
        ("scrapy.downloadermiddlewares.redirect", logging.INFO),
        ("scrapy.downloadermiddlewares.retry", logging.FATAL),
    ]:
        logger = logging.getLogger(namespace)
        logger.setLevel(level)

    logging.getLogger('scrapy.core.scraper').addFilter(ItemMessageFilter())

    # parse CLI arguments
    parser = argparse.ArgumentParser(description='Android APK market crawler')
    parser.add_argument("--configs", help="Path to YAML configuration files", nargs="+",
                        default="config/config.template.yml")
    parser.add_argument("--logdir", help="Directory in which to store the log files", default="logs")
    parser.add_argument("--spider", help="Spider to run", required=True, default="config/spider_list.txt")
    parser.add_argument("--user_agents_file", help="Path to file of user agents", default="config/user_agents.txt")
    parser.add_argument("--proxies_file", help="Path to file of proxy addresses", default="config/proxies.txt")
    args = parser.parse_args()

    cnf = {}
    for cnf_file in args.configs:
        try:
            with open(cnf_file) as f:
                cnf = merge(cnf, yaml.load(f, Loader=yaml.FullLoader))
        except Exception as e:
            pass
    main(cnf, args.spider, args.logdir)
