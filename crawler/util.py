import hashlib
import os
import re
from random import choice

import requests
import scrapy
from eventlet import Timeout
from scrapy.settings import Settings
from scrapy.statscollectors import MemoryStatsCollector

_PROXIES = []


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


def get_directory(meta, spider):
    """
    Returns the relative directory in which to store APKs, icon files, meta.json, etc.

    Args:
        spider: scrapy.Spider
            spider that crawled the item
        item: crawler.item.Meta
            item resulting from crawl

    Returns:
        str: relative directory in which to store APKs and meta.json
    """
    identifier = get_identifier(meta)
    market = market_from_spider(spider)

    return os.path.join(market, identifier)


class TestEngine:
    def pause(self):
        pass

    def unpause(self):
        pass


class TestCrawler:
    def __init__(self):
        self.settings = Settings()
        self.stats = MemoryStatsCollector(self)
        self.engine = TestEngine()
        self.spider = None


class TestSpider(scrapy.Spider):
    """
    Spider for testing purposes
    """
    name = "test_spider"

    def __init__(self):
        self.crawler = TestCrawler()

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
    with Timeout(timeout,
                 False):  # ensure that APK downloading does not exceed timeout duration; TODO: is this preferred behaviour?
        r = requests.get(url, allow_redirects=True, timeout=60)

    if not r:
        raise TimeoutError(f"request timeout for '{url}'")

    return r


def sha256(f):
    """
    Returns the lowercase hex representation of the SHA 256 digest of the data
    Args:
        f: file

    Returns: str
        Hex representation of SHA 256 digest of data
    """
    m = hashlib.sha256()
    for byte_block in iter(lambda: f.read(4096), b""):
        m.update(byte_block)
    return m.hexdigest()


def random_proxy():
    """
    Assigns a random proxy dictionary to be used by requests or the GooglePlayApi
    Returns: dict; example: {'http': ..., 'https': ...}
    """
    try:
        selected = choice(_PROXIES)
        full_url = f"http://{selected}"
        return {
            "http": full_url,
            "https": full_url
        }
    except IndexError:
        return {}


def is_success(status_code):
    return 200 <= status_code < 400
