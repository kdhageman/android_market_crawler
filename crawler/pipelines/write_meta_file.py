import json
import os

from crawler.item import Result
from crawler.store.janusgraph import Store
from crawler.util import get_directory

FNAME = "meta.json"


class WriteMetaFilePipeline:
    """
    Writes meta data to meta.json files
    """

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            params=crawler.settings.get('JANUS_PARAMS')
        )

    def __init__(self, params):
        self.store = Store(**params)

    def process_item(self, item, spider):
        """
        Writes the meta data of a crawled (app, market)-tuple to a meta.json file
        This file is located in the same directory in which the APKs are stored

        Args:
            item: dict of download URLs and store meta data
            spider: spider that crawled the market
        """
        if not isinstance(item, Result):
            return item

        self.store.store_result(item)

        return item
