from scrapy.crawler import CrawlerProcess

from spider.fdroid import FDroidSpider


def main():
    item_pipelines = {
        'spider.pipeline.DownloadApksPipeline': 100
    }

    process = CrawlerProcess({
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36',
        'CONCURRENT_REQUESTS': 1,
        'ITEM_PIPELINES': item_pipelines,
        'DEPTH_LIMIT': 2,
        'FEED_URI': 'file:///meta.csv',
        'FEED_EXPORT_FIELDS': ["meta"],
    })

    process.crawl(FDroidSpider)
    process.start()  # the script will block here until the crawling is finished


if __name__ == "__main__":
    main()
