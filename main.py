import os

from scrapy.crawler import CrawlerProcess

from spider.apkmonk import ApkMonkSpider
from spider.fdroid import FDroidSpider
from spider.huawei import HuaweiSpider
from spider.mi import MiSpider
from spider.slideme import SlideMeSpider
from spider.tencent import TencentSpider
from spider.threesixty import ThreeSixtySpider


def main():
    item_pipelines = {
        # 'spider.pipeline.DownloadApksPipeline': 100
    }

    feed_uri = f"file://{os.path.join(os.getcwd(), 'meta.csv')}"

    process = CrawlerProcess({
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36',
        'CONCURRENT_REQUESTS': 5,
        'ITEM_PIPELINES': item_pipelines,
        'DEPTH_LIMIT': 1,
        'FEED_URI': feed_uri,
        'FEED_EXPORT_FIELDS': ["meta"],
        'CLOSESPIDER_ITEMCOUNT': 2
    })

    process.crawl(ThreeSixtySpider)
    process.start()  # the script will block here until the crawling is finished


if __name__ == "__main__":
    main()
