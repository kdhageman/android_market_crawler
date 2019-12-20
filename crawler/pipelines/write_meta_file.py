import json
import os

from crawler.item import Meta
from crawler.util import get_directory

FNAME = "meta.json"


class WriteMetaFilePipeline:
    """
    Writes meta data to meta.json files
    """

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            outdir=crawler.settings.get('CRAWL_ROOTDIR')
        )

    def __init__(self, outdir):
        self.outdir = outdir

    def process_item(self, item, spider):
        """
        Writes the meta data of a crawled (app, market)-tuple to a meta.json file
        This file is located in the same directory in which the APKs are stored

        Args:
            item: dict of download URLs and store meta data
            spider: spider that crawled the market
        """
        if not isinstance(item, Meta):
            return item

        meta_dir = get_directory(item['meta'], spider)
        fpath = os.path.join(self.outdir, meta_dir, FNAME)

        os.makedirs(os.path.dirname(fpath), exist_ok=True) # ensure directories exist

        with open(fpath, "a+") as f:
            jsonstr = json.dumps(dict(item))
            f.write(jsonstr + "\n")

        return item
