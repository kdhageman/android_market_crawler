import scrapy
import re

pkg_pattern = "https://f-droid\.org/en/packages/(.*)/"


class FDroidSpider(scrapy.Spider):
    name = "fdroid_spider"
    start_urls = ['https://f-droid.org/en/packages/']

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps
        :param response:
        :return:
        """
        # follow pagination
        a_to_next = response.css("li.nav.next").css("a")
        if "href" in a_to_next.attrib:
            next_page = response.urljoin(a_to_next.attrib["href"])
            yield scrapy.Request(next_page, callback=self.parse)  # add URL to set of URLs to crawl

        # links to packages
        for link in response.css("a.package-header::attr(href)").getall():
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            yield scrapy.Request(next_page, callback=self.parge_pkg_page)  # add URL to set of URLs to crawl

    def parge_pkg_page(self, response):
        """
        Crawls the page of a single app
        :param response:
        :return:
        """
        app_name = response.css("h3.package-name::text").get().strip()
        app_summary = response.css("div.package-summary::text").get().strip()
        app_description = "\n".join(response.css("div.package-description::text").getall()).strip()

        pkg_name = "undefined"
        m = re.search(pkg_pattern, response.url)
        if m:
            pkg_name = m.group(1)

        res = dict(
            meta=dict(
                pkg_name=pkg_name,
                app_name=app_name,
                app_summary=app_summary,
                app_description=app_description
            ),
            download_urls=[],
        )

        for dl_link in response.css("p.package-version-download").css("b").css("a::attr(href)").getall():
            res["download_urls"].append(dl_link)

        return res
