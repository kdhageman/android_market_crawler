import argparse
import os

import yaml
from scrapy.crawler import CrawlerProcess

from spider.apkmonk import ApkMonkSpider
from spider.apkmirror import ApkMirrorSpider
from spider.baidu import BaiduSpider
from spider.fdroid import FDroidSpider
from spider.gplay import GooglePlaySpider
from spider.huawei import HuaweiSpider
from spider.mi import MiSpider
from spider.slideme import SlideMeSpider
from spider.tencent import TencentSpider
from spider.threesixty import ThreeSixtySpider


def main():
    # parse CLI arguments
    parser = argparse.ArgumentParser(description='Android APK market crawler')
    parser.add_argument("--config", default="config/config.template.yml", help="Path to YAML configuration file")
    args = parser.parse_args()

    with open(args.config) as f:
        conf = yaml.load(f, Loader=yaml.FullLoader)

    item_pipelines = {
        'spider.pipeline.AddMetaPipeline': 100,
        'spider.pipeline.DownloadApksPipeline': 200,
        'spider.pipeline.PackageNamePipeline': 300
    }

    feed_uri = f"file://{os.path.join(os.getcwd(), conf.get('meta_outfile', 'meta.csv'))}"
    outdir = conf.get('outdir', "/tmp/crawl")
    pkg_outfile = conf.get('pkg_outfile', "./packages.csv")

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
         'Safari/537.36'),  # chrome
        ('Mozilla/5.0 (X11; Linux x86_64) '
         'AppleWebKit/537.36 (KHTML, like Gecko) '
         'Chrome/63.0.3239.108 '
         'Safari/537.36'),  # chrome
    ]

    process = CrawlerProcess(dict(
        DOWNLOADER_MIDDLEWARES=downloader_middlewares,
        USER_AGENTS=user_agents,
        CONCURRENT_REQUESTS=1,
        ITEM_PIPELINES=item_pipelines,
        DEPTH_LIMIT=2,
        FEED_URI=feed_uri,
        FEED_EXPORT_FIELDS=["meta"],
        CLOSESPIDER_ITEMCOUNT=2,
        # custom settings
        APK_OUTDIR=outdir,
        PKG_NAME_OUTFILE=pkg_outfile
    ))

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
    main()
