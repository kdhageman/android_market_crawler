import json
import re
import time

import numpy as np
import requests
import scrapy

from crawler.item import Result
from crawler.spiders.util import PackageListSpider

pkg_pattern = "https://play.google.com/store/apps/details\?id=(.*)"


class ApiUnavailableError(Exception):
    def __init__(self):
        super().__init__("API is unavailable, start the API first (check README)")


class GooglePlaySpider(PackageListSpider):
    """
    This Spider returns spider.tem.PackageName instead of meta data and versions
    """

    name = "googleplay_spider"

    def __init__(self, crawler, outdir, apiurl="http://localhost:5000", interval=1):
        super().__init__(crawler=crawler, settings=crawler.settings)
        self.outdir = outdir
        self.apiurl = apiurl
        self.interval = interval

    @classmethod
    def from_crawler(cls, crawler):
        outdir = crawler.settings.get("CRAWL_ROOTDIR", "/tmp/crawl")
        params = crawler.settings.get("GPLAY_PARAMS")
        apiurl = params.get("apiurl")
        interval = params.get("interval", 0.25)

        # check if the api is available
        url = f"{apiurl}/ping"
        try:
            requests.get(url)
        except requests.exceptions.ConnectionError:
            raise ApiUnavailableError

        return cls(crawler, outdir, apiurl=apiurl, interval=interval)

    def start_requests(self):
        yield scrapy.Request('https://play.google.com/store/apps', self.parse)
        for req in super().start_requests():
            yield req

    def url_by_package(self, pkg):
        return f"https://play.google.com/store/apps/details?id={pkg}"

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps

        Args:
            response: scrapy.Response
        """
        # find all links to packages on the overview page
        # pkgs = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        res = []

        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            req = scrapy.Request(full_url, priority=1, callback=self.parse_pkg_page)
            res.append(req)

        # follow 'See more' buttons on the home page
        see_more_links = response.xpath("//a[text() = 'See more']//@href").getall()
        for link in see_more_links:
            full_url = response.urljoin(link)
            req = scrapy.Request(full_url, callback=self.parse_similar_apps)
            res.append(req)

        # follow categories on the home page
        category_links = response.css("#action-dropdown-children-Categories a::attr(href)").getall()
        for link in category_links:
            full_url = response.urljoin(link)
            req = scrapy.Request(full_url, callback=self.parse)
            res.append(req)

        return res

    def parse_pkg_page(self, response):
        """
        Parses the page of a single package
        Example URL: https://play.google.com/store/apps/details?id=com.mi.android.globalminusscreen

        Args:
            response:
        """

        res = []

        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            req = scrapy.Request(full_url, callback=self.parse_pkg_page)
            res.append(req)

        # package name
        m = re.search(pkg_pattern, response.url)
        if m:
            pkg = m.group(1)
            full_url = f"{self.apiurl}/details?pkg={pkg}"
            req = scrapy.Request(full_url, callback=self.parse_details, meta={'pkg': pkg}, priority=10)
            res.append(req)

        # similar apps
        similar_link = response.xpath("//a[contains(@aria-label, 'Similar')]//@href").get()
        if similar_link:
            full_url = response.urljoin(similar_link)
            req = scrapy.Request(full_url, callback=self.parse_similar_apps)
            res.append(req)

        return res

    def parse_details(self, response):
        """
        Parses the retrieved details from a locally running API
        Example URL: localhost:5000/details?pkg=com.quizlet.quizletandroid

        Args:
            response:
        """
        pkg = response.meta.get("pkg", None)
        meta = json.loads(response.body_as_unicode())

        self.pause(self.interval)

        # we assume that there is only one version of the apk
        for version, dat in meta.get('versions', {}).items():
            available = meta.get("meta", {}).get("available", False)
            offer_type = meta.get("meta", {}).get("offer_type", 1)
            version_code = dat['code']
            if available:
                url = f"{self.apiurl}/download?pkg={pkg}&version_code={version_code}&offer_type={offer_type}"
                dat['download_url'] = url
                meta['versions'][version] = dat
            else:
                self.logger.warn(f"package '{pkg}' is unavailable")
        return Result(
            meta=meta.get('meta', {}),
            versions=meta.get('versions', {}),
        )

    def parse_similar_apps(self, response):
        """
        Parses a page of similar apps
        Example URL: https://play.google.com/store/apps/collection/cluster?clp=ogouCBEqAggIMiYKIGNvbS5taS5hbmRyb2lkLmdsb2JhbG1pbnVzc2NyZWVuEAEYAw%3D%3D:S:ANO1ljJT8p0&gsr=CjGiCi4IESoCCAgyJgogY29tLm1pLmFuZHJvaWQuZ2xvYmFsbWludXNzY3JlZW4QARgD:S:ANO1ljK6BA8

        Args:
            response:
        """
        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        res = []

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            req = scrapy.Request(full_url, callback=self.parse_pkg_page)
            res.append(req)

        return res

    def pause(self, t):
        """
        Pause the crawler for t seconds
        Args:
            t: int
                number of seconds to pause crawler
        """
        if t:
            self.crawler.engine.pause()
            time.sleep(t)
            self.crawler.engine.unpause()
