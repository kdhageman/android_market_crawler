import re

import scrapy

dl_pattern = "zhytools.downloadApp\((.*)\);"


class HuaweiSpider(scrapy.Spider):
    name = "huawei_spider"
    start_urls = ['https://appstore.huawei.com/']

    def parse(self, response):
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
        # meta data
        meta = dict()

        app_info = response.css("ul.app-info-ul")
        meta["app_name"] = app_info[0].css("span.title::text").get()

        more_info = app_info[1].css("li.ul-li-detail > span::text").getall()
        meta["date"] = more_info[1]
        meta["developer_name"] = more_info[2]
        meta["version"] = more_info[3]

        app_description = "\n".join(response.css("#app_strdesc::text").getall()) + "\n"
        app_description += "\n".join(response.css("#app_desc::text").getall())
        meta["app_description"] = app_description

        response.css("#app_desc::text").getall()
        res = dict(
            meta=meta,
            download_urls=[]
        )
        # sidebar on the right
        for pkg_link in response.css("div.unit.nofloat.corner")[1].css("a::attr(href)").getall():
            full_url = response.urljoin(pkg_link)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

        # download link
        onclick = response.css("a.mkapp-btn::attr(onclick)").get()
        m = re.search(dl_pattern, onclick)
        if m:
            dl_link = m.group(1).split(",")[5]  # the download link is thee 6-th parameter of the js function
            res['download_urls'].append(dl_link)  # link is absolute already

        return res
