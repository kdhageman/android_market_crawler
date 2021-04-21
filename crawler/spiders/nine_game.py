import re

import scrapy

from crawler.item import Result
from crawler.spiders.util import normalize_rating

identifier_pattern = "http:\/\/www\.9game\.com\/(.*)\.html.*"


class NineGameSpider(scrapy.Spider):
    name = "9game_spider"
    start_urls = ['http://www.9game.com/']

    def parse(self, response):
        """
        Crawls the homepage for apps
        Example URL: http://www.9game.com/
        Args:
            response: scrapy.Response
        """
        res = []

        for link in response.css("a.inner::attr(href)").getall():
            full_url = response.urljoin(link)
            req = scrapy.Request(full_url, callback=self.parse_pkg_page)
            res.append(req)
        return res

    # TODO: all version of APK
    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        Example URL: http://www.9game.com/Free-Fire-Battlegrounds.html

        Args:
           response: scrapy.Response
        """
        res = []

        downloads = response.css("span.download-count::text").get()
        app_name = response.css("h1.name span::text").get()
        icon_url = response.css("div.main-info div.pic img::attr(dataimg)").get()
        user_rating = response.css("span.rate::text").get()
        user_rating = normalize_rating(user_rating, 5)

        category = response.css("a.category::text").get().replace("\"", "", -1).strip()
        app_description = response.css("p.text").get()
        download_path = response.css("a.btn-fast-download::attr(onclick)").re("fastDownload\('.*','(.*)'\)")
        if len(download_path) > 0:
            download_url = response.urljoin(download_path[0])

        meta = dict(
            app_name=app_name,
            app_description=app_description,
            icon_url=icon_url,
            user_rating=user_rating,
            categories=[category],
            downloads=downloads
        )

        m = re.search(identifier_pattern, response.url)
        if m:
            identifier = m.group(1).lower()
            meta['id'] = identifier

        versions = dict(
            current=dict(
                timestamp='unknown',
                download_url=download_url
            )
        )

        res.append(Result(
            meta=meta,
            versions=versions
        ))

        # related apps
        for link in response.css("a.inner::attr(href)").getall():
            full_url = response.urljoin(link)
        req = scrapy.Request(full_url, callback=self.parse_pkg_page)
        res.append(req)

        return res
