import re

import scrapy

pkg_pattern = "https://android\.myapp\.com/myapp/detail\.htm\?apkName=(.*)"


class TencentSpider(scrapy.Spider):
    name = "tencent_spider"
    start_urls = ['https://android.myapp.com/']

    def parse(self, response):
        """
        Parses the front page for packages
        Example URL: https://android.myapp.com/

        Args:
            response: scrapy.Response
        """
        # find links to other apps
        for link in response. \
                css("a::attr(href)"). \
                re("../myapp/detail.htm\?apkName=.*"):
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            yield scrapy.Request(next_page, callback=self.parse_pkg_page)  # add URL to set of URLs to crawl

    def parse_pkg_page(self, response):
        """
        Parses the page of a single package
        Example URL: https://android.myapp.com/myapp/detail.htm?apkName=ctrip.android.view

        Args:
            response: scrapy.Response
        """
        # find meta data
        meta = dict()

        divs = response.css("div.det-othinfo-container div.det-othinfo-data")

        meta['developer_name'] = divs[2].css("::text").get()
        meta['app_name'] = response.css("div.det-name-int::text").get()
        meta['app_description'] = response.css("div.det-app-data-info::text").get()

        m = re.search(pkg_pattern, response.url)
        if m:
            meta['pkg_name'] = m.group(1)

        # find download button(s)
        versions = dict()
        version = divs[0].css("::text").get()
        dl_link = response.css("a::attr(data-apkurl)").get()
        date = divs[1].attrib['data-apkpublishtime'] # as unix timestamp

        versions[version] = dict(
            date=date,
            dl_link=dl_link
        )

        res = dict(
            meta=meta,
            versions=versions
        )

        return res
