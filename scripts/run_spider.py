import argparse
import os

import eventlet
import sentry_sdk
import yaml
from scrapy.crawler import CrawlerProcess

import sys

sys.path.append(os.path.abspath('.'))
from crawler.pipelines.util import market_from_spider
from crawler.spiders.apkmirror import ApkMirrorSpider
from crawler.spiders.apkmonk import ApkMonkSpider
from crawler.spiders.baidu import BaiduSpider
from crawler.spiders.fdroid import FDroidSpider
from crawler.spiders.gplay import GooglePlaySpider
from crawler.spiders.huawei import HuaweiSpider
from crawler.spiders.mi import MiSpider
from crawler.spiders.slideme import SlideMeSpider
from crawler.spiders.tencent import TencentSpider
from crawler.spiders.threesixty import ThreeSixtySpider

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
    GooglePlaySpider
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


LOG_LEVELS = [
    "CRITICAL",
    "ERROR",
    "WARNING",
    "INFO",
    "DEBUG"
]


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

    scrapy = config.get("scrapy", None)
    if not scrapy:
        raise YamlException("scrapy")

    concurrent_requests = scrapy.get('concurrent_requests', 1)
    depth_limit = scrapy.get('depth_limit', 2)
    item_count = scrapy.get('item_count', 10)
    log_level = scrapy.get("log_level", "INFO")

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

    influxdb = config.get("influxdb", None)
    if not influxdb:
        raise YamlException("influxdb")

    gplay = config.get("googleplay", {})
    if not gplay:
        raise YamlException("googleplay")

    log_file = os.path.join(logdir, f"{spidername}.log")

    item_pipelines = {
        'crawler.pipelines.add_universal_meta.AddUniversalMetaPipeline': 100,
        'crawler.pipelines.package_name.PackageNamePipeline': 300,
        'crawler.pipelines.influxdb.InfluxdbMiddleware': 301,
        'crawler.pipelines.ads_txt.AdsTxtPipeline': 500,
        'crawler.pipelines.privacy_policy.PrivacyPolicyPipeline': 501,
        'crawler.pipelines.analyze_apks.AnalyzeApkPipeline': 700,
        'crawler.pipelines.write_meta_file.WriteMetaFilePipeline': 1000
    }

    if apk_enabled:
        item_pipelines['crawler.pipelines.download_apks.DownloadApksPipeline'] = 200

    if icon_enabled:
        item_pipelines['crawler.pipelines.download_icon.DownloadIconPipeline'] = 210

    downloader_middlewares = {
        'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
        'crawler.middlewares.proxy.HttpProxyMiddleware': 100,
        'crawler.middlewares.sentry.SentryMiddleware': 110,
        'scrapy_useragents.downloadermiddlewares.useragents.UserAgentsMiddleware': 500,
        'crawler.middlewares.ratelimit.RatelimitMiddleware': 543
    }

    user_agents = _load_user_agents(args.user_agents_file)
    proxies = _load_proxies(args.proxies_file)

    settings = dict(
        LOG_LEVEL=log_level,
        DOWNLOADER_MIDDLEWARES=downloader_middlewares,
        USER_AGENTS=user_agents,
        ITEM_PIPELINES=item_pipelines,
        CONCURRENT_REQUESTS=concurrent_requests,
        DEPTH_LIMIT=depth_limit,
        CLOSESPIDER_ITEMCOUNT=item_count,
        # AUTOTHROTTLE_ENABLED=True,
        # AUTOTHROTTLE_START_DELAY=0,
        RETRY_TIMES=2,
        RETRY_HTTP_CODES=[429],  # also retry rate limited requests
        MEDIA_ALLOW_REDIRECTS=True,
        HTTPPROXY_ENABLED=True,
        HTTP_PROXIES=proxies,
        # custom settings
        CRAWL_ROOTDIR=rootdir,
        DOWNLOAD_TIMEOUT=10 * 60 * 1000,  # 10 minute timeout (in milliseconds)
        DOWNLOAD_MAXSIZE=0,
        RATELIMIT_PARAMS=ratelimit,
        PACKAGE_FILES=package_files,
        STATSD_PARAMS=statsd,
        INFLUXDB_PARAMS=influxdb,
        GPLAY_PARAMS=gplay
    )

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
    process = CrawlerProcess(settings)

    spider = spider_by_name(spidername)

    process.crawl(spider)
    process.start()  # the script will block here until the crawling is finished


if __name__ == "__main__":
    eventlet.monkey_patch(socket=True)

    # parse CLI arguments
    parser = argparse.ArgumentParser(description='Android APK market crawler')
    parser.add_argument("--config", help="Path to YAML configuration file", default="config/config.template.yml")
    parser.add_argument("--logdir", help="Directory in which to store the log files", default="logs")
    parser.add_argument("--spider", help="Spider to run", required=True, default="config/spider_list.txt")
    parser.add_argument("--user_agents_file", help="Path to file of user agents", default="config/user_agents.txt")
    parser.add_argument("--proxies_file", help="Path to file of proxy addresses", default="config/proxies.txt")
    args = parser.parse_args()

    with open(args.config) as f:
        cnf = yaml.load(f, Loader=yaml.FullLoader)

    main(cnf, args.spider, args.logdir)
