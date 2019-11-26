import json
import re

import requests
import scrapy

from spider.util import version_name

url_pattern = "/download-app/(.*)/(.*)/"
dl_url_tmpl = "https://www.apkmonk.com/down_file/?pkg=%s&key=%s"


class ApkMonkSpider(scrapy.Spider):
    name = "apkmonk_spider"
    start_urls = ['https://www.apkmonk.com/']

    def parse(self, response):
        """
        Crawls the homepage for apps
        Example URL: https://www.apkmonk.com/

        Args:
            response: scrapy.Response
        """
        # trending and top picks
        for pkg_link in response.css("div.col.l8.m8.s12 * div.section.side-padding-8 * a::attr(href)").getall():
            full_url = response.urljoin(pkg_link)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        Example URL: https://www.apkmonk.com/app/ir.behbahan.tekken/
                     https://www.apkmonk.com/app/com.mkietis.osgame/

        Args:
            response: scrapy.Response
        """
        # meta data
        meta = dict()
        meta['app_name'] = response.css("h1::text").get()
        trows = response.css("div.box")[1].css("table * tr")
        meta['developer_name'] = trows[3].css("td > span::text").get()
        meta['pkg_name'] = trows[7].css("td::text").getall()[1]
        meta['app_description'] = "\n".join(response.xpath("//div[@class='box' and .//div[@class='box-title']/text()='About this app']//p[@id='descr']//text()").getall())

        # all versions
        versions = dict()
        version_rows = response.xpath("//div[@class='box' and .//div[@class = 'box-title']/text()='All Versions']//tr")
        for r in version_rows:
            version, date = r.css("td ::text").getall()
            dl_link = r.css("td a::attr(href)").get()

            m = re.search(url_pattern, dl_link)
            if m:
                pkg = m.group(1)
                key = m.group(2)
                full_url = dl_url_tmpl % (pkg, key)

                headers = {
                    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"
                }

                r = requests.get(full_url, headers=headers)
                dl_url = json.loads(r.content)['url']

                version = version_name(version, versions)

                versions[version] = dict(
                    date=date,
                    dl_link=dl_url
                )

        res = dict(
            meta=meta,
            versions=versions
        )

        return res