import io
import time
from datetime import datetime, timedelta
import hashlib
import os
import re
from random import choice

import scrapy
from scrapy.settings import Settings
from scrapy.statscollectors import MemoryStatsCollector
from treq import get as treqget
from twisted.internet import defer

PROXY_POOL = None


class NoProxiesError(Exception):
    pass


def init_proxy_pool(crawler, proxies):
    global PROXY_POOL
    if not PROXY_POOL:
        PROXY_POOL = BackoffProxyPool(crawler, proxies)


class BackoffProxyPool:
    def __init__(self, crawler, proxies):
        self.crawler = crawler
        self.proxies = {}
        for proxy in proxies:
            self.proxies[proxy] = None

        self.use_proxies = len(proxies) > 0
        self.non_proxy_until = datetime.now()

        crawler.spider.logger.debug(f"initialized {len(proxies)} proxies")

    def _available_proxies(self):
        """
        Returns the list of proxies that is currently available
        """
        res = []

        now = datetime.now()
        for proxy, blocked_until in self.proxies.items():
            if not blocked_until:
                res.append(proxy)
            elif now >= blocked_until:
                res.append(proxy)
                self.proxies[proxy] = None
        return res

    def _time_until_next_available(self):
        """
        Returns the time until the first proxy becomes available
        """
        if not self.use_proxies:
            res = (self.non_proxy_until - datetime.now()).total_seconds()
            res = max(res, 0)
            return res
        else:
            earliest_available = None
            for until in self.proxies.values():
                if not earliest_available or (until and until < earliest_available):
                    earliest_available = until
            if not earliest_available:
                return 0
            res = (earliest_available - datetime.now()).total_seconds()
            res = max(res, 0)
            return res

    def _pause(self, t):
        """
        Pause the crawler 't' seconds
        """
        try:
            self.crawler.engine.pause()
            time.sleep(t)
        finally:
            self.crawler.engine.unpause()

    def get_proxy(self):
        """
        Returns a random proxy that is not rate limited
        If none available, return the time until the next becomes available
        """
        wait_time = self._time_until_next_available()
        if wait_time:
            self.crawler.spider.logger.debug(f"backing off for {wait_time:.2f} seconds")
        self._pause(wait_time)

        if not self.use_proxies:
            return {}
        else:
            available = self._available_proxies()
            if available:
                return choice(available)
            return Exception("should never happen!")

    def get_proxy_as_dict(self):
        return get_proxy_as_dict(self.get_proxy())

    def backoff(self, proxy, **kwargs):
        """
        Blocks the proxy from being used until "until"
        Args:
            proxy: proxy to backoff
            duration: time delta in milliseconds

        Returns:

        """
        until = datetime.now() + timedelta(**kwargs)
        if not proxy:
            self.non_proxy_until = until
        else:
            self.proxies[proxy] = until


def get_proxy_as_dict(proxy):
    """
    Returns a proxy dictionary to be used by 'request' or 'treq' library
    """
    if not proxy:
        return {}
    full_url = f"http://{proxy}"
    return {
        "http": full_url,
        "https": full_url
    }


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


class RequestException(Exception):
    pass


class ContentTypeError(Exception):
    pass


class UnknownInputError(Exception):
    pass


class HttpClient:
    def __init__(self, crawler):
        self.crawler = crawler

    @defer.inlineCallbacks
    def get(self, url, **kwargs):
        resp = yield treqget(url, kwargs)

        resp_codes = self.crawler.stats.get_value("response_codes", default={})
        resp_codes[resp.code] = resp_codes.get(resp.code, 0) + 1
        self.crawler.stats.set_value("response_codes", resp_codes)
        defer.returnValue(resp)


def sha256(f):
    """
    Returns the lowercase hex representation of the SHA 256 digest of the data
    Args:
        f: bytes or io.BufferedReader

    Returns: str
        Hex representation of SHA 256 digest of data
    """
    m = hashlib.sha256()
    if type(f) == bytes:
        m.update(f)
    elif type(f) == io.BufferedReader:
        for byte_block in iter(lambda: f.read(4096), b""):
            m.update(byte_block)
    else:
        raise UnknownInputError()
    return m.hexdigest()


def is_success(status_code):
    return 200 <= status_code < 400


def response_has_content_type(resp, ct):
    """
    Returns if response contains a "Content-Type" header with the given 'ct' value
    Args:
        resp: twister.Response
        ct: content type string
        default: default result if header is empty

    Returns: bool
    """
    received_ctypes = resp.headers.getRawHeaders("Content-Type")
    if not received_ctypes:
        return False
    return ct.lower() in [n.lower() for n in received_ctypes]
