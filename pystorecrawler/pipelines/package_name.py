import os

from pystorecrawler.item import PackageName


class PackageNamePipeline:
    def __init__(self, outfile):
        self.outfile = outfile
        self.f = None
        self.seen = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            outfile=crawler.settings.get('PKG_NAME_OUTFILE')
        )

    def open_spider(self, spider):
        # fill set of seen packages
        self.seen = set()
        if os.path.exists(self.outfile):
            with open(self.outfile, 'r') as f:
                for l in f.readlines():
                    self.seen.add(l.strip())

        # open file for further appending
        self.f = open(self.outfile, 'a+')

    def process_item(self, item, spider):
        if not isinstance(item, PackageName):
            return item

        pkg_name = item['name']
        if not pkg_name in self.seen:
            self.f.write(f"{pkg_name }\n")
            self.seen.add(pkg_name)

        return item

    def close_spider(self, spider):
        self.f.close()
