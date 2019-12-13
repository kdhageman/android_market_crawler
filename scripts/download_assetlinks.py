import argparse
import json

import scrapy
from scrapy.crawler import CrawlerProcess


class Spider(scrapy.Spider):
    def __init__(self, infile, outfile):
        self.infile = infile
        self.f = open(outfile, "w")
        self.seen = set()

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            infile=crawler.settings.get("INPUT_FILE"),
            outfile=crawler.settings.get('OUTPUT_FILE')
        )

    def closed(self):
        self.f.close()

    def start_requests(self):
        with open(self.infile, "r") as f:
            for l in f.readlines():
                parsed = json.loads(l)
                assetlink_domains = parsed.get('assetlink_domains', [])
                for domain in assetlink_domains:
                    if domain not in self.seen:
                        self.seen.add(domain)
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

        self.f.write(json.dumps(res) + "\n")


def get_settings(args):
    return dict(
        CONCURRENT_REQUESTS=5,
        INPUT_FILE=args.infile,
        OUTPUT_FILE=args.outfile,
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
