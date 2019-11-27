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


def main(cnf):
    item_pipelines = {
        'pystorecrawler.pipelines.add_universal_meta.AddUniversalMetaPipeline': 100,
        'pystorecrawler.pipelines.download_apks.DownloadApksPipeline': 200,
        'pystorecrawler.pipelines.package_name.PackageNamePipeline': 300,
        'pystorecrawler.pipelines.write_meta_file.WriteMetaFilePipeline': 1000
    }

    outdir = cnf.get('outdir', "/tmp/crawl")
    pkg_outfile = cnf.get('pkg_outfile', "./packages.csv")

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
        CLOSESPIDER_ITEMCOUNT=1,
        # custom settings
        APK_OUTDIR=outdir,
        APK_DOWNLOAD_TIMEOUT=5 * 60 * 1000,  # 5 minute timeout (in milliseconds)
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
    eventlet.monkey_patch(socket=True)

    # parse CLI arguments
    parser = argparse.ArgumentParser(description='Android APK market crawler')
    parser.add_argument("--config", default="config/config.template.yml", help="Path to YAML configuration file")
    args = parser.parse_args()

    with open(args.config) as f:
        cnf = yaml.load(f, Loader=yaml.FullLoader)

    main(cnf)
