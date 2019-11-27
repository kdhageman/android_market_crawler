import re

import scrapy

from pystorecrawler.item import Meta

version_pattern = '版本: (.*)'
id_pattern = "http://as\.baidu\.com/(.*?)/(.*)\.html"


class BaiduSpider(scrapy.Spider):
    name = "baidu_spider"
    start_urls = ['http://as.baidu.com/']

    def parse(self, response):
        """
        Crawls the homepage for apps
        Example URL: http://as.baidu.com/

        Args:
            response: scrapy.Response
        """
        for pkg_link in response.css("div.sec-app a.app-box::attr(href)").getall() :
            full_url = response.urljoin(pkg_link)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        Example URL: http://as.baidu.com/software/26600966.html

        Args:
            response: scrapy.Response
        """
        meta = dict()
        yui3 = response.css("div.yui3-u")
        meta['app_name'] = yui3.css("div.intro-top h1.app-name > span::text").get()
        meta['app_description'] = "\n".join(yui3.css("div.section-container.introduction div.brief-long p::text").getall())

        m = re.search(id_pattern, response.url)
        if m:
            meta["id"] = f"{m.group(1)}-{m.group(2)}"

        versions = dict()
        m = re.search(version_pattern, yui3.css("span.version::text").get())
        if m:
            version = m.group(1)
            dl_link = yui3.css("a.apk::attr(href)").get()
            versions[version] = dict(
                dl_link=dl_link
            )

        res = Meta(
            meta=meta,
            versions=versions
        )

        # apps you might like
        for pkg_link in response.css("div.sec-favourite div.app-bda.app-box::attr(href)").getall():
            full_url = response.urljoin(pkg_link )
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

        yield res
