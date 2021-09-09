import json

import scrapy

from crawler.item import Result
from crawler.spiders.util import version_name, PackageListSpider

url_pattern = "/download-app/(.*)/(.*)/"
dl_url_tmpl = "https://www.apkmonk.com/down_file/?pkg=%s&key=%s"


class ApkMonkSpider(PackageListSpider):
    name = "apkmonk_spider"

    def __init__(self, crawler):
        super().__init__(crawler=crawler, settings=crawler.settings)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def start_requests(self):
        for req in super().start_requests():
            yield req

    def base_requests(self, meta={}):
        return [scrapy.Request('https://www.apkmonk.com/categories/', callback=self.parse, meta=meta)]

    def url_by_package(self, pkg):
        return f"https://www.apkmonk.com/app/{pkg}/"

    def parse(self, response):
        """
        Crawls the homepage for apps
        Example URL: https://www.apkmonk.com/

        Args:
            response: scrapy.Response
        """
        # visit all individual category pages
        res = []
        for category_url in response.css("a.waves-effect::attr(href)").getall():
            if category_url:
                req = response.follow(category_url, callback=self.parse_category)
                res.append(req)

        return res

    def parse_category(self, response):
        """
        Crawls a paginated category page
        """
        res = []
        # go to package pages
        for pkg in response.css("a::attr(href)").re("/app(?:/id)?/(.+)/"):
            pkg_url = f"/app/id/{pkg}/"
            req = response.follow(pkg_url, callback=self.parse_pkg_page, priority=20)
            res.append(req)

        # pagination
        for category_url in response.css("div.selection a::attr(href)").getall():
            req = response.follow(category_url, callback=self.parse_category)
            res.append(req)

        return res

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
        meta['app_description'] = "\n".join(response.xpath(
            "//div[@class='box' and .//div[@class='box-title']/text()='About this app']//p[@id='descr']//text()").getall())

        category = " ".join([i.strip() for i in trows[4].css("td")[1].css("::text").getall()])
        meta['categories'] = [category]
        meta['content_rating'] = trows[5].css("td")[1].css("::text").get()
        meta['icon_url'] = response.xpath("//img[@class = 'hide-on-med-and-down']//@data-src").get()

        # all versions
        versions = []
        version_rows = response.xpath(
            "//div[@class='box' and .//div[@class = 'box-title' and (contains(./text(),'Semua Versi') or contains(./text(),'All Versions'))]]//tr")

        remaining = []
        for r in version_rows:
            version, date = r.css("td ::text").getall()
            dl_link_parts = r.css("td a::attr(href)").re(url_pattern)

            if dl_link_parts and len(dl_link_parts) == 2:
                full_url = dl_url_tmpl % tuple(dl_link_parts)
                version = version_name(version, versions)
                versions.append(version)
                remaining.append((full_url, version, date))

        if remaining:
            next_version = remaining.pop()
            data = dict(
                cur=next_version,
                remaining=remaining,
                meta=meta,
                versions={}
            )

            return scrapy.Request(next_version[0], callback=self.parse_download_link_page, meta=data, priority=30)

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
            return Result(meta=data['meta'], versions=data['versions'])

        next_version = data['remaining'].pop()
        data['cur'] = next_version

        return scrapy.Request(next_version[0], callback=self.parse_download_link_page, meta=data, priority=50)
