import re

import scrapy

from spider.item import Meta

dl_pattern = "zhytools.downloadApp\((.*)\);"
id_pattern = "https://appstore\.huawei\.com/app/(.*)"


class HuaweiSpider(scrapy.Spider):
    name = "huawei_spider"
    start_urls = ['https://appstore.huawei.com/']

    def parse(self, response):
        """
        Parses the front page
        Example URL: https://appstore.huawei.com/

        Args:
           response: scrapy.Response
        """
        # find links to packages
        pkg_links = []

        # recommended
        for pkg_link in response.css("#recommendAppList * li.app-ico > a::attr(href)").getall():
            pkg_links.append(pkg_link)

        # others
        for pkg_link in response.css("div.unit-tri * div.app-sweatch * div.open-ico > a::attr(href)").getall():
            pkg_links.append(pkg_link)

        for pkg_link in pkg_links:
            full_url = response.urljoin(pkg_link)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Parses the page of a package
        Example URL:

        Args:
            response: scrapy.Response
        """
        # meta data
        meta = dict()

        app_info = response.css("ul.app-info-ul")
        meta["app_name"] = app_info[0].css("span.title::text").get()

        more_info = app_info[1].css("li.ul-li-detail > span::text").getall()
        meta["developer_name"] = more_info[2]

        m = re.search(id_pattern, response.url)
        if m:
            meta['id'] = m.group(1)

        app_description = "\n".join(response.css("#app_strdesc::text").getall()) + "\n"
        app_description += "\n".join(response.css("#app_desc::text").getall())
        meta["app_description"] = app_description

        # download link
        versions=dict()

        jsparams = response.css("a.mkapp-btn::attr(onclick)").re(dl_pattern)
        dl_link = jsparams[0].split(",")[5].strip(" '")  # the download link is the 6-th parameter of the js function
        date = more_info[1]
        version = more_info[3]
        versions[version] = dict(
            date=date,
            dl_link=dl_link
        )

        res = Meta(
            meta=meta,
            versions=versions
        )

        # sidebar on the right
        for pkg_link in response.css("div.unit.nofloat.corner")[1].css("a::attr(href)").getall():
            full_url = response.urljoin(pkg_link)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

        yield res
