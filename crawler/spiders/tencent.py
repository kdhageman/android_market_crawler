import urllib
import scrapy

from crawler.spiders.util import normalize_rating, PackageListSpider


class TencentSpider(PackageListSpider):
    name = "tencent_spider"

    def __init__(self, crawler):
        super().__init__(crawler=crawler, settings=crawler.settings)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def start_requests(self):
        for req in super().start_requests():
            yield req

    def base_requests(self, meta={}):
        return [scrapy.Request('https://android.myapp.com/', callback=self.parse)]

    def url_by_package(self, pkg):
        return f"https://android.myapp.com/myapp/detail.htm?apkName={pkg}"

    def parse(self, response):
        """
        Parses the front page for packages
        Example URL: https://android.myapp.com/

        Args:
            response: scrapy.Response
        """
        res = []
        # find links to other apps
        for link in response.css("a::attr(href)").re("../myapp/detail.htm\?apkName=.+"):
            self.logger.debug(f"scheduled new package page: {link}")
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            req = scrapy.Request(next_page, callback=self.parse_pkg_page)  # add URL to set of URLs to crawl
            res.append(req)
        return res

    def parse_pkg_page(self, response):
        """
        Parses the page of a single package
        Example URL: https://android.myapp.com/myapp/detail.htm?apkName=ctrip.android.view

        Args:
            response: scrapy.Response
        """

        if response.css("div.search-none-img") or response.url == 'https://a.app.qq.com/error_pages/noApp.jsp':
            # not found page
            return

        res = []

        # add related apps
        related_app_urls = response.css("a.appName::attr(href)").getall()
        for path in related_app_urls:
            self.logger.debug(f"scheduled new package page: {path}")
            url = response.urljoin(path)
            req = scrapy.Request(url, callback=self.parse_pkg_page)
            res.append(req)

        # find meta data
        meta = {
            'url': response.url
        }

        divs = response.css("div.det-othinfo-container div.det-othinfo-data")

        meta['developer_name'] = divs[2].css("::text").get()
        meta['app_name'] = response.css("div.det-name-int::text").get()
        meta['app_description'] = response.css("div.det-app-data-info::text").get()

        qs = urllib.parse.urlparse(response.url).query
        query_params = urllib.parse.parse_qs(qs)
        meta['pkg_name'] = query_params.get("apkName", [""])[0]

        user_rating = response.css("div.com-blue-star-num::text").re("(.*)分")[0]
        meta['user_rating'] = normalize_rating(user_rating, 5)
        meta['downloads'] = response.css("div.det-insnum-line div.det-ins-num::text").get()

        category = response.css("#J_DetCate::text").get()
        meta['categories'] = [category]
        meta['icon_url'] = response.css("div.det-icon img::attr(src)").get()

        # find download button(s)
        versions = dict()
        version = divs[0].css("::text").get()
        dl_link = response.css("a::attr(data-apkurl)").get()
        date = divs[1].attrib['data-apkpublishtime']  # as unix timestamp

        versions[version] = dict(
            timestamp=date,
            download_url=dl_link
        )

        res.append({
            'meta': meta,
            'versions': versions,
        })
        return res
