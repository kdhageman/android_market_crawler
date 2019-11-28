import os

from pystorecrawler.item import PackageName
from pystorecrawler.pipelines.util import market_from_spider


class PackageNamePipeline:
    def __init__(self, outdir):
        self.outdir = outdir
        self.f = None
        self.seen = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            outdir=crawler.settings.get('CRAWL_ROOTDIR')
        )

    def open_spider(self, spider):
        market = market_from_spider(spider)
        fname = f"{market}-packages.csv"
        fpath = os.path.join(self.outdir, fname)

        # fill set of seen packages
        self.seen = set()
        if os.path.exists(fpath):
            with open(fpath, 'r') as f:
                for l in f.readlines():
                    self.seen.add(l.strip())

        # open file for further appending
        self.f = open(fpath, 'a+')

    def process_item(self, item, spider):
        """
        Write the package name to the output file, in case it has not been seen before
        """
        if not isinstance(item, PackageName):
            return item

        pkg_name = item['name']
        if not pkg_name in self.seen:
            self.f.write(f"{pkg_name }\n")
            self.seen.add(pkg_name)

        return item

    def close_spider(self, spider):
        self.f.close()
