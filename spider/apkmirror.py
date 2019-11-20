import scrapy
import re

pkg_pattern = "https://f-droid\.org/en/packages/(.*)/"


class ApkMirrorSpider(scrapy.Spider):
    name = "apkmirror_spider"
    start_urls = ['https://www.apkmirror.com/']

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps
        :param response:
        :return:
        """
        # follow pagination
        a_to_next = response.css("a.nextpostslink::attr(href)").get()
        if a_to_next:
            next_page = response.urljoin(a_to_next)
            yield scrapy.Request(next_page, callback=self.parse)  # add URL to set of URLs to crawl

        # links to packages
        for link in response.css("a.fontBlack::attr(href)").getall():
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            yield scrapy.Request(next_page, callback=self.parge_pkg_page)  # add URL to set of URLs to crawl

    def parge_pkg_page(self, response):
        print(response.url)

        header = response.css("div.site-header-contents")

        developer_name = header.css("h3").css("a::text").get()
        app_name = header.css("h1::text").get()
        app_description = "\n".join(response.css("#description").css("div.notes::text").getall()).strip()

        res = dict(
            meta=dict(
                developer_name=developer_name,
                app_name=app_name,
                app_description=app_description
            ),
            download_urls=[],
        )

        # TODO: find all download links for all version for this package

        return res
