import re

import numpy as np
import scrapy

from pystorecrawler.item import PackageName
from pystorecrawler.spiders.util import PackageListSpider

pkg_pattern = "https://play.google.com/store/apps/details\?id=(.*)"


class GooglePlaySpider(PackageListSpider):
    """
    This Spider returns spider.tem.PackageName instead of meta data and versions
    """

    name = "googleplay_spider"

    def start_requests(self):
        for req in super().start_requests():
            yield req
        yield scrapy.Request('https://play.google.com/store/apps', self.parse)

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

        # follow 'See more' buttons on the home page
        see_more_links = response.xpath("//a[text() = 'See more']//@href").getall()
        for link in see_more_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_similar_apps)

        # follow categories on the home page
        category_links = response.css("#action-dropdown-children-Categories a::attr(href)").getall()
        for link in category_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse)

        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Parses the page of a single package
        Example URL: https://play.google.com/store/apps/details?id=com.mi.android.globalminusscreen

        Args:
            response:
        """

        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

        # similar apps
        similar_link = response.xpath("//a[contains(@aria-label, 'Similar')]//@href").get()
        if similar_link:
            full_url = response.urljoin(similar_link)
            yield scrapy.Request(full_url, callback=self.parse_similar_apps)

        # package name
        m = re.search(pkg_pattern, response.url)
        if m:
            yield PackageName(name=m.group(1))

    def parse_similar_apps(self, response):
        """
        Parses a page of similar apps
        Example URL: https://play.google.com/store/apps/collection/cluster?clp=ogouCBEqAggIMiYKIGNvbS5taS5hbmRyb2lkLmdsb2JhbG1pbnVzc2NyZWVuEAEYAw%3D%3D:S:ANO1ljJT8p0&gsr=CjGiCi4IESoCCAgyJgogY29tLm1pLmFuZHJvaWQuZ2xvYmFsbWludXNzY3JlZW4QARgD:S:ANO1ljK6BA8

        Args:
            response:
        """
        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)
