import scrapy
import re

from pystorecrawler.item import Meta

pkg_pattern = "http://app\.mi\.com/details\?id=(.*)"


class MiSpider(scrapy.Spider):
    name = "mi_spider"
    start_urls = ['http://app.mi.com/']

    def parse(self, response):
        """
        Crawls the homepage for apps
        Example URL: http://app.mi.com/

        Args:
            response: scrapy.Response
        """
        # links to package pages

        pkg_links = []
        # recommended + popular
        for link in response.css("div.applist-wrap").css("ul.applist").css("h5").css("a::attr(href)").getall():
            full_url = response.urljoin(link)
            pkg_links.append(full_url)

        # rankings
        for link in response.css("#J-accordion").css("li").css("a.ranklist-img::attr(href)").getall():
            full_url = response.urljoin(link)
            pkg_links.append(full_url)

        # TODO: by category

        # crawl the found package pages
        for link in pkg_links:
            yield scrapy.Request(link, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        Example URL: http://app.mi.com/details?id=com.tencent.tmgp.jx3m

        details preventDefault

        Args:
            response: scrapy.Response
        """
        meta = dict()

        m = re.search(pkg_pattern, response.url)
        if m:
            meta["pkg_name"] = m.group(1)

        intro_titles = response.css("div.app-info").css("div.intro-titles")
        meta["app_name"] = intro_titles.css("h3::text").get()
        meta["developer_name"] = intro_titles.css("p::text").get()
        app_text = response.css("div.app-text")
        meta["app_description"] = "\n".join(app_text.css("p")[0].css("::text").getall())

        # find download link
        versions=dict()
        details = response.css("div.details ul.cf li:not(.weight-font)::text").getall()
        version, date = details[1:3]
        dl_link = response.css("a.download::attr(href)").get()
        full_url = response.urljoin(dl_link)

        versions[version] = dict(
            timestamp=date,
            download_url=full_url
        )

        # links to package pages
        for link in response.css("div.second-imgbox").css("h5").css("a::attr(href)").getall():
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

        res = Meta(
            meta=meta,
            versions=versions
        )

        yield res
