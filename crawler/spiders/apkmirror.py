import scrapy
from scrapy.exceptions import CloseSpider
from scrapy_splash import SplashRequest

from crawler.spiders.util import normalize_rating

dl_link_pattern = "\/wp-content\/themes\/APKMirror\/download\.php\?id=(.*)"


class ApkMirrorSpider(scrapy.Spider):
    name = "apkmirror_spider"

    def __init__(self, crawler, start_page=1):
        super().__init__(crawler=crawler, settings=crawler.settings)
        splash_url = crawler.settings.get("SPLASH_URL", None)
        if not splash_url:
            raise CloseSpider("Must provide Splash URL for this spider")
        self.start_page = start_page

    @classmethod
    def from_crawler(cls, crawler):
        apkmirror_params = crawler.settings.get("APKMIRROR_PARAMS", {})
        start_page = apkmirror_params.get('start_page', 1)
        return cls(crawler, start_page)

    def start_requests(self):
        pages = 8813  # can be changed manually
        for page_nr in range(self.start_page, pages):
            url = f"https://www.apkmirror.com/uploads/page/{page_nr}/"
            self.logger.debug(f"scheduled new pagination page: {url}")
            yield SplashRequest(url, callback=self.parse, args={
                'wait': 1,
            })

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
            self.logger.debug(f"scheduled new package page: {link}")
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            req = SplashRequest(next_page, callback=self.parse_pkg_page, priority=1, args={
                'wait': 1,
            })  # add URL to set of URLs to crawl
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
        variant_link = response.css(
            "div.table.variants-table a::attr(href)").get()  # get the first variants link, we don't care about the various variants
        if variant_link:
            full_link = response.urljoin(variant_link)
            # give higher priority to package download pages
            self.logger.debug(f"scheduled new variant page: {variant_link}")
            req = SplashRequest(full_link, callback=self.parse_variant_page, priority=2, args={
                'wait': 1,
            })
            res.append(req)

        # khageman 01-10-2021: disable downloading any versions

        # list_of_other_versions = response.xpath("//div[@class='listWidget' and .//div[@class='widgetHeader' and (contains(text(), 'All Releases ') or contains(text(), 'All versions '))]]")
        #
        # # find all version links, list with 'All Versions ' or 'All Releases ' header
        # for version_link in list_of_other_versions.xpath(".//div[@class='appRow']//a[@class='fontBlack']//@href").getall():
        #     full_link = response.urljoin(version_link)
        #     req = scrapy.Request(full_link, callback=self.parse_versions_page)
        #     res.append(req)
        #
        # # find 'more versions' link
        # versions_page = list_of_other_versions.xpath(".//div[contains(@class, 'center')]//@href").get()
        # if versions_page:
        #     full_link = response.urljoin(versions_page)
        #     req = scrapy.Request(full_link, callback=self.parse_versions_page)
        #     res.append(req)

        return res

    def parse_variant_page(self, response):
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

        breadcrumbs = response.css("div.breadcrumbs > a.withoutripple::text").getall()
        try:
            developer_name = breadcrumbs[0]
        except:
            developer_name = "undefined"

        try:
            app_name = breadcrumbs[1]
        except:
            app_name = "undefined"

        try:
            version = breadcrumbs[2]
        except:
            version = "undefined"

        meta['developer_name'] = developer_name
        meta['app_name'] = app_name

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

        date = appspecs[-1].css("span::text").get()

        # find download link
        dl_link = response.css("a.downloadButton::attr(href)").get()
        dl_link_full = response.urljoin(dl_link)

        versions = {
            version: {
                "timestamp": date,
            }
        }

        self.logger.debug(f"scheduled download link: {dl_link}")
        req = SplashRequest(dl_link_full, callback=self.download_url_from_button, priority=10,
                            meta=dict(meta=meta, versions=versions), args={
                'wait': 1,
            })
        return req

    def download_url_from_button(self, response):
        """
        Obtains the true download URL from the button on the page
        Example URL: https://www.apkmirror.com/apk/ee/my-ee/my-ee-4-58-0-release/my-ee-4-58-0-android-apk-download/download/
        Args:
            response:

        Returns:

        """
        meta = response.meta['meta']
        versions = response.meta['versions']

        dl_path = response.css("a[rel='nofollow'][data-google-vignette=false]::attr('href')").get()
        dl_url = response.urljoin(dl_path)

        for version in versions.keys():
            versions[version]['download_url'] = dl_url
            break

        return dict(
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
            req = SplashRequest(full_link, callback=self.parse_pkg_page, args={
                'wait': 1,
            })
            res.append(req)

        # pagination of versions page
        next_page_link = response.css("a.nextpostslink::attr(href)").get()
        if next_page_link:
            full_link = response.urljoin(next_page_link)
            req = SplashRequest(full_link, callback=self.parse_versions_page, args={
                'wait': 1,
            })
            res.append(req)

        return res
