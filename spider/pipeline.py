import os
import re
import time

import requests

from spider.item import PackageName, Meta


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


class AddMetaPipeline:
    def process_item(self, item, spider):
        """
        Adds a timestamp/market name to the meta data in the item
        """
        if not isinstance(item, Meta):
            return item

        res = item
        res['meta']['timestamp'] = int(time.time())
        market = market_from_spider(spider)
        res['meta']['market'] = market

        return res


class DownloadApksPipeline:
    """
    Retrieves APKs from a set of URLs
    """

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            outdir=crawler.settings.get('APK_OUTDIR')
        )

    def __init__(self, outdir):
        self.outdir = outdir

    def process_item(self, item, spider):
        """
        Downloads APKs and stores them on disk, according to the following file structure:
        {outdir}/{market}/{pkg_name}/{version}.apk

        Args:
            item: dict of download URLs and store meta data
            spider: spider that crawled the market
        """
        if not isinstance(item, Meta):
            return item

        meta = item['meta']
        identifier = get_identifier(meta)
        market = market_from_spider(spider)

        for version, values in item['versions'].items():
            r = requests.get(values['dl_link'], allow_redirects=True)
            if r.status_code == 200:
                apk = r.content

                fname = f"{version}.apk"
                fpath = os.path.join(self.outdir, market, identifier, fname)

                os.makedirs(os.path.dirname(fpath), exist_ok=True)

                with open(fpath, 'wb') as f:
                    f.write(apk)
        return item

def get_identifier(meta):
    """
    Returns the identifier of a package given its meta information.
    The identifier is either a 'pkg_name' or an 'id' field
    Args:
        meta: dict

    Returns:
        str: identifier of package
    """
    if 'pkg_name' in meta:
        return meta['pkg_name']
    if 'id' in meta:
        return meta['id']
    else:
        raise Exception('cannot find identifier for app')


def market_from_spider(spider):
    market = spider.name
    m = re.search("(.*)_spider", market)
    if m:
        market = m.group(1)
    return market
