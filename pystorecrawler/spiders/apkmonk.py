import json

import scrapy

from pystorecrawler.item import Meta
from pystorecrawler.spiders.util import version_name

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
        meta = dict(
            url=response.url
        )
        meta['app_name'] = response.css("h1::text").get()
        trows = response.css("div.box")[1].css("table tr")
        meta['developer_name'] = trows[3].css("td > span::text").get()
        meta['pkg_name'] = trows[7].css("td::text").getall()[1]
        meta['app_description'] = "\n".join(response.xpath("//div[@class='box' and .//div[@class='box-title']/text()='About this app']//p[@id='descr']//text()").getall())

        category = " ".join([i.strip() for i in trows[4].css("td")[1].css("::text").getall()])
        meta['categories'] = [category]
        meta['content_rating'] = trows[5].css("td")[1].css("::text").get()
        meta['icon_url'] = response.xpath("//img[@class = 'hide-on-med-and-down']//@data-src").get()

        # all versions
        versions = []
        version_rows = response.xpath("//div[@class='box' and .//div[@class = 'box-title']/text()='All Versions']//tr")

        remaining = []
        for r in version_rows:
            version, date = r.css("td ::text").getall()
            dl_link_parts = r.css("td a::attr(href)").re(url_pattern)

            if dl_link_parts and len(dl_link_parts) == 2:
                full_url = dl_url_tmpl % tuple(dl_link_parts)
                version = version_name(version, versions)
                versions.append(version)
                remaining.append((full_url, version, date))

        next = remaining.pop()
        data = dict(
            cur=next,
            remaining=remaining,
            meta=meta,
            versions={}
        )

        return scrapy.Request(next[0], callback=self.parse_download_link_page, meta=data)


    def parse_download_link_page(self, response):
        dl_url = json.loads(response.body)['url']
        data = response.meta

        _, version, date = data['cur']
        data['versions'][version] = dict(
            timestamp=date,
            download_url=dl_url
        )

        if len(data['remaining']) == 0:
            # this is the last download link to be returned
            return Meta(meta=data['meta'], versions=data['versions'])

        next = data['remaining'].pop()
        data['cur'] = next

        return scrapy.Request(next[0], callback=self.parse_download_link_page, meta=data)

