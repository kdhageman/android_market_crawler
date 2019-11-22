import re

import scrapy

version_pattern = '版本: (.*)'


class BaiduSpider(scrapy.Spider):
    name = "baidu_spider"
    start_urls = ['http://as.baidu.com/']

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps
        :param response:
        :return:
        """
        for pkg_link in response.css("div.sec-app").css("a.app-box::attr(href)").getall() :
            full_url = response.urljoin(pkg_link)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        :param response:
        :return:
        """
        meta = dict()
        yui3 = response.css("div.yui3-u")
        meta['app_name'] = yui3.css("div.intro-top").css("h1.app-name > span::text").get()
        meta['app_description'] = yui3.css("div.section-container.introduction").css(
            "div.brief-short > p.content::text").get()  # TODO: this is the 'collapsed' version of the description

        m = re.search(version_pattern, yui3.css("span.version::text").get())
        if m:
            meta["version"] = m.group(1)

        res = dict(
            meta=meta,
            download_urls=[]
        )

        # find download link
        dl_link = yui3.css("a.apk::attr(href)").get()
        if dl_link:
            res['download_urls'].append(dl_link)

        # apps you might like; TODO: scroll through all these apps instead of only the first couple
        for pkg_link in response.css("div.sec-favourite * div.app-bd.show * a.app-box::attr(href)").getall():
            full_url = response.urljoin(pkg_link )
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

        return res
