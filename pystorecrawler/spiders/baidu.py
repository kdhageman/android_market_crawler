import re

import scrapy

from pystorecrawler.item import Meta
from pystorecrawler.spiders.util import normalize_rating

version_pattern = '版本: (.*)'
id_pattern = "http://as\.baidu\.com/(.*?)/(.*)\.html"


class BaiduSpider(scrapy.Spider):
    name = "baidu_spider"

    def start_requests(self):
        yield scrapy.Request('http://as.baidu.com/', self.parse)
        yield scrapy.Request('https://as.baidu.com/rank/top/', self.parse_top_page)

    def parse(self, response):
        """
        Crawls the homepage for apps
        Example URL: http://as.baidu.com/

        Args:
            response: scrapy.Response
        """
        for pkg_link in response.css("div.sec-app a.app-box::attr(href)").getall():
            yield response.follow(pkg_link, callback=self.parse_pkg_page)

    def parse_top_page(self, response):
        """
        Crawls the page of top apps
        Example URL: https://as.baidu.com/rank/top/
        Args:
            response: scrapy.Response
        """
        # visit all apps
        for pkg_link in response.css("div.sec-app a.app-box::attr(href)").getall():
            yield response.follow(pkg_link, callback=self.parse_pkg_page)

        # follow pagination
        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse_top_page)

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        Example URL: http://as.baidu.com/software/26600966.html

        Args:
            response: scrapy.Response
        """
        meta = dict(
            url=response.url
        )
        yui3 = response.css("div.yui3-u")
        meta['app_name'] = yui3.css("div.intro-top h1.app-name > span::text").get()
        meta['app_description'] = "\n".join(yui3.css("div.section-container.introduction div.brief-long p::text").getall())

        m = re.search(id_pattern, response.url)
        if m:
            meta["id"] = f"{m.group(1)}-{m.group(2)}"

        meta['downloads'] = response.css("span.download-num::text").re("下载次数: (.*)")[0]

        categories = []
        categories.append(response.css("div.app-nav div.nav span a::text").getall()[-1])
        meta['categories'] = categories

        meta['icon_url'] = response.css("div.app-pic img::attr(src)").get()
        user_rating = response.css("span.star-percent::attr(style)").re("width:(.*)%")[0]
        meta['user_rating'] = normalize_rating(user_rating, 100)

        versions = dict()
        m = re.search(version_pattern, yui3.css("span.version::text").get())
        if m:
            version = m.group(1)
            dl_link = yui3.css("a.apk::attr(href)").get()
            versions[version] = dict(
                # TODO: timestamp?
                download_url=dl_link
            )

        res = Meta(
            meta=meta,
            versions=versions
        )

        yield res

        # apps you might like
        for pkg_link in response.css("div.sec-favourite a.app-box::attr(href)").getall()  :
            full_url = response.urljoin(pkg_link )
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)
