import re

import scrapy

from crawler.spiders.util import normalize_rating

version_pattern = '版本: (.*)'
id_pattern = "https?://shouji\.baidu\.com/(.*?)/(.*)\.html"


class BaiduSpider(scrapy.Spider):
    name = "baidu_spider"

    def start_requests(self):
        url = "https://shouji.baidu.com/"
        self.logger.debug(f"scheduling new starting URL: {url}")
        yield scrapy.Request(url, self.parse)

        url = 'https://shouji.baidu.com/rank/top/'
        self.logger.debug(f"scheduling new starting URL: {url}")
        yield scrapy.Request(url, self.parse_top_page)

    def parse(self, response):
        """
        Crawls the homepage for apps
        Example URL: http://as.baidu.com/

        Args:
            response: scrapy.Response
        """
        for pkg_link in response.css("div.sec-app a.app-box::attr(href)").getall():
            self.logger.debug(f"scheduling new app URL: {pkg_link}")
            full_url = response.urljoin(pkg_link)
            req = scrapy.Request(full_url, callback=self.parse_pkg_page, priority=2)
            yield req

    def parse_top_page(self, response):
        """
        Crawls the page of top apps
        Example URL: https://as.baidu.com/rank/top/
        Args:
            response: scrapy.Response
        """
        res = []

        # visit all apps
        for pkg_link in response.css("div.sec-app a.app-box::attr(href)").getall():
            self.logger.debug(f"scheduling new app URL: {pkg_link}")
            full_url = response.urljoin(pkg_link)
            req = scrapy.Request(full_url, callback=self.parse_pkg_page, priority=2)
            res.append(req)

        # follow pagination
        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            self.logger.debug(f"scheduling new top page: {next_page}")
            full_url = response.urljoin(next_page)
            req = scrapy.Request(full_url, callback=self.parse_top_page)
            res.append(req)

        return req

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        Example URL: http://as.baidu.com/software/26600966.html

        Args:
            response: scrapy.Response
        """
        res = []
        meta = dict(
            url=response.url
        )
        yui3 = response.css("div.yui3-u")
        meta['app_name'] = yui3.css("div.intro-top h1.app-name > span::text").get()
        if not meta['app_name']:
            # we found a non-existing app page
            return
        meta['app_description'] = "\n".join(yui3.css("div.section-container.introduction div.brief-long p::text").getall())

        # increment internal identifier by one
        m = re.search(id_pattern, response.url)
        if m:
            type = m.group(1)
            id = int(m.group(2))
            meta["id"] = f"{type}-{id}"
            pkg_url = f"https://shouji.baidu.com/{type}/{id+1}.html"
            req = scrapy.Request(pkg_url, callback=self.parse_pkg_page, priority=1)
            res.append(req)
        else:
            self.logger.debug(f"failed to identify the identifier for '{response.request.url}'")

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

        res.append(dict(
            meta=meta,
            versions=versions
        ))

        # apps you might like
        for pkg_link in response.css("div.sec-favourite a.app-box::attr(href)").getall():
            full_url = response.urljoin(pkg_link)
            req = scrapy.Request(full_url, callback=self.parse_pkg_page, priority=2)
            res.append(req)

        return res
