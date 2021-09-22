import re
import time
from base64 import b64decode, urlsafe_b64encode
from urllib.parse import urlencode

import numpy as np
import requests
import scrapy
import sqlite3
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.serialization import load_der_public_key

import ssl

from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_

from crawler.spiders.util import PackageListSpider, normalize_rating, read_int, to_big_int
from protobuf.proto.googleplay_pb2 import ResponseWrapper

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


class AuthDb:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS logins (email TEXT, ast TEXT)")

    def get_ast(self, email):
        cur = self.conn.cursor()
        qry = f"SELECT ast FROM logins WHERE email = :email"
        cur.execute(qry, {"email": email})
        row = cur.fetchone()
        if not row:
            return None
        return row[0]

    def create_ast(self, email, ast):
        cur = self.conn.cursor()
        # remove all
        qry = "DELETE FROM logins WHERE email = :email"
        cur.execute(qry, {"email": email})

        # insert new
        qry = "INSERT INTO logins VALUES (:email, :ast)"
        cur.execute(qry, {"email": email, "ast": ast})

        self.conn.commit()


class SSLContext(ssl.SSLContext):
    def set_alpn_protocols(self, protocols):
        """
        ALPN headers cause Google to return 403 Bad Authentication.
        """
        pass


class AuthHTTPAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        """
        Secure settings from ssl.create_default_context(), but without
        ssl.OP_NO_TICKET which causes Google to return 403 Bad
        Authentication.
        """
        context = SSLContext()
        context.set_ciphers(_CIPHERS)
        context.verify_mode = ssl.CERT_REQUIRED
        context.options &= ~ssl_.OP_NO_TICKET
        self.poolmanager = PoolManager(*args, ssl_context=context, **kwargs)


class GooglePlaySpider(PackageListSpider):
    name = "googleplay_spider"

    def __init__(self, crawler, android_id, accounts_db_path, accounts, lang='en_US', interval=1):
        super().__init__(crawler=crawler, settings=crawler.settings)
        self.session = requests.session()
        self.session.mount('https://', AuthHTTPAdapter())

        if type(android_id) == int:
            self.android_id = android_id
        else:
            # from hex representation to integer
            self.android_id = int(android_id, 16)
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

        return cls(crawler, android_id, accounts_db_path, accounts, lang='en_US', interval=interval)

    # Methods for interacting with Google Play API

    def get_auth_sub_tokens(self, db_path, accounts):
        """
        Returns: the sub auth tokens for a given set of accounts.
        Fetches the sub auth tokens from a local sqlite3 database
        """
        self.logger.debug("getting auth sub tokens")

        auth_db = AuthDb(db_path)

        res = []
        for account in accounts:
            email = account['email']
            password = account['password']

            ast = auth_db.get_ast(email)
            if not ast:
                try:
                    ast = self.login(email, password)
                    auth_db.create_ast(email, ast)
                except (CredsError, AuthFailedError) as e:
                    self.logger.warn(f"failed to login Google Play user '{email}': {e}")
                    continue
            res.append(ast)
        self.logger.debug(f"logged in {len(res)} / {len(accounts)} accounts")
        return res

    def login(self, email=None, password=None):
        """
        Logs the user in using their email address and password
        """
        if not (email and password):
            raise CredsError
        encrypted_password = encrypt_password(email, password).decode('utf-8')
        params = get_login_params(email, encrypted_password)
        params['service'] = 'ac2dm'
        params['add_account'] = '1'
        params['callerPkg'] = 'com.google.android.gms'
        headers = get_auth_headers()
        headers['app'] = 'com.google.android.gsm'
        resp = self.session.post(_URL_LOGIN, data=params)

        if resp.status_code == 403:
            err_splitted = {n.split("=")[0]:"=".join(n.split("=")[1:]) for n in resp.text.split("\n")}
            if err_splitted['Error'] == "NeedsBrowser":
                raise AuthFailedError(f"To access your account, you must sign in on the web. Follow this link: https://accounts.google.com/b/0/DisplayUnlockCaptcha")

        return None

    def _get_headers(self, post_content_type=_CONTENT_TYPE_URLENC):
        """get_head
        Return a dictionary of headers used for various requests
        """
        ast = np.random.choice(self.auth_sub_tokens)

        res = {"Accept-Language": _locale.replace('_', '-'),
               "X-DFE-Encoded-Targets": _DFE_TARGETS,
               "User-Agent": _USERAGENT_SEARCH,
               "X-DFE-Client-Id": "am-android-google",
               "X-DFE-MCCMNC": "334050",
               "X-DFE-Network-Type": "4",
               "X-DFE-Content-Filters": "",
               "X-DFE-Request-Params": "timeoutMs=4000",
               "Authorization": f"Bearer {ast}",
               "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
               "X-DFE-Device-Id": f"{self.android_id:x}",
               "Content-Type": post_content_type,
               }

        return res

    # Scrapy methods

    def start_requests(self):
        for req in super().start_requests():
            yield req

    def base_requests(self, meta={}):
        return [scrapy.Request(_APP_LISTING_PAGE, callback=self.parse, meta=meta)]

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

    def _craft_purchase_req(self, pkg_name, version_code, offer_type, meta=None):
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
        headers = self._get_headers(post_content_type="application/x-www-form-urlencoded; charset=UTF-8")

        return scrapy.Request(url, method='POST', body=body, headers=headers, priority=20,
                              callback=self.parse_api_purchase, meta=meta)

    def _craft_delivery_request(self, pkg_name, version_code, offer_type, dl_token, meta=None):
        param_dict = {
            "ot": offer_type,
            "doc": pkg_name,
            "vc": version_code,
            "dtok": dl_token
        }
        params = urlencode(param_dict)
        url = f"{_URL_DELIVERY}?{params}"
        headers = self._get_headers()
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
            req = self._craft_details_req(pkg)
            req.meta['meta'] = {
                "icon_url": icon_url,
                "developer_address": developer_address,
            }
            req.meta["__pkg_start_time"] = response.meta['__pkg_start_time']
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
        res = []

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

            req = self._craft_delivery_request(pkg_name, version_code, offer_type, dl_token, meta={
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

        headers = self._get_headers()
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
