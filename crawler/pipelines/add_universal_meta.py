import time

from crawler.pipelines.util import timed
from crawler.util import market_from_spider


class AddUniversalMetaPipeline:
    @timed("AddUniversalMetaPipeline")
    def process_item(self, item, spider):
        """
        Adds a timestamp/market name to the meta data in the item
        """

        res = item
        res['meta']['timestamp'] = int(time.time())
        market = market_from_spider(spider)
        res['meta']['market'] = market

        return res