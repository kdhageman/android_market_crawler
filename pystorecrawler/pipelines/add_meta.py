import time

from pystorecrawler.item import Meta
from pystorecrawler.pipelines.util import market_from_spider


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