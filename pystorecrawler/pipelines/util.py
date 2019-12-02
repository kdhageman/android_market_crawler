import hashlib
import os
import re

import requests
import scrapy
from eventlet import Timeout

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
    Returns the relative directory in which to store APKs, icon files, meta.json, etc.

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

def get(url, timeout):
    """
    Performs an HTTP GET request for the given URL, and ensures that the entire requests does not exceed the timeout value (in ms)
    If the timeout is zero, request does not terminate on the usual timeout; however, internally it uses the requests timeout to terminate on bad connections

    Args:
        url: url to request
        timeout: timeout for entire request

    Returns: requests.Response
    """
    if timeout == 0:
        return requests.get(url, allow_redirects=True, timeout=60)

    r = None
    with Timeout(timeout, False):  # ensure that APK downloading does not exceed timeout duration; TODO: is this preferred behaviour?
        r = requests.get(url, allow_redirects=True, timeout=60)

    if not r:
        raise TimeoutError(f"request timeout for '{url}'")

    return r

def sha256(data):
    """
    Returns the lowercase hex representation of the SHA 256 digest of the data
    Args:
        data: bytes

    Returns: str
        Hex representation of SHA 256 digest of data
    """
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()