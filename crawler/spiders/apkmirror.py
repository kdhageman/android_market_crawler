import scrapy
import re

from crawler.item import Result
from crawler.spiders.util import normalize_rating

dl_link_pattern = "\/wp-content\/themes\/APKMirror\/download\.php\?id=(.*)"

# TODO: deal with ordered requests (https://stackoverflow.com/a/16177544/12096194, https://stackoverflow.com/questions/54138758/scrapy-python-getting-items-from-yield-requests/54140461)
class ApkMirrorSpider(scrapy.Spider):
    name = "apkmirror_spider"

    def start_requests(self):
        yield scrapy.Request('https://www.apkmirror.com/', callback=self.parse)

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps

        Args:
            response: scrapy.Response

        Returns:
        """
        res = []
        # links to packages
        for link in response.css("a.fontBlack::attr(href)").getall():
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            req = scrapy.Request(next_page, callback=self.parse_pkg_page)  # add URL to set of URLs to crawl
            res.append(req)

        # follow pagination
        a_to_next = response.css("a.nextpostslink::attr(href)").get()
        if a_to_next:
            next_page = response.urljoin(a_to_next)
            req = scrapy.Request(next_page, callback=self.parse)  # add URL to set of URLs to crawl
            res.append(req)

        return res

    def parse_pkg_page(self, response):
        """
        Parses page of a specific package
        Example URL: https://www.apkmirror.com/apk/bgnmobi/dns-changer-no-root-3g-wifi/dns-changer-no-root-3g-wifi-1136r-release/

        Args:
            response:
        """
        res = []
        # download a single variant
        variant_link = response.css("div.table.variants-table a::attr(href)").get() # get the first variants link, we don't care about the various variants
        if variant_link:
            full_link = response.urljoin(variant_link)
            # give higher priority to package download pages
            req = scrapy.Request(full_link, callback=self.parse_download_page, priority=1)
            res.append(req)

        list_of_other_versions = response.xpath("//div[@class='listWidget' and .//div[@class='widgetHeader' and (contains(text(), 'All Releases ') or contains(text(), 'All versions '))]]")

        # find all version links, list with 'All Versions ' or 'All Releases ' header
        for version_link in list_of_other_versions.xpath(".//div[@class='appRow']//a[@class='fontBlack']//@href").getall():
            full_link = response.urljoin(version_link)
            req = scrapy.Request(full_link, callback=self.parse_versions_page)
            res.append(req)

        # find 'more versions' link
        versions_page = list_of_other_versions.xpath(".//div[contains(@class, 'center')]//@href").get()
        if versions_page:
            full_link = response.urljoin(versions_page)
            req = scrapy.Request(full_link, callback=self.parse_versions_page)
            res.append(req)

        return res

    def parse_download_page(self, response):
        """
        Parses the page with an app's download link
        Example URL: https://www.apkmirror.com/apk/bgnmobi/dns-changer-no-root-3g-wifi/dns-changer-no-root-3g-wifi-1136r-release/dns-changer-no-root-3g-wifi-1136r-android-apk-download/

        Args:
            response: scrapy.Response
        """
        # meta data
        meta = dict(
            url=response.url
        )

        header = response.css("div.site-header-contents")

        meta['developer_name'] = header.css("h3 a::text").get()
        meta['app_name'] = header.css("h1::text").get()
        meta['app_description'] = "\n".join(response.css("#description.tab-pane div.notes *::text").getall()).strip()

        appspecs = response.css("#file div.appspec-row div.appspec-value")
        m = appspecs.css("::text").re("Package: (.*)")
        if m:
            meta["pkg_name"] = m[0]

        m = appspecs.css("::text").re(" by (.*)")
        if m:
            meta['uploader'] = m[0]

        m = appspecs.css("::text").re("(.*) downloads?")
        if m:
            meta['downloads'] = m[0]

        m = response.xpath("//div[@itemprop = 'aggregateRating']/span[1]/span[1]//@title").re("(.*) / 5.0")
        if m:
            user_rating = m[0]
            meta['user_rating'] = normalize_rating(user_rating, 5)

        category = response.css("a.play-category::text").get()
        meta['categories'] = [category]

        icon_url_rel = response.css("div.siteTitleBar img::attr(src)").get()
        meta['icon_url'] = response.urljoin(icon_url_rel)

        # find download link
        versions = dict()
        date = appspecs[-1].css("span::text").get()
        m = appspecs[0].css("::text")[0].re("Version: (.*)")
        version = m[0] if m else "undefined"
        dl_link = response.css("a.downloadButton::attr(href)").get()
        dl_link_full = response.urljoin(dl_link)

        versions[version] = dict(
            timestamp=date,
            download_url=dl_link_full
        )

        res = []

        if re.search(dl_link_pattern, dl_link):
            # in case this regex matches, the actual download link has been found
            # otherwise, we must visit another nested download page first, before yielding the Meta response
            res.append(Result(
                meta=meta,
                versions=versions
            ))
        else:
            req = response.follow(dl_link, callback=self.download_url_from_button, meta=dict(meta=meta, versions=versions))
            res.append(req)

        return res

    def download_url_from_button(self, response):
        """
        Obtains the true download URL from the button on the page
        Args:
            response:

        Returns:

        """
        meta = response.meta['meta']
        versions = response.meta['versions']

        dl_url = response.xpath("//a[@rel = 'nofollow']/@href").get()
        for version, d in versions.items():
            if d['download_url'] == response.url:
                d['download_url'] = response.urljoin(dl_url)
                versions[version] = d
                break

        return Result(
            meta=meta,
            versions=versions
        )

    def parse_versions_page(self, response):
        """
        Parses the paginated page of version of a package, yielding requests to package pages
        Example URL: https://www.apkmirror.com/uploads/?q=dns-changer-no-root-3g-wifi

        Args:
            response: scrapy.Response
        """
        res = []
        # visit package page for all different versions
        for pkg_link in response.css("#primary h5.appRowTitle a::attr(href)").getall():
            full_link = response.urljoin(pkg_link)
            req = scrapy.Request(full_link, callback=self.parse_pkg_page)
            res.append(req)

        # pagination of versions page
        next_page_link = response.css("a.nextpostslink::attr(href)").get()
        if next_page_link:
            full_link = response.urljoin(next_page_link)
            req = scrapy.Request(full_link, callback=self.parse_versions_page)
            res.append(req)

        return res
