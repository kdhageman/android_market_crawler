import scrapy
import re

from crawler.item import Result
from crawler.spiders.util import PackageListSpider

pkg_pattern = "https://f-droid\.org/en/packages/(.*)/"


class FDroidSpider(PackageListSpider):
    name = "fdroid_spider"

    def __init__(self, crawler):
        super().__init__(crawler=crawler, settings=crawler.settings)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def start_requests(self):
        for req in super().start_requests():
            yield req

    def base_requests(self, meta={}):
        return [scrapy.Request('https://f-droid.org/en/packages/', callback=self.parse, meta=meta)]

    def url_by_package(self, pkg):
        return f"https://f-droid.org/en/packages/{pkg}/"

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps
        Example URL: https://f-droid.org/en/packages/

        Args:
            response: scrapy.Response
        """
        res = []
        # follow pagination
        a_to_next = response.css("li.nav.next").css("a")
        if "href" in a_to_next.attrib:
            next_page = response.urljoin(a_to_next.attrib["href"])
            req = scrapy.Request(next_page, callback=self.parse)  # add URL to set of URLs to crawl
            res.append(req)

        # links to packages
        for link in response.css("a.package-header::attr(href)").getall():
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            req = scrapy.Request(next_page, callback=self.parse_pkg_page)  # add URL to set of URLs to crawl
            res.append(req)

        return res

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
        icon_url = response.css("img.package-icon::attr(src)").get()
        meta['icon_url'] = response.urljoin(icon_url)

        m = re.search(pkg_pattern, response.url)
        if m:
            meta['pkg_name'] = m.group(1)

        versions = dict()

        # get website
        # TODO: this is ugly, improve!
        developer_website = None
        links = response.css("ul.package-links > .package-link > a")
        for link in links:
            text = link.css("a::text").get()
            if text == 'Website':
                developer_website = link.css("a::attr('href')").get().strip()
        meta['developer_website'] = developer_website

        # get developer name + email address
        developer_name = None
        developer_email = None
        developer_el = response.css("ul.package-links > div.package-link")
        if developer_el:
            matched_emails = developer_el.css("a::attr('href')").re("mailto:(.*)\?")
            if matched_emails:
                developer_email = matched_emails[0].strip()
            developer_texts = developer_el.css("::text").getall()
            if len(developer_texts) == 3:
                developer_name = developer_texts[1].strip()
        meta['developer_email'] = developer_email
        if developer_email != developer_name:
            meta['developer_name'] = developer_name

        package_versions = response.css("li.package-version")
        for pv in package_versions:
            version = pv.css("div.package-version-header a::attr(name)").get()
            added_on = pv.css("div.package-version-header::text")[3].re(".*Added on (.*)")
            dl_link = pv.css("p.package-version-download b a::attr(href)").get()

            versions[version] = dict(
                timestamp=added_on[0] if added_on else '',
                download_url=dl_link
            )

        res = Result(
            meta=meta,
            versions=versions
        )

        return res
