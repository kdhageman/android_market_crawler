import scrapy

from pystorecrawler.item import Meta

pkg_pattern = "https://f-droid\.org/en/packages/(.*)/"

# TODO: deal with ordered requests (https://stackoverflow.com/a/16177544/12096194)

class ApkMirrorSpider(scrapy.Spider):
    name = "apkmirror_spider"
    start_urls = ['https://www.apkmirror.com/']

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps

        Args:
            response: scrapy.Response

        Returns:
        """
        # links to packages
        for link in response.css("a.fontBlack::attr(href)").getall():
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            yield scrapy.Request(next_page, callback=self.parse_pkg_page)  # add URL to set of URLs to crawl

        # follow pagination
        a_to_next = response.css("a.nextpostslink::attr(href)").get()
        if a_to_next:
            next_page = response.urljoin(a_to_next)
            yield scrapy.Request(next_page, callback=self.parse)  # add URL to set of URLs to crawl

    def parse_pkg_page(self, response):
        """
        Parses page of a specific package
        Example URL: https://www.apkmirror.com/apk/bgnmobi/dns-changer-no-root-3g-wifi/dns-changer-no-root-3g-wifi-1136r-release/

        Args:
            response:
        """
        # download a single variant
        list_widgets = response.css("#content div.listWidget,#primary div.listWidget")
        variant_link = list_widgets[0].css("div.table a::attr(href)").get()  # get the first variants link, we don't care about the various variants
        if variant_link:
            full_link = response.urljoin(variant_link)
            # give higher priority to package download pages
            yield scrapy.Request(full_link, callback=self.parse_download_page, priority=1)

        # find all version links, list with 'All Versions ' or 'All Releases ' header
        list_of_other_versions = response.xpath("//div[@class='listWidget' and .//div[@class='widgetHeader' and (contains(text(), 'All Releases ') or contains(text(), 'All versions '))]]")
        for version_link in list_of_other_versions.xpath(".//div[@class='appRow']//a[@class='fontBlack']//@href").getall():
            full_link = response.urljoin(version_link)
            yield scrapy.Request(full_link, callback=self.parse_versions_page)

        # find 'more versions' link
        versions_page = list_of_other_versions.xpath(".//div[contains(@class, 'center')]//@href").get()
        if versions_page:
            full_link = response.urljoin(versions_page)
            yield scrapy.Request(full_link, callback=self.parse_versions_page)

    def parse_download_page(self, response):
        """
        Parses the page with an app's download link
        Example URL: https://www.apkmirror.com/apk/bgnmobi/dns-changer-no-root-3g-wifi/dns-changer-no-root-3g-wifi-1136r-release/dns-changer-no-root-3g-wifi-1136r-android-apk-download/

        Args:
            response: scrapy.Response
        """
        # meta data
        meta = dict()

        header = response.css("div.site-header-contents")

        meta['developer_name'] = header.css("h3 a::text").get()
        meta['app_name'] = header.css("h1::text").get()
        meta['app_description'] = "\n".join(response.css("#description.tab-pane div.notes *::text").getall()).strip()

        appspecs = response.css("#file div.appspec-row div.appspec-value")
        m = appspecs[0].css("::text")[2].re("Package: (.*)")
        meta["pkg_name"] = m[0] if m else None

        m = appspecs[-1].css("::text").re(" by (.*)")
        meta['uploader'] = m[0] if m else None

        meta['downloads'] = appspecs[0].css("::text")[-1].re("(.*) downloads")[0]

        user_rating = response.xpath("//div[@itemprop = 'aggregateRating']/span[1]/span[1]//@title").re("(.*) / 5.0")[0]
        meta['user_rating'] = normalize_rating(user_rating)

        category = response.css("a.play-category::text").get()
        meta['categories'] = [category]

        icon_url_rel = response.css("div.siteTitleBar img::attr(src)").get()
        meta['icon_url'] = response.urljoin(icon_url_rel)

        # find download link
        versions = dict()
        date = appspecs[-1].css("span::text").get()
        m = appspecs[0].css("::text")[0].re("Version: (.*)")
        version = m[0] if m else "undefined"
        dl = response.css("a.downloadButton::attr(href)").get()
        full_url = response.urljoin(dl)

        versions[version] = dict(
            timestamp=date,
            download_url=full_url
        )

        res = Meta(
            meta=meta,
            versions=versions
        )

        yield res

    def parse_versions_page(self, response):
        """
        Parses the paginated page of version of a package, yielding requests to package pages
        Example URL: https://www.apkmirror.com/uploads/?q=dns-changer-no-root-3g-wifi

        Args:
            response: scrapy.Response
        """
        # visit package page for all different versions
        for pkg_link in response.css("#primary h5.appRowTitle a::attr(href)").getall():
            full_link = response.urljoin(pkg_link)
            yield scrapy.Request(full_link, callback=self.parse_pkg_page)

        # pagination of versions page
        next_page_link = response.css("a.nextpostslink::attr(href)").get()
        if next_page_link:
            full_link = response.urljoin(next_page_link)
            yield scrapy.Request(full_link, callback=self.parse_versions_page)

def normalize_rating(rating):
    """
    Normalizes a (string) rating between 0 and 5 to a float between 0 and 100
    Args:
        rating : str
            between 0 and 5

    Returns: float
        between 0 and 100
    """
    return float(rating) * 20