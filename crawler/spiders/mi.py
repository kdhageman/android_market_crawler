import scrapy
import re

from crawler.spiders.util import normalize_rating, PackageListSpider

pkg_pattern = "http://app\.mi\.com/details\?id=(.*)"


class MiSpider(PackageListSpider):
    name = "mi_spider"

    def __init__(self, crawler):
        super().__init__(crawler=crawler, settings=crawler.settings)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def start_requests(self):
        for req in super().start_requests():
            yield req

    def base_requests(self, meta={}):
        return [scrapy.Request('http://app.mi.com/', callback=self.parse, meta=meta)]

    def url_by_package(self, pkg):
        return f"http://app.mi.com/details?id={pkg}"

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

        res = []
        # crawl the found package pages
        for link in pkg_links:
            req = scrapy.Request(link, callback=self.parse_pkg_page)
            res.append(req)

        return res

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        Example URL: http://app.mi.com/details?id=com.tencent.tmgp.jx3m

        Args:
            response: scrapy.Response
        """
        meta = dict(
            url=response.url
        )

        intro_titles = response.css("div.app-info").css("div.intro-titles")
        meta["app_name"] = intro_titles.css("h3::text").get().strip()
        meta["developer_name"] = response.css("div.container.cf .float-right div[style*='float:right']::text")[1].get().strip()
        app_text = response.css("div.app-text")
        meta["app_description"] = "\n".join(app_text.css("p")[0].css("::text").getall()).strip()
        user_rating_css_class = response.css("div.star1-empty > div::attr(class)").re("star1-hover (.*)")[0]
        user_rating = get_rating_from_css_class(user_rating_css_class)
        meta["user_rating"] = user_rating

        category = response.css("div.intro-titles p.special-font.action::text").get()
        meta['categories'] = [category]

        meta['icon_url'] = response.css("img.yellow-flower::attr(src)").get()

        # find download link
        versions=dict()
        details = response.css("div.container.cf .float-left div[style*='float:right']::text").getall()
        version, date, pkg_name = [e.strip() for e in details[1:4]]
        dl_link = response.css("a.download::attr(href)").get()
        full_url = response.urljoin(dl_link) if dl_link != 'javascript:void(0)' else None

        meta["pkg_name"] = pkg_name

        versions[version] = dict(
            timestamp=date,
            download_url=full_url
        )

        res = [dict(
            meta=meta,
            versions=versions
        )]

        # links to package pages
        for link in response.css("div.second-imgbox").css("h5").css("a::attr(href)").getall():
            full_url = response.urljoin(link)
            req = scrapy.Request(full_url, callback=self.parse_pkg_page)
            res.append(req)

        return res

def get_rating_from_css_class(css_class):
    """
    Parses the CSS class that contains the rating.
    If the class is empty, the rating is 0, otherwise, it follows the following naming convention:
        star1-{rating between 1 and 10}

    Args: str
        css_class: name of CSS class

    Returns: int
        rating between 0 and 100
    """
    if not css_class:
        return 0

    m = re.search("star1-(.*)", css_class)
    if m:
        rating = m.group(1)
        rating = normalize_rating(rating, 10)
        rating = min(rating, 100)
        return rating
    return "invalid"