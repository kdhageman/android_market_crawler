import re

import scrapy

from pystorecrawler.item import Meta
from pystorecrawler.spiders.util import normalize_rating

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
        meta = dict(
            url=response.url
        )

        divs = response.css("div.det-othinfo-container div.det-othinfo-data")

        meta['developer_name'] = divs[2].css("::text").get()
        meta['app_name'] = response.css("div.det-name-int::text").get()
        meta['app_description'] = response.css("div.det-app-data-info::text").get()

        m = re.search(pkg_pattern, response.url)
        if m:
            meta['pkg_name'] = m.group(1)

        user_rating = response.css("div.com-blue-star-num::text").re("(.*)分")[0]
        meta['user_rating'] = normalize_rating(user_rating, 5)
        meta['downloads'] = response.css("div.det-insnum-line div.det-ins-num::text").get()

        category = response.css("#J_DetCate::text").get()
        meta['categories'] = [category]
        meta['icon_url'] = response.css("div.det-icon img::attr(src)").get()

        # find download button(s)
        versions = dict()
        version = divs[0].css("::text").get()
        dl_link = response.css("a::attr(data-apkurl)").get()
        date = divs[1].attrib['data-apkpublishtime'] # as unix timestamp

        versions[version] = dict(
            timestamp=date,
            download_url=dl_link
        )

        res = Meta(
            meta=meta,
            versions=versions
        )

        return res
