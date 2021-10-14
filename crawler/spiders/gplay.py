import json
import re
import socketserver
import time
from base64 import b64decode, urlsafe_b64encode
from http.server import BaseHTTPRequestHandler
from random import choice
from urllib.parse import urlencode, parse_qs

import numpy as np
import requests
import scrapy
import sqlite3
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.serialization import load_der_public_key
from multiprocessing import Process

import ssl

from playstoreapi.googleplay import GooglePlayAPI
from playstoreapi.googleplay_pb2 import ResponseWrapper
from scrapy import signals
from scrapy.exceptions import CloseSpider

from crawler import util
from crawler.spiders.util import PackageListSpider, normalize_rating, read_int, to_big_int
from crawler.util import get_proxy_as_dict

_CIPHERS = "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:ECDH+AESGCM:DH+AESGCM:ECDH+AES:DH+AES:RSA+AESGCM:RSA+AES:!DSS"

pkg_pattern = "https://play.google.com/store/apps/details\?id=(.*)"

_APP_LISTING_PAGE = 'https://play.google.com/store/apps'
_SERVICE = "androidmarket"
_URL_LOGIN = "https://android.clients.google.com/auth"
_URL_DELIVERY = "https://play-fe.googleapis.com/fdfe/delivery"
_ACCOUNT_TYPE_HOSTED_OR_GOOGLE = "HOSTED_OR_GOOGLE"
_GOOGLE_LOGIN_APP = 'com.android.vending'
_GOOGLE_LOGIN_CLIENT_SIG = '321187995bc7cdc2b5fc91b11a96e2baa8602c62'
_USERAGENT_DOWNLOAD = "AndroidDownloadManager/6.0 (Linux; U; Android 8.0.0; Pixel Build/OPR3.170623.013)"
_INCOMPATIBLE_DEVICE_MSG = "Your device is not compatible with this item."
_GOOGLE_PUBKEY = "AAAAgMom/1a/v0lblO2Ubrt60J2gcuXSljGFQXgcyZWveWLEwo6prwgi3iJIZdodyhKZQrNWp5nKJ3srRXc" \
                 "UW+F1BD3baEVGcmEgqaLZUNBjm057pKRI16kB0YppeGx5qIQ5QjKzsR8ETQbKLNWgRY0QRNVz34kMJR3P/L" \
                 "gHax/6rmf5AAAAAwEAAQ=="
_DFE_TARGETS = "CAEScFfqlIEG6gUYogFWrAISK1WDAg+hAZoCDgIU1gYEOIACFkLMAeQBnASLATlASUuyAyqCAjY5igOMBQzfA" \
               "/IClwFbApUC4ANbtgKVAS7OAX8YswHFBhgDwAOPAmGEBt4OfKkB5weSB5AFASkiN68akgMaxAMSAQEBA9kBO7" \
               "UBFE1KVwIDBGs3go6BBgEBAgMECQgJAQIEAQMEAQMBBQEBBAUEFQYCBgUEAwMBDwIBAgOrARwBEwMEAg0mrwE" \
               "SfTEcAQEKG4EBMxghChMBDwYGASI3hAEODEwXCVh/EREZA4sBYwEdFAgIIwkQcGQRDzQ2fTC2AjfVAQIBAYoB" \
               "GRg2FhYFBwEqNzACJShzFFblAo0CFxpFNBzaAd0DHjIRI4sBJZcBPdwBCQGhAUd2A7kBLBVPngEECHl0UEUMt" \
               "QETigHMAgUFCc0BBUUlTywdHDgBiAJ+vgKhAU0uAcYCAWQ/5ALUAw1UwQHUBpIBCdQDhgL4AY4CBQICjARbGF" \
               "BGWzA1CAEMOQH+BRAOCAZywAIDyQZ2MgM3BxsoAgUEBwcHFia3AgcGTBwHBYwBAlcBggFxSGgIrAEEBw4QEqU" \
               "CASsWadsHCgUCBQMD7QICA3tXCUw7ugJZAwGyAUwpIwM5AwkDBQMJA5sBCw8BNxBVVBwVKhebARkBAwsQEAgE" \
               "AhESAgQJEBCZATMdzgEBBwG8AQQYKSMUkAEDAwY/CTs4/wEaAUt1AwEDAQUBAgIEAwYEDx1dB2wGeBFgTQ "
_CONTENT_TYPE_URLENC = 'application/x-www-form-urlencoded; charset=UTF-8'
_version_string = "26.1.25-21 [0] [PR] 382830316"
_version_code = "81582300"
_sdk = "28"
_device = "sargo"
_hardware = "sargo"
_product = "sargo"
_platform_v = "9"
_model = "Pixel 3a"
_build_id = "PQ3B.190705.003"
_supported_abis = "arm64-v8a,armeabi-v7a,armeabi"
_gsf_version = "203315024"
_locale = "en_GB"
_timezone = 'Europe/London'
_USERAGENT_SEARCH = f"Android-Finsky/{_version_string} (api=3,versionCode={_version_code},sdk={_sdk},device={_device},hardware={_hardware},product={_product},platformVersionRelease={_platform_v},model={_model},buildId={_build_id},isWideScreen=0,supportedAbis={_supported_abis.replace(',', ';')})"
_ALLOWED_ERROR_COUNT = 5


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_len = int(self.headers['content-length'])
            post_body = self.rfile.read(content_len).decode()
            qs = parse_qs(post_body)

            proxy = qs.get("proxy")[0]
            proxy_config = get_proxy_as_dict(proxy)
        except:
            proxy_config = None

        try:
            api = GooglePlayAPI('en_US', 'Europe/Copenhagen', proxies_config=proxy_config)
            api.login(anonymous=True)
        except Exception:
            self.send_error(500)
            return

        body_raw = {
            "gsf_id": api.gsfId,
            "ast": api.authSubToken
        }
        body = bytes(json.dumps(body_raw), "utf-8")

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)


class AuthRenewServer:
    def __init__(self):
        server = socketserver.TCPServer(("", 0), Handler)
        self.port = server.server_address[1]
        server.server_close()

    def start(self):
        with socketserver.TCPServer(("", self.port), Handler) as server:
            print(f"serving anonymous GooglePlay credentials at port: {self.port}")
            try:
                server.serve_forever()
            except KeyboardInterrupt as e:
                print("Received SIGINT, shutting down gracefully")

def parse_details(details):
    """
    Parse the details from the Google Play api
    Args:
        details: dict
    """
    docv2 = details.item
    url = docv2.shareUrl
    pkg_name = docv2.id
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
    downloads = ad.downloadCount

    ann = docv2.annotations
    privacy_policy_url = ann.privacyPolicyUrl
    contains_ads = ad.installNotes == "Contains ads"

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
    version_date = ad.infoUpdatedOn

    if version_string == '':
        versions = {}
    else:
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


class Account:
    def __init__(self, gsf_id, ast):
        self.gsf_id = gsf_id
        self.ast = ast


class AuthDb:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS logins (gsfid INT, ast TEXT)")

    def get_accounts(self):
        cur = self.conn.cursor()
        qry = f"SELECT * FROM logins"
        cur.execute(qry)

        accounts = []
        for res in cur.fetchall():
            account = Account(res[0], res[1])
            accounts.append(account)

        return accounts

    def create_account(self, account):
        cur = self.conn.cursor()
        qry = "INSERT INTO logins VALUES (:gsfid, :ast)"
        cur.execute(qry, {"gsfid": account.gsf_id, "ast": account.ast})

        self.conn.commit()

    def delete_account(self, account):
        cur = self.conn.cursor()
        # remove all
        qry = "DELETE FROM logins WHERE gsfid = (:gsfid)"
        cur.execute(qry, {"gsfid": account.gsf_id})

        self.conn.commit()


class SSLContext(ssl.SSLContext):
    def set_alpn_protocols(self, protocols):
        """
        ALPN headers cause Google to return 403 Bad Authentication.
        """
        pass



class GooglePlaySpider(PackageListSpider):
    name = "googleplay_spider"

    def __init__(self, crawler, accounts_db_path, nr_anonymous_accounts, server_port, apk_enabled, lang='en_US', interval=1):
        super().__init__(crawler=crawler, settings=crawler.settings)

        self.interval = interval
        self.lang = lang
        self.server_port = server_port
        self.apk_enabled = apk_enabled

        self.nr_anonymous_accounts = nr_anonymous_accounts
        self.open_account_renewals = 0
        self.max_open_account_renewals = 10

        self.auth_db = AuthDb(path=accounts_db_path)
        self.accounts = self.auth_db.get_accounts()

        accounts_to_create = self.nr_anonymous_accounts - len(self.accounts)

        for i in range(accounts_to_create):
            url = f"http://localhost:{self.server_port}"
            try:
                res = requests.post(url=url)

                account = Account(res.json()['gsf_id'], res.json()['ast'])
                self.logger.info("created new anonymous account")
                self.auth_db.create_account(account)

                self.accounts.append(account)
            except Exception as e:
                self.logger.info(f"failed to create a new anonymous account: {e}")
                # raise CloseSpider()

    @classmethod
    def from_crawler(cls, crawler):
        params = crawler.settings.get("GPLAY_PARAMS")
        interval = params.get("interval", 0.25)

        accounts_db_path = params.get("accounts_db_path")
        nr_anonymous_accounts = params.get("nr_anonymous_accounts")
        server_port = params.get("server_port")

        spider = cls(crawler, accounts_db_path, nr_anonymous_accounts, server_port, crawler.settings.get("APK_ENABLED", True), lang='en_US', interval=interval)

        return spider

    def _get_headers(self, account, post_content_type=_CONTENT_TYPE_URLENC):
        """get_head
        Return a dictionary of headers used for various requests
        """
        res = {"Accept-Language": _locale.replace('_', '-'),
               "X-DFE-Encoded-Targets": _DFE_TARGETS,
               "User-Agent": _USERAGENT_SEARCH,
               "X-DFE-Client-Id": "am-android-google",
               "X-DFE-MCCMNC": "334050",
               "X-DFE-Network-Type": "4",
               "X-DFE-Content-Filters": "",
               "X-DFE-Request-Params": "timeoutMs=4000",
               "Authorization": f"Bearer {account.ast}",
               "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
               "X-DFE-Device-Id": f"{account.gsf_id:x}",
               "Content-Type": post_content_type,
               }

        return res

    # Scrapy methods

    def start_requests(self):
        for req in super().start_requests():
            yield req

    def base_requests(self, meta={}):
        res = [scrapy.Request(_APP_LISTING_PAGE, callback=self.parse, meta=meta)]

        return res

    def parse_account_create(self, response):
        gsf_id = response.json()['gsf_id']
        ast = response.json()['ast']
        account = Account(gsf_id, ast)

        self.logger.info("created new anonymous account")
        self.auth_db.create_account(account)

        self.accounts.append(account)

    def url_by_package(self, pkg):
        return f"https://play.google.com/store/apps/details?id={pkg}"

    def _craft_details_req(self, pkg_name, account, meta={}):
        """
        Returns a scrapy.Request for the given pkg that fetches its details from the Google Play API
        Args:
            pkg_name: the name of the package to retrieve details from

        Returns: scrapy.Request
        """
        path = f"details?doc={requests.utils.quote(pkg_name)}"
        url = f"https://android.clients.google.com/fdfe/{path}"
        headers = self._get_headers(account)
        meta['_account'] = account
        return scrapy.Request(url, headers=headers, priority=10, callback=self.parse_api_details, meta=meta)

    def _craft_purchase_req(self, pkg_name, version_code, offer_type, account, meta={}):
        """
        Returns a scrapy.Request for the given pkg that purchases the package
        Args:
            pkg_name: the name of the package to retrieve details from
            version_code: the app version
            offer_type: (almost) always 1

        Returns: scrapy.Request
        """
        url = f"https://android.clients.google.com/fdfe/purchase"
        body = f"ot={offer_type}&doc={requests.utils.quote(pkg_name)}&vc={version_code}"
        headers = self._get_headers(account, post_content_type="application/x-www-form-urlencoded; charset=UTF-8")
        meta['_account'] = account

        return scrapy.Request(url, method='POST', body=body, headers=headers, priority=20,
                              callback=self.parse_api_purchase, meta=meta)

    def _craft_delivery_request(self, pkg_name, version_code, offer_type, dl_token, account, meta={}):
        param_dict = {
            "ot": offer_type,
            "doc": pkg_name,
            "vc": version_code,
            "dtok": dl_token
        }
        meta['_account'] = account
        params = urlencode(param_dict)
        url = f"{_URL_DELIVERY}?{params}"
        headers = self._get_headers(account)
        return scrapy.Request(url, headers=headers, priority=30, callback=self.parse_delivery, meta=meta)

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
            self.logger.debug(f"scheduling new package: {pkg}")
            req = scrapy.Request(full_url, priority=1, callback=self.parse_pkg_page, meta=response.meta)
            res.append(req)

        # follow 'See more' buttons on the home page
        see_more_links = response.xpath("//a[text() = 'See more']//@href").getall()
        for link in see_more_links:
            full_url = response.urljoin(link)
            req = scrapy.Request(full_url, callback=self.parse_similar_apps, meta=response.meta)
            res.append(req)

        # follow categories on the home page
        category_links = response.css("#action-dropdown-children-Categories a::attr(href)").getall()
        for link in category_links:
            full_url = response.urljoin(link)
            self.logger.debug(f"scheduling new category: {link}")
            req = scrapy.Request(full_url, callback=self.parse, meta=response.meta)
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

        # developer address
        els = response.xpath("//*[text() = 'Developer']/../*[2]/*/*/*/text()")
        if len(els) > 0:
            # must be address
            developer_address = els[0].get()
        else:
            developer_address = None

        # package name
        m = re.search(pkg_pattern, response.url)
        if m:
            pkg = m.group(1)

            # select account
            if len(self.accounts) == 0:
                return [response.request]

            try:
                account = choice(self.accounts)
            except IndexError:
                # could not find an account, so put the request back in the queue and wait for accounts to be ready
                req = response.request
                req.dont_filter = True
                return response.request

            req = self._craft_details_req(pkg, account)

            req.meta['meta'] = {
                "icon_url": icon_url,
                "developer_address": developer_address,
            }
            req.meta["__pkg_start_time"] = response.meta['__pkg_start_time']
            self.logger.debug(f"scheduling details request: {req.url}")
            res.append(req)

        # only search for apps recursively if enabled
        if self.recursive:
            # visit page of each package
            for pkg in packages:
                full_url = f"https://play.google.com/store/apps/details?id={pkg}"
                req = scrapy.Request(full_url, callback=self.parse_pkg_page, meta=response.meta)
                res.append(req)

            # similar apps
            similar_link = response.xpath("//a[contains(@aria-label, 'Similar')]//@href").get()
            if similar_link:
                full_url = response.urljoin(similar_link)
                req = scrapy.Request(full_url, callback=self.parse_similar_apps, meta=response.meta)
                res.append(req)

        return res

    def parse_api_details(self, response):
        """
        Parses the retrieved details from the API
        Example URL: https://android.clients.google.com/fdfe/details?doc=com.whatsapp"
        """
        res = []

        account = response.meta['_account']

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

        developer_address = response.meta.get('meta', {}).get('developer_address', None)
        if developer_address:
            meta['developer_address'] = developer_address
        pkg_name = meta.get('pkg_name')
        offer_type = meta.get('offer_type', 1)

        if not self.apk_enabled:
            return {
                "meta": meta,
                "versions": versions,
                '_account': account
            }

        for version, dat in versions.items():
            version_code = dat.get("code")
            req = self._craft_purchase_req(pkg_name, version_code, offer_type, account, meta={
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
        res = []

        account = response.meta['_account']

        if response.status != 200:
            err_msg = ResponseWrapper.FromString(response.content).commands.displayErrorMessage
            if err_msg == _INCOMPATIBLE_DEVICE_MSG:
                raise IncompatibleDeviceError
            raise RequestFailedError(err_msg)
        body = ResponseWrapper.FromString(response.body)
        dl_token = body.payload.buyResponse.encodedDeliveryToken
        pkg_name = response.meta['meta']['pkg_name']
        offer_type = response.meta['meta']['offer_type']
        for version, version_dict in response.meta['versions'].items():
            version_code = version_dict['code']

            req = self._craft_delivery_request(pkg_name, version_code, offer_type, dl_token, account, meta={
                'version': version,
                "meta": response.meta['meta'],
                "versions": response.meta['versions'],
                '__pkg_start_time': response.meta['__pkg_start_time']
            })
            res.append(req)

        return res

    def parse_delivery(self, response):
        body = ResponseWrapper.FromString(response.body)

        url = body.payload.deliveryResponse.appDeliveryData.downloadUrl
        dl_auth_cookie = body.payload.deliveryResponse.appDeliveryData.downloadAuthCookie[0]
        cookies = {
            str(dl_auth_cookie.name): str(dl_auth_cookie.value)
        }

        account = response.meta['_account']
        headers = self._get_headers(account)

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
            self.logger.debug(f"scheduling new package: {pkg}")
            req = scrapy.Request(full_url, callback=self.parse_pkg_page, meta=response.meta)
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

    def process_response(self, request, response, reason):
        old_account = request.meta['_account']
        self.auth_db.delete_account(old_account)

        try:
            self.accounts.remove(old_account)
        except:
            pass

        if response.status == 401 and len(self.accounts) < self.nr_anonymous_accounts:
            self.logger.debug(f"replacing Google account due to 401 response")

            # account requests
            url = f"http://127.0.0.1:{self.server_port}"
            proxy = util.PROXY_POOL.get_proxy()
            if proxy:
                body = json.dumps({"proxy": proxy})
            else:
                body = None
            headers = {'Content-Type': 'application/json'}
            account_req = scrapy.Request(url=url, method="POST", body=body, headers=headers, priority=1000, callback=self.parse_account_create)

            retry_req = self._retry(request, reason, self)

            return [account_req, retry_req]
        return response


def encrypt_password(email, passwd):
    """Encrypt credentials using the google publickey, with the
    RSA algorithm"""

    # structure of the binary key:
    #
    # *-------------------------------------------------------*
    # | modulus_length | modulus | exponent_length | exponent |
    # *-------------------------------------------------------*
    #
    # modulus_length and exponent_length are uint32
    binaryKey = b64decode(_GOOGLE_PUBKEY)
    # modulus
    i = read_int(binaryKey, 0)
    modulus = to_big_int(binaryKey[4:][0:i])
    # exponent
    j = read_int(binaryKey, i + 4)
    exponent = to_big_int(binaryKey[i + 8:][0:j])

    # calculate SHA1 of the pub key
    digest = hashes.Hash(hashes.SHA1(), backend=default_backend())
    digest.update(binaryKey)
    h = b'\x00' + digest.finalize()[0:4]

    # generate a public key
    der_data = encode_dss_signature(modulus, exponent)
    publicKey = load_der_public_key(der_data, backend=default_backend())

    # encrypt email and password using pubkey
    to_be_encrypted = email.encode() + b'\x00' + passwd.encode()
    ciphertext = publicKey.encrypt(
        to_be_encrypted,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None
        )
    )

    return urlsafe_b64encode(h + ciphertext)


def get_login_params(email, encrypted_password):
    return {"Email": email,
            "EncryptedPasswd": encrypted_password,
            "add_account": "1",
            "accountType": _ACCOUNT_TYPE_HOSTED_OR_GOOGLE,
            "google_play_services_version": _gsf_version,
            "has_permission": "1",
            "source": "android",
            "device_country": _locale[0:2],
            "lang": _locale,
            "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
            "callerSig": "38918a453d07199354f8b19af05ec6562ced5788"}


def get_auth_headers(gsfid=None):
    headers = {
        "User-Agent": f"GoogleAuth/1.4 ({_device} {_build_id})",
    }
    if gsfid:
        headers["device"] = f"{gsfid:x}"
    return headers
