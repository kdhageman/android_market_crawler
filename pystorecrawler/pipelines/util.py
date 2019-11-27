import os
import re

import scrapy

import pystorecrawler
from pystorecrawler.item import Meta


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
    """
    Returns the name of the marker of a given spider instance
    Args:
        spider: scrapy.Spider

    Returns:
        str: name of market
    """
    market = spider.name
    m = re.search("(.*)_spider", market)
    if m:
        market = m.group(1)
    return market


def meta_directory(item, spider):
    """
    Returns the relative directory in which to store APKs and meta.json

    Args:
        spider: scrapy.Spider
            spider that crawled the item
        item: pystorecrawler.item.Meta
            item resulting from crawl

    Returns:
        str: relative directory in which to store APKs and meta.json
    """
    if not isinstance(item, Meta):
        raise Exception("invalid item type")

    meta = item['meta']
    identifier = get_identifier(meta)
    market = market_from_spider(spider)

    return os.path.join(market, identifier)


class TestSpider(scrapy.Spider):
    """
    Spider for testing purposes
    """
    name = "test_spider"

    def parse(self, response):
        pass
