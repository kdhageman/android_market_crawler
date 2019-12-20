import os
import re
import sys
import time
from random import choice

import numpy as np
import scrapy
from sentry_sdk import capture_exception

from crawler.item import Meta
from crawler.util import market_from_spider, sha256, random_proxy
from crawler.spiders.util import PackageListSpider, normalize_rating
sys.path.append("./gplaycrawler/playcrawler")
sys.path.append("./gplaycrawler/playcrawler/googleplayapi")
from googleplayapi.googleplay import GooglePlayAPI

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

    def __init__(self, crawler, outdir, proxies=[], interval=1, lang="", android_id="", accounts=[]):
        super().__init__(crawler=crawler, settings=crawler.settings)
        self.apis = []
        for account in accounts:
            email = account.get("email", "")
            password = account.get("password", "")
            if email and password:
                p = random_proxy()
                api = GooglePlayAPI(androidId=android_id, lang=lang, proxies=p)
                api.login(email, password)
                self.apis.append(api)
        if len(self.apis) == 0:
            raise Exception("cannot crawl Google Play without valid user accounts")
        self.outdir = outdir
        self.interval = interval

    @classmethod
    def from_crawler(cls, crawler):
        outdir = crawler.settings.get("CRAWL_ROOTDIR", "/tmp/crawl")
        proxies = crawler.settings.get("HTTP_PROXIES", [])
        return cls(crawler, outdir, proxies, **crawler.settings.get("GPLAY_PARAMS"))

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

            for version, dat in versions.items():
                version_code = dat['code']
                if version_code:
                    try:
                        apk = api.download(pkg, version_code)
                    except Exception as e:
                        # unreliable api, so catch ANY exception
                        capture_exception(e)
                    self.pause(self.interval)

                    market = market_from_spider(self)
                    fpath = os.path.join(self.outdir, market, meta['pkg_name'], f"{version}.apk")

                    os.makedirs(os.path.dirname(fpath), exist_ok=True)  # ensure directories exist

                    # TODO: parse APK
                    with open(fpath, "wb") as f:
                        f.write(apk)
                    with open(fpath, "rb") as f:
                        dat['file_sha256'] = sha256(f)
                    dat['file_size'] = len(apk)
                    dat['file_path'] = fpath
                    versions[version] = dat
                else:
                    self.logger.warn(f"failed to find 'version_code' for {pkg}")
            yield Meta(meta=meta, versions=versions)

        # similar apps
        similar_link = response.xpath("//a[contains(@aria-label, 'Similar')]//@href").get()
        if similar_link:
            full_url = response.urljoin(similar_link)
            yield scrapy.Request(full_url, callback=self.parse_similar_apps)

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

    def pause(self, t):
        """
        Pause the crawler for t seconds
        Args:
            t: int
                number of seconds to pause crawler
        """
        if t:
            self.crawler.engine.pause()
            time.sleep(t)
            self.crawler.engine.unpause()
