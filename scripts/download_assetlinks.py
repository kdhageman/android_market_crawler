import argparse
import json

import scrapy
from scrapy.crawler import CrawlerProcess


class Pipeline:
    def __init__(self, outfile):
        self.outfile = outfile
        self.f = None
        self.seen = set()

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            outfile=crawler.settings.get('OUTPUT_FILE')
        )

    def open_spider(self, spider):
        self.f = open(self.outfile, "w")

    def close_spider(self, spider):
        self.f.close()

    def process_item(self, item, spider):
        domain = item.get("domain")
        if domain and domain not in self.seen:
            self.f.write(json.dumps(item) + "\n")
            self.seen.add(domain)


class Spider(scrapy.Spider):
    def __init__(self, infile):
        self.infile = infile
        self.seen = set()

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            infile=crawler.settings.get("INPUT_FILE")
        )

    def start_requests(self):
        with open(self.infile, "r") as f:
            for l in f.readlines():
                parsed = json.loads(l)
                assetlink_domains = parsed.get('assetlink_domains', [])
                for domain in assetlink_domains:
                    url = f"https://{domain}/.well-known/assetlinks.json"
                    yield scrapy.Request(url, callback=self.parse, meta={"domain": domain})

    def parse(self, response):
        if response.status != 200:
            return

        domain = response.meta.get("domain")
        res = dict(
            domain=domain,
            statements={}
        )

        statements = json.loads(response.body.decode('utf-8'))
        for statement in statements:
            target = statement.get('target', {})
            if target.get("namespace", "") == "android_app":
                pkg_name = target.get("package_name", "")
                fps = target.get("sha256_cert_fingerprints", "")
                fps = [fp.lower().replace(":", "") for fp in fps]
                res['statements'][pkg_name] = fps
        return res


def get_settings(args):
    return dict(
        CONCURRENT_REQUESTS=5,
        INPUT_FILE=args.infile,
        OUTPUT_FILE=args.outfile,
        ITEM_PIPELINES={
            'scripts.download_assetlinks.Pipeline': 300,
        }
    )


def main(args):
    settings = get_settings(args)
    process = CrawlerProcess(settings)
    process.crawl(Spider)
    process.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Downloads the asset-links.json for the output file of "analyze_apks.py"')
    parser.add_argument("--infile", help="path of input file", default="apks.json")
    parser.add_argument("--outfile", help="path of output file", default="assetlinks.json")
    args = parser.parse_args()

    main(args)
