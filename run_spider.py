import argparse
import os

import eventlet
import yaml
from scrapy.crawler import CrawlerProcess

from pystorecrawler.pipelines.util import market_from_spider
from pystorecrawler.spiders.apkmirror import ApkMirrorSpider
from pystorecrawler.spiders.apkmonk import ApkMonkSpider
from pystorecrawler.spiders.baidu import BaiduSpider
from pystorecrawler.spiders.fdroid import FDroidSpider
from pystorecrawler.spiders.gplay import GooglePlaySpider
from pystorecrawler.spiders.huawei import HuaweiSpider
from pystorecrawler.spiders.mi import MiSpider
from pystorecrawler.spiders.slideme import SlideMeSpider
from pystorecrawler.spiders.tencent import TencentSpider
from pystorecrawler.spiders.threesixty import ThreeSixtySpider

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

    ratelimit_inc = ratelimit.get("inc", 10)
    ratelimit_dec = ratelimit.get("dec", 5)
    ratelimit_base = ratelimit.get("base", 0.05)
    ratelimit_default = ratelimit.get("default", 30)

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

    log_file = os.path.join(logdir, f"{spidername}.log")

    item_pipelines = {
        'pystorecrawler.pipelines.add_universal_meta.AddUniversalMetaPipeline': 100,
        'pystorecrawler.pipelines.package_name.PackageNamePipeline': 300,
        'pystorecrawler.pipelines.write_meta_file.WriteMetaFilePipeline': 1000
    }

    if apk_enabled:
        item_pipelines['pystorecrawler.pipelines.download_apks.DownloadApksPipeline'] = 200

    if icon_enabled:
        item_pipelines['pystorecrawler.pipelines.download_icon.DownloadIconPipeline'] = 210

    downloader_middlewares = {
        'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
        'scrapy_useragents.downloadermiddlewares.useragents.UserAgentsMiddleware': 500,
        # 'pystorecrawler.middlewares.too_many_requests.IncDec429RetryMiddleware': 543,
        'pystorecrawler.middlewares.too_many_requests.Base429RetryMiddleware': 543,
    }

    user_agents = [
        ('Mozilla/5.0 (X11; Linux x86_64) '
         'AppleWebKit/537.36 (KHTML, like Gecko) '
         'Chrome/57.0.2987.110 '
         'Safari/537.36'),  # chrome
        ('Mozilla/5.0 (X11; Linux x86_64) '
         'AppleWebKit/537.36 (KHTML, like Gecko) '
         'Chrome/61.0.3163.79 '
         'Safari/537.36'),  # chrome
        ('Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) '
         'Gecko/20100101 '
         'Firefox/55.0'),  # firefox
        ('Mozilla/5.0 (X11; Linux x86_64) '
         'AppleWebKit/537.36 (KHTML, like Gecko) '
         'Chrome/61.0.3163.91 '
         'Safari/537.36'),  # chrome
        ('Mozilla/5.0 (X11; Linux x86_64) '
         'AppleWebKit/537.36 (KHTML, like Gecko) '
         'Chrome/62.0.3202.89 '
         'Chrome/62.0.3202.89 '
         'Safari/537.36'),  # chrome
        ('Mozilla/5.0 (X11; Linux x86_64) '
         'AppleWebKit/537.36 (KHTML, like Gecko) '
         'Chrome/63.0.3239.108 '
         'Safari/537.36'),  # chrome
    ]

    settings = dict(
        LOG_LEVEL=log_level,
        LOG_FILE=log_file,
        DOWNLOADER_MIDDLEWARES=downloader_middlewares,
        USER_AGENTS=user_agents,
        ITEM_PIPELINES=item_pipelines,
        CONCURRENT_REQUESTS=concurrent_requests,
        DEPTH_LIMIT=depth_limit,
        CLOSESPIDER_ITEMCOUNT=item_count,
        # AUTOTHROTTLE_ENABLED=True,
        # AUTOTHROTTLE_START_DELAY=0,
        RETRY_TIMES=2,
        RETRY_HTTP_CODES=[429], # also retry rate limited requests
        # custom settings
        CRAWL_ROOTDIR=rootdir,
        DOWNLOAD_TIMEOUT=10 * 60 * 1000,  # 10 minute timeout (in milliseconds)
        DOWNLOAD_MAXSIZE=0,
        RATELIMIT_INC_TIME=ratelimit_inc,
        RATELIMIT_DEC_TIME=ratelimit_dec,
        RATELIMIT_BASE_INC=ratelimit_base,
        RATELIMIT_DEFAULT_BACKOFF=ratelimit_default,
        PACKAGE_FILES=package_files
    )

    if resumation_enabled:
        settings['JOBDIR'] = jobdir

    return settings


def main(config, spidername, logdir):
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
    parser.add_argument("--spider", help="Spider to run", required=True)
    parser.add_argument("--logdir", help="Directory in which to store the log files", default="logs")
    args = parser.parse_args()

    with open(args.config) as f:
        cnf = yaml.load(f, Loader=yaml.FullLoader)

    main(cnf, args.spider, args.logdir)
