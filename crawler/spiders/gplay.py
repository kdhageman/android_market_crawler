import re
from random import choice

import numpy as np
import scrapy

from crawler.item import Meta
from crawler.spiders.util import PackageListSpider, normalize_rating
from gplaycrawler.playcrawler.googleplayapi.googleplay import GooglePlayAPI

pkg_pattern = "https://play.google.com/store/apps/details\?id=(.*)"


def parse_details(details):
    """
    Parse the details from the Google Play api
    Args:
        details: dict
    """
    docv2 = details.get("docV2", {})
    url = docv2.get("shareUrl", "")
    pkg_name = docv2.get("docid", "")
    app_name = docv2.get("title", "")
    creator = docv2.get("creator", "")
    description = docv2.get("descriptionHtml", "")
    available = docv2.get("availability", {}).get("restriction", 0) == 1
    user_rating = docv2.get("aggregateRating", {}).get("starRating", 0)
    user_rating = normalize_rating(user_rating, 5)

    ad = docv2.get("details", {}).get("appDetails", {})
    developer_name = ad.get("developerName", "")
    developer_email = ad.get("developerEmail", "")
    developer_website = ad.get("developerWebsite", "")
    downloads = ad.get("numDownloads", "")

    ann = docv2.get("annotations", {})
    privacy_policy_url = ann.get("privacyPolicyUrl", "")
    contains_ads = "contains ads" in str(ann.get("badgeForDoc", "")).lower()

    offer = str(docv2.get("offer", ""))
    m = re.search('currencyCode: "(.*)"', offer)
    currency = m[1] if m else ""
    m = re.search('formattedAmount: "(.*)"', offer)
    price = m[1] if m else ""

    meta = dict(
        url=url,
        pkg_name=pkg_name,
        app_name=app_name,
        creator=creator,
        description=description,
        available=available,
        user_rating=user_rating,
        developer_name=developer_name,
        developer_email=developer_email,
        developer_website=developer_website,
        downloads=downloads,
        privacy_policy_url=privacy_policy_url,
        contains_ads=contains_ads,
        currency=currency,
        price=price
    )

    version_code = ad.get("versionCode", "")
    version_string = ad.get("versionString", "")
    version_date = ad.get("uploadDate")

    versions = {
        version_string: {
            "timestamp": version_date,
            "code": version_code
        }
    }
    return meta, versions


class GooglePlaySpider(PackageListSpider):
    """
    This Spider returns spider.tem.PackageName instead of meta data and versions
    """

    name = "googleplay_spider"

    def __init__(self, crawler, lang="", android_id="", accounts=[]):
        super().__init__(crawler=crawler, settings=crawler.settings)
        self.apis = []
        for account in accounts:
            email = account.get("email", "")
            password = account.get("password", "")
            if email and password:
                api = GooglePlayAPI(androidId=android_id, lang=lang)
                api.login(email, password)
                self.apis.append(api)
        if len(self.apis) == 0:
            raise Exception("cannot crawl Google Play without valid user accounts")

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler, **crawler.settings.get("GPLAY_PARAMS"))

    def start_requests(self):
        for req in super().start_requests():
            yield req
        yield scrapy.Request('https://play.google.com/store/apps', self.parse)

    def url_by_package(self, pkg):
        return f"https://play.google.com/store/apps/details?id={pkg}"

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps

        Args:
            response: scrapy.Response
        """
        # find all links to packages on the overview page
        # pkgs = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # follow 'See more' buttons on the home page
        see_more_links = response.xpath("//a[text() = 'See more']//@href").getall()
        for link in see_more_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_similar_apps)

        # follow categories on the home page
        category_links = response.css("#action-dropdown-children-Categories a::attr(href)").getall()
        for link in category_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse)

        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Parses the page of a single package
        Example URL: https://play.google.com/store/apps/details?id=com.mi.android.globalminusscreen

        Args:
            response:
        """

        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

        # package name
        m = re.search(pkg_pattern, response.url)
        if m:
            pkg = m.group(1)
            api = choice(self.apis)
            details = api.toDict(api.details(pkg))
            meta, versions = parse_details(details)

            version_code = list(versions.values())[0]['code']
            if version_code:
                # apk = api.download(pkg, version_code)
                # TODO: store apk

                # TODO: move to pipeline
                privacy_policy_url = meta['privacy_policy_url']
                developer_website = meta["developer_website"]
                if privacy_policy_url:
                    # download privacy policy
                    yield scrapy.Request(privacy_policy_url, callback=self.parse_privacy_policy, priority=1000,
                                         meta=dict(meta=meta, versions=versions))
                elif developer_website:
                    # downloads ads.txt
                    ads_url = f"{developer_website}/ads.txt"
                    return scrapy.Request(ads_url, callback=self.parse_ads_txt, priority=1001, meta=meta)
                else:
                    return Meta(meta=meta, versions=versions)
            else:
                self.logger.warn(f"failed to find 'version_code' for {pkg}")

        # similar apps
        similar_link = response.xpath("//a[contains(@aria-label, 'Similar')]//@href").get()
        if similar_link:
            full_url = response.urljoin(similar_link)
            yield scrapy.Request(full_url, callback=self.parse_similar_apps)

    def parse_privacy_policy(self, response):
        privacy_policy_html = response.body.decode("utf-8")
        meta = response.meta
        meta['meta']['privacy_policy_html'] = privacy_policy_html

        developer_website = meta['meta']["developer_website"]
        if developer_website:
            ads_url = f"{developer_website}/ads.txt"
            return scrapy.Request(ads_url, callback=self.parse_ads_txt, priority=1001, meta=meta)
        return Meta(meta=meta['meta'], versions=meta['versions'])

    def parse_ads_txt(self, response):
        meta = response.meta
        meta['meta']['ads_txt'] = response.body.decode("utf-8")
        return Meta(meta=meta['meta'], versions=meta['versions'])

    def parse_similar_apps(self, response):
        """
        Parses a page of similar apps
        Example URL: https://play.google.com/store/apps/collection/cluster?clp=ogouCBEqAggIMiYKIGNvbS5taS5hbmRyb2lkLmdsb2JhbG1pbnVzc2NyZWVuEAEYAw%3D%3D:S:ANO1ljJT8p0&gsr=CjGiCi4IESoCCAgyJgogY29tLm1pLmFuZHJvaWQuZ2xvYmFsbWludXNzY3JlZW4QARgD:S:ANO1ljK6BA8

        Args:
            response:
        """
        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)
