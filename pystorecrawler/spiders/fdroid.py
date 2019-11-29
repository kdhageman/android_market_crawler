import scrapy
import re

from pystorecrawler.item import Meta

pkg_pattern = "https://f-droid\.org/en/packages/(.*)/"


class FDroidSpider(scrapy.Spider):
    name = "fdroid_spider"
    start_urls = ['https://f-droid.org/en/packages/']

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps
        Example URL: https://f-droid.org/en/packages/

        Args:
            response: scrapy.Response
        """
        # follow pagination
        a_to_next = response.css("li.nav.next").css("a")
        if "href" in a_to_next.attrib:
            next_page = response.urljoin(a_to_next.attrib["href"])
            yield scrapy.Request(next_page, callback=self.parse)  # add URL to set of URLs to crawl

        # links to packages
        for link in response.css("a.package-header::attr(href)").getall():
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            yield scrapy.Request(next_page, callback=self.parse_pkg_page)  # add URL to set of URLs to crawl

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        Example URL: https://f-droid.org/en/packages/com.oF2pks.kalturadeviceinfos/

        Args:
            response: scrapy.Response
        """
        meta = dict(
            url=response.url
        )
        meta['app_name'] = response.css("h3.package-name::text").get().strip()
        meta['app_summary'] = response.css("div.package-summary::text").get().strip()
        meta['app_description'] = "\n".join(response.css("div.package-description::text").getall())
        meta['icon_url'] = response.css("img.package-icon::attr(src)").get()

        m = re.search(pkg_pattern, response.url)
        if m:
            meta['pkg_name'] = m.group(1)

        versions = dict()

        package_versions = response.css("li.package-version")
        for pv in package_versions:
            version = pv.css("div.package-version-header a::attr(name)").get()
            added_on = pv.css("div.package-version-header::text")[3].re(".*Added on (.*)")
            dl_link = pv.css("p.package-version-download b a::attr(href)").get()

            versions[version] = dict(
                timestamp=added_on[0] if added_on else '',
                download_url=dl_link
            )

        res = Meta(
            meta=meta,
            versions=versions
        )

        yield res
