import argparse
import os

import eventlet
import yaml
from scrapy.crawler import CrawlerProcess
from pystorecrawler.spider.apkmirror import ApkMirrorSpider
from pystorecrawler.spider.apkmonk import ApkMonkSpider
from pystorecrawler.spider.baidu import BaiduSpider
from pystorecrawler.spider.fdroid import FDroidSpider
from pystorecrawler.spider.gplay import GooglePlaySpider
from pystorecrawler.spider.huawei import HuaweiSpider
from pystorecrawler.spider.mi import MiSpider
from pystorecrawler.spider.slideme import SlideMeSpider
from pystorecrawler.spider.tencent import TencentSpider
from pystorecrawler.spider.threesixty import ThreeSixtySpider

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

def as_bool(val):
    """
    Returns if string is boolean true or not

    Args:
        val: str

    Returns: bool
    """
    return val in ["1", "true", "True"]

def get_settings(config):
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
    pkg_outfile = output.get("pkg_outfile", "./packages.csv")

    scrapy = config.get("scrapy", None)
    if not scrapy:
        raise YamlException("scrapy")

    concurrent_requests = scrapy.get('concurrent_requests', 1)
    depth_limit = scrapy.get('depth_limit', 2)
    item_count = scrapy.get('item_count', 10)
    log_level = scrapy.get("log_level", "INFO")

    resumation = scrapy.get("resumation", None)
    if not resumation:
        raise YamlException("scrapy/resumation")

    resumation_enabled = as_bool(resumation.get("enabled", "true"))
    jobdir = resumation.get("jobdir", "./jobdir")

    downloads = config.get("downloads", None)
    if not downloads:
        raise YamlException("downloads")

    apk_enabled = as_bool(downloads.get("apk", "true"))
    icon_enabled = as_bool(downloads.get("icon", "true"))

    item_pipelines = {
        'pystorecrawler.pipelines.add_universal_meta.AddUniversalMetaPipeline': 100,
        'pystorecrawler.pipelines.package_name.PackageNamePipeline': 300,
        'pystorecrawler.pipelines.write_meta_file.WriteMetaFilePipeline': 1000
    }

    if apk_enabled:
        item_pipelines['pystorecrawler.pipelines.download_apks.DownloadApksPipeline'] = 200

    if icon_enabled:
        # TODO implement DownloadIconPipeline
        pass

    downloader_middlewares = {
        'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        'scrapy_useragents.downloadermiddlewares.useragents.UserAgentsMiddleware': 500,
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
        DOWNLOADER_MIDDLEWARES=downloader_middlewares,
        USER_AGENTS=user_agents,
        ITEM_PIPELINES=item_pipelines,
        CONCURRENT_REQUESTS=concurrent_requests,
        DEPTH_LIMIT=depth_limit,
        CLOSESPIDER_ITEMCOUNT=item_count,
        AUTOTHROTTLE_ENABLED=True,
        AUTOTHROTTLE_START_DELAY=1,
        # custom settings
        APK_OUTDIR=rootdir,
        APK_DOWNLOAD_TIMEOUT=5 * 60 * 1000,  # 5 minute timeout (in milliseconds)
        PKG_NAME_OUTFILE=pkg_outfile
    )

    if resumation_enabled:
        settings['JOBDIR'] = jobdir

    return settings


def main(config):
    settings = get_settings(config)
    process = CrawlerProcess(settings)

    spiders = [
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

    for spider in spiders:
        process.crawl(spider)
    process.start()  # the script will block here until the crawling is finished


if __name__ == "__main__":
    eventlet.monkey_patch(socket=True)

    # parse CLI arguments
    parser = argparse.ArgumentParser(description='Android APK market crawler')
    parser.add_argument("--config", default="config/config.template.yml", help="Path to YAML configuration file")
    args = parser.parse_args()

    with open(args.config) as f:
        cnf = yaml.load(f, Loader=yaml.FullLoader)

    main(cnf)
