import gpsoauth
import requests

from protobuf.proto.googleplay_pb2 import ResponseWrapper
from protobuf.util import parse_details

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


class MissingCookieError(Exception):
    def __str__(self):
        return "response does not contain a cookie"


class AuthFailedError(Exception):
    def __str__(self):
        return "authentication failed"


class RequestFailedError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f"failed to execute request: {self.msg}"


class IncompatibleDeviceError(Exception):
    pass


class InputError(Exception):
    pass


class CredsError(Exception):
    def __str__(self):
        return "login accepts either (1) an email/password pair or (2) an auth_sub_token"


class NotLoggedInError(Exception):
    def __str__(self):
        return "must login before performing action"


# decorator for checking if user is logged in or not
def logged_in(func):
    def f(*args, **kwargs):
        obj = args[0]
        if not obj.auth_sub_token:
            raise NotLoggedInError
        return func(*args, **kwargs)

    return f


def _handle_error(response):
    """
    Handles the response of the error, by throwing different types of exceptions depending on the response
    Args:
        response: a requests response
    """
    if response.status_code != 200:
        err_msg = ResponseWrapper.FromString(response.content).commands.displayErrorMessage
        if err_msg == _INCOMPATIBLE_DEVICE_MSG:
            raise IncompatibleDeviceError
        raise RequestFailedError(err_msg)


class GooglePlayApi:
    def __init__(self, android_id, lang):
        self.android_id = android_id
        if not android_id or not lang:
            raise InputError
        self.auth_sub_token = None
        self.lang = lang

    def _get_headers(self, post_content_type=None):
        """
        Return a dictionary of headers used for various requests
        """
        res = {
            "Accept-Language": self.lang,
            "Authorization": f"GoogleLogin auth={self.auth_sub_token}",
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

    def login(self, email=None, password=None, auth_sub_token=None):
        """
        Logs the user in. There are two options of doing so:
        (1) use an email address and a a password
        (2) use an auth_sub_token, which is obtained when using the first login method
        The second method takes precedence over the first
        """
        if not (auth_sub_token or (email and password)):
            raise CredsError

        if auth_sub_token:
            self.auth_sub_token = auth_sub_token

        else:
            master_login = gpsoauth.perform_master_login(email, password, self.android_id)
            oauth_login = gpsoauth.perform_oauth(
                email,
                master_login.get('Token', ''),
                self.android_id,
                _SERVICE,
                _GOOGLE_LOGIN_APP,
                _GOOGLE_LOGIN_CLIENT_SIG
            )
            ast = oauth_login.get('Auth', None)
            if ast:
                self.auth_sub_token = ast
            else:
                raise AuthFailedError

    def _do_get(self, path):
        """
        Performs a GET request to the backend of the Play Store API
        Args:
            path: the HTTP path to query
        Returns:
            a ResponseWrapper object
        """
        headers = self._get_headers()
        url = f"https://android.clients.google.com/fdfe/{path}"
        response = requests.get(url, headers=headers, timeout=10)
        _handle_error(response)
        return ResponseWrapper.FromString(response.content)

    def _do_post(self, path, data, content_type="application/x-www-form-urlencoded; charset=UTF-8"):
        """
        Performs a POST request to the backend of the Play Store API
        Args:
            path: the HTTP path to query
            data: the data sent in the POST query

        Returns:
            a ResponseWrapper object
        """
        headers = self._get_headers(post_content_type=content_type)
        url = f"https://android.clients.google.com/fdfe/{path}"
        response = requests.post(url, data=data, headers=headers, timeout=10)
        _handle_error(response)
        return ResponseWrapper.FromString(response.content)

    @logged_in
    def details(self, pkg_name):
        """
        Fetches the details (i.e. meta data) of an app on the play store
        Args:
            pkg_name: the package name that identifies an app

        Returns: a dict representation of the app details
        """
        path = f"details?doc={requests.utils.quote(pkg_name)}"
        res = self._do_get(path)
        dr = res.payload.detailsResponse
        return parse_details(dr)

    @logged_in
    def download(self, pkg_name, version_code, offer_type=1):
        """
        Download the APK for a given package name
        Args:
            pkg_name: the package name that identifies an app
            version_code: the code that can be obtained by using the details() method for the given package name
            offer_type: usually equals 1

        Returns: the raw APK file
        """
        path = "purchase"
        data = f"ot={offer_type}&doc={requests.utils.quote(pkg_name)}&vc={version_code}"

        res = self._do_post(path, data)

        url = res.payload.buyResponse.purchaseStatusResponse.appDeliveryData.downloadUrl
        if len(res.payload.buyResponse.purchaseStatusResponse.appDeliveryData.downloadAuthCookie) == 0:
            raise MissingCookieError()
        cookie = res.payload.buyResponse.purchaseStatusResponse.appDeliveryData.downloadAuthCookie[0]

        cookies = {
            str(cookie.name): str(cookie.value)  # python-requests #459 fixes this
        }

        headers = {
            "User-Agent": _USERAGENT_DOWNLOAD,
            "Accept-Encoding": "",
        }

        response = requests.get(
            url,
            headers=headers,
            cookies=cookies,
            timeout=10
        )

        return response.content
