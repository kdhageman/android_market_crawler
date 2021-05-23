import re
import time

import gpsoauth
import numpy as np
import requests
import scrapy

from crawler.spiders.util import PackageListSpider, normalize_rating
from protobuf.proto.googleplay_pb2 import ResponseWrapper

pkg_pattern = "https://play.google.com/store/apps/details\?id=(.*)"

_APP_LISTING_PAGE = 'https://play.google.com/store/apps'
_SERVICE = "androidmarket"
_URL_LOGIN = "https://android.clients.google.com/auth"
_ACCOUNT_TYPE_GOOGLE = "GOOGLE"
_ACCOUNT_TYPE_HOSTED = "HOSTED"
_ACCOUNT_TYPE_HOSTED_OR_GOOGLE = "HOSTED_OR_GOOGLE"
_GOOGLE_LOGIN_APP = 'com.android.vending'
_GOOGLE_LOGIN_CLIENT_SIG = '321187995bc7cdc2b5fc91b11a96e2baa8602c62'
_USERAGENT_SEARCH = "Android-Finsky/8.0.0 (api=3,versionCode=8016014,sdk=26,device=sailfish,hardware=sailfish,product=sailfish)"
_USERAGENT_DOWNLOAD = "AndroidDownloadManager/6.0 (Linux; U; Android 8.0.0; Pixel Build/OPR3.170623.013)"
_INCOMPATIBLE_DEVICE_MSG = "Your device is not compatible with this item."


def parse_details(details):
    """
    Parse the details from the Google Play api
    Args:
        details: dict
    """
    docv2 = details.docV2
    url = docv2.shareUrl
    pkg_name = docv2.docid
    app_name = docv2.title
    creator = docv2.creator
    description = docv2.descriptionHtml
    restriction = docv2.availability.restriction
    available = restriction == 1
    user_rating = docv2.aggregateRating.starRating
    user_rating = normalize_rating(user_rating, 5)

    ad = docv2.details.appDetails
    developer_name = ad.developerName
    developer_email = ad.developerEmail
    developer_website = ad.developerWebsite
    downloads = ad.numDownloads

    ann = docv2.annotations
    privacy_policy_url = ann.privacyPolicyUrl
    contains_ads = "contains ads" in ann.badgeForDoc

    offer = docv2.offer

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
        restriction=restriction
    )

    try:
        currency = offer[0].currencyCode
        price = offer[0].formattedAmount
        offer_type = offer[0].offerType

        meta["currency"] = currency
        meta["price"] = price
        meta["offer_type"] = offer_type
    except IndexError:
        pass

    version_code = ad.versionCode
    version_string = ad.versionString
    version_date = ad.uploadDate

    versions = {
        version_string: {
            "timestamp": version_date,
            "code": version_code
        }
    }
    return meta, versions


class MissingCookieError(Exception):
    def __str__(self):
        return "response does not contain a cookie"


class AuthFailedError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f"authentication failed: {self.msg}"


class RequestFailedError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f"failed to execute request: {self.msg}"


class IncompatibleDeviceError(Exception):
    pass


class CredsError(Exception):
    def __str__(self):
        return "login accepts either (1) an email/password pair or (2) an auth_sub_token"


class NotLoggedInError(Exception):
    def __str__(self):
        return "must login before performing action"


class GooglePlaySpider(PackageListSpider):
    name = "googleplay_spider"

    def __init__(self, crawler, android_id, accounts_db_path, accounts, lang='en_US', interval=1):
        super().__init__(crawler=crawler, settings=crawler.settings)

        self.android_id = android_id
        self.interval = interval
        self.lang = lang
        self.auth_sub_tokens = self.get_auth_sub_tokens(accounts_db_path, accounts)
        if len(self.auth_sub_tokens) == 0:
            raise NotLoggedInError

    @classmethod
    def from_crawler(cls, crawler):
        params = crawler.settings.get("GPLAY_PARAMS")
        interval = params.get("interval", 0.25)

        android_id = params.get("android_id")
        accounts_db_path = params.get("accounts_db_path")
        accounts = params.get("accounts")

        return cls(crawler, android_id, accounts_db_path, accounts, interval=interval)

    # Methods for interacting with Google Play API

    def get_auth_sub_tokens(self, db_path, accounts):
        """
        Returns: the sub auth tokens for a given set of accounts.
        Fetches the sub auth tokens from a local sqlite3 database
        """
        # TODO: fetch existing ASTs from database
        self.logger.debug("getting auth sub tokens")

        res = []
        for account in accounts:
            email = account['email']
            password = account['password']
            try:
                ast = self.login(email, password)
                res.append(ast)
                # TODO: insert ast in database
            except (CredsError, AuthFailedError) as e:
                self.logger.warn(f"failed to login Google Play user '{email}': {e}")

        self.logger.debug(f"logged in {len(res)} / {len(accounts)} accounts")
        return res

    def login(self, email=None, password=None):
        """
        Logs the user in using their email address and password
        """
        if not (email and password):
            raise CredsError

        master_login = gpsoauth.perform_master_login(email, password, self.android_id)
        err = master_login.get("Error", None)
        if err == 'NeedsBrowser':
            errdetail = master_login.get("ErrorDetail", None)
            raise AuthFailedError(f"Failed display captcha: {err}: {errdetail}. "
                                  f"To access your account, you must sign in on the web."
                                  f"Follow this link: https://accounts.google.com/b/0/DisplayUnlockCaptcha")
        if err:
            errdetail = master_login.get("ErrorDetail", None)
            raise AuthFailedError(f"master login: {err}: {errdetail}")
        oauth_login = gpsoauth.perform_oauth(
            email,
            master_login.get('Token', ''),
            self.android_id,
            _SERVICE,
            _GOOGLE_LOGIN_APP,
            _GOOGLE_LOGIN_CLIENT_SIG
        )
        err = oauth_login.get("Error", None)
        if err:
            errdetail = master_login.get("ErrorDetail", None)
            raise AuthFailedError(f"oauth login: {err}: {errdetail}")
        ast = oauth_login.get('Auth', None)
        if not ast:
            raise AuthFailedError("'Auth' is missing in oauth response")
        return ast

    def _get_headers(self, post_content_type=None):
        """
        Return a dictionary of headers used for various requests
        """
        ast = np.random.choice(self.auth_sub_tokens)

        res = {
            "Accept-Language": self.lang,
            "Authorization": f"GoogleLogin auth={ast}",
            "X-DFE-Enabled-Experiments": "cl:billing.select_add_instrument_by_default",
            "X-DFE-Unsupported-Experiments": "nocache:billing.use_charging_poller,market_emails,buyer_currency,prod_baseline,checkin.set_asset_paid_app_field,shekel_test,content_ratings,buyer_currency_in_app,nocache:encrypted_apk,recent_changes",
            "X-DFE-Device-Id": self.android_id,
            "X-DFE-Client-Id": "am-android-google",
            "User-Agent": _USERAGENT_SEARCH,
            "X-DFE-SmallestScreenWidthDp": "335",
            "X-DFE-Filter-Level": "3",
            "Accept-Encoding": "",
            "Host": "android.clients.google.com"
        }
        if post_content_type:
            res["Content-Type"] = post_content_type
        return res

    # Scrapy methods

    def start_requests(self):
        for req in super().start_requests():
            yield req

    def base_requests(self):
        return [scrapy.Request(_APP_LISTING_PAGE, self.parse)]

    def url_by_package(self, pkg):
        return f"https://play.google.com/store/apps/details?id={pkg}"

    def _craft_details_req(self, pkg_name, meta=None):
        """
        Returns a scrapy.Request for the given pkg that fetches its details from the Google Play API
        Args:
            pkg_name: the name of the package to retrieve details from

        Returns: scrapy.Request
        """
        path = f"details?doc={requests.utils.quote(pkg_name)}"
        url = f"https://android.clients.google.com/fdfe/{path}"
        headers = self._get_headers()
        return scrapy.Request(url, headers=headers, priority=10, callback=self.parse_api_details, meta=meta)

    def _craft_purchase_req(self, pkg_name, version, offer_type, meta=None):
        """
        Returns a scrapy.Request for the given pkg that purchases the package
        Args:
            pkg_name: the name of the package to retrieve details from
            version: the app version
            offer_type: (almost) always 1

        Returns: scrapy.Request
        """
        url = f"https://android.clients.google.com/fdfe/purchase"
        body = f"ot={offer_type}&doc={requests.utils.quote(pkg_name)}&vc={version}"
        headers = self._get_headers(post_content_type="application/x-www-form-urlencoded; charset=UTF-8")

        return scrapy.Request(url, method='POST', body=body, headers=headers, priority=20,
                              callback=self.parse_api_purchase, meta=meta)

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps
        Example URL: https://play.google.com/store/apps
        """

        res = []

        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            req = scrapy.Request(full_url, priority=1, callback=self.parse_pkg_page)
            res.append(req)

        # follow 'See more' buttons on the home page
        see_more_links = response.xpath("//a[text() = 'See more']//@href").getall()
        for link in see_more_links:
            full_url = response.urljoin(link)
            req = scrapy.Request(full_url, callback=self.parse_similar_apps)
            res.append(req)

        # follow categories on the home page
        category_links = response.css("#action-dropdown-children-Categories a::attr(href)").getall()
        for link in category_links:
            full_url = response.urljoin(link)
            req = scrapy.Request(full_url, callback=self.parse)
            res.append(req)

        return res

    def parse_pkg_page(self, response):
        """
        Parses the page of a single package
        Example URL: https://play.google.com/store/apps/details?id=com.mi.android.globalminusscreen
        """

        res = []

        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        # icon url
        icon_url = response.xpath("//img[contains(@alt, 'Cover art')]/@src").get()

        # package name
        m = re.search(pkg_pattern, response.url)
        if m:
            pkg = m.group(1)
            req = self._craft_details_req(pkg)
            req.meta['meta'] = {
                "icon_url": icon_url,
            }
            req.meta["__pkg_start_time"] = response.meta['__pkg_start_time']
            res.append(req)

        # only search for apps recursively if enabled
        if self.recursive:
            # visit page of each package
            for pkg in packages:
                full_url = f"https://play.google.com/store/apps/details?id={pkg}"
                req = scrapy.Request(full_url, callback=self.parse_pkg_page)
                res.append(req)

            # similar apps
            similar_link = response.xpath("//a[contains(@aria-label, 'Similar')]//@href").get()
            if similar_link:
                full_url = response.urljoin(similar_link)
                req = scrapy.Request(full_url, callback=self.parse_similar_apps)
                res.append(req)

        return res

    def parse_api_details(self, response):
        """
        Parses the retrieved details from the API
        Example URL: https://android.clients.google.com/fdfe/details?doc=com.whatsapp"
        """
        res = []

        if response.status != 200:
            err_msg = ResponseWrapper.FromString(response.content).commands.displayErrorMessage
            if err_msg == _INCOMPATIBLE_DEVICE_MSG:
                raise IncompatibleDeviceError
            raise RequestFailedError(err_msg)

        details = ResponseWrapper.FromString(response.body).payload.detailsResponse

        meta, versions = parse_details(details)
        icon_url = response.meta.get('meta', {}).get('icon_url', None)
        if icon_url:
            meta['icon_url'] = icon_url

        pkg_name = meta.get('pkg_name')
        offer_type = meta.get('offer_type', 1)
        for version, dat in versions.items():
            version_code = dat.get("code")
            req = self._craft_purchase_req(pkg_name, version_code, offer_type, meta={
                'version': version,
                "meta": meta,
                "versions": versions,
                '__pkg_start_time': response.meta['__pkg_start_time']
            })
            res.append(req)

        return res

    def parse_api_purchase(self, response):
        """
        Parses the response when purchasing an app
        Example URL: https://android.clients.google.com/fdfe/purchase?ot=1&doc=com.whatsapp&vc=1
        """
        if response.status != 200:
            err_msg = ResponseWrapper.FromString(response.content).commands.displayErrorMessage
            if err_msg == _INCOMPATIBLE_DEVICE_MSG:
                raise IncompatibleDeviceError
            raise RequestFailedError(err_msg)
        body = ResponseWrapper.FromString(response.body)

        url = body.payload.buyResponse.purchaseStatusResponse.appDeliveryData.downloadUrl
        resp_cookies = body.payload.buyResponse.purchaseStatusResponse.appDeliveryData.downloadAuthCookie
        if len(resp_cookies) == 0:
            raise MissingCookieError()
        cookie = resp_cookies[0]

        cookies = {
            str(cookie.name): str(cookie.value)
        }

        headers = {
            "User-Agent": _USERAGENT_DOWNLOAD,
            "Accept-Encoding": "",
        }

        version = response.meta['version']
        meta = response.meta['meta']
        versions = response.meta['versions']
        version_data = versions[version]
        version_data['cookies'] = cookies
        version_data['headers'] = headers
        version_data['download_url'] = url
        versions[version] = version_data

        self.pause(self.interval)

        return {
            '__pkg_start_time': response.meta['__pkg_start_time'],
            'meta': meta,
            'versions': versions,
        }

    def parse_similar_apps(self, response):
        """
        Parses a page of similar apps
        Example URL: https://play.google.com/store/apps/collection/cluster?clp=ogouCBEqAggIMiYKIGNvbS5taS5hbmRyb2lkLmdsb2JhbG1pbnVzc2NyZWVuEAEYAw%3D%3D:S:ANO1ljJT8p0&gsr=CjGiCi4IESoCCAgyJgogY29tLm1pLmFuZHJvaWQuZ2xvYmFsbWludXNzY3JlZW4QARgD:S:ANO1ljK6BA8

        Args:
            response:
        """
        # find all links to packages
        packages = np.unique(response.css("a::attr(href)").re("/store/apps/details\?id=(.*)"))

        res = []

        # visit page of each package
        for pkg in packages:
            full_url = f"https://play.google.com/store/apps/details?id={pkg}"
            req = scrapy.Request(full_url, callback=self.parse_pkg_page)
            res.append(req)

        return res

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
