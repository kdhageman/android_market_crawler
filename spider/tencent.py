import re

import scrapy

pkg_pattern = "https://android\.myapp\.com/myapp/detail\.htm\?apkName=(.*)"


class TencentSpider(scrapy.Spider):
    name = "tencent_spider"
    start_urls = ['https://android.myapp.com/']

    def parse(self, response):
        # find links to other apps
        for link in response. \
                css("a::attr(href)"). \
                re("../myapp/detail.htm\?apkName=.*"):
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            yield scrapy.Request(next_page, callback=self.parge_pkg_page)  # add URL to set of URLs to crawl

    def parge_pkg_page(self, response):
        # find meta data
        meta = dict(
            pkg_name="",
            app_name="",
            app_description="",
            version="",
            publish_time="",
            developer_name=""
        )

        divs = response.css("div.det-othinfo-container").css("div.det-othinfo-data")

        if len(divs) == 4:
            meta['version'] = divs[0].css("::text").get()
            meta['publish_time'] = divs[1].attrib['data-apkpublishtime']
            meta['developer_name'] = divs[2].css("::text").get()
        else:
            print("failed to find part of metadata")

        meta['app_name'] = response.css("div.det-name-int::text").get()
        meta['app_description'] = response.css("div.det-app-data-info::text").get()

        m = re.search(pkg_pattern, response.url)
        if m:
            meta['pkg_name'] = m.group(1)

        res = dict(
            meta=meta,
            download_urls=[]
        )

        # find download button(s)
        for dl_link in response.css("a::attr(data-apkurl)").getall():
            res["download_urls"].append(dl_link)

        return res
