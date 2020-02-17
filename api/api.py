import os
import re
import sys
import traceback
from random import choice

from flask import Flask, request, abort

from api.db import Db
from crawler.spiders.util import normalize_rating
from crawler.util import ProxyPool

sys.path.append("./gplaycrawler/playcrawler")
sys.path.append("./gplaycrawler/playcrawler/googleplayapi")
from googleplayapi.googleplay import GooglePlayAPI

app = Flask(__name__)


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


def get_accounts(path):
    db = Db(path)
    return db.load_creds()


def get_proxies(path):
    with open(path, "r") as f:
        return [l.strip() for l in f.readlines()]


def load_apis():
    proxies = get_proxies(os.getenv("PROXIES_FILE"))
    proxy_pool = ProxyPool(None, proxies)
    accounts = get_accounts(os.getenv("ACCOUNT_DB"))

    apis = []

    android_id = os.getenv("ANDROID_ID")
    for email, auth_sub_token in accounts.items():
        api = GooglePlayAPI(android_id, proxies=proxy_pool.get_proxy_as_dict())
        api.login(email=email, authSubToken=auth_sub_token)
        apis.append(api)
    return apis


_apis = load_apis()


@app.route('/details')
def details():
    pkg = request.args.get("pkg", None)
    if not pkg:
        abort(400)

    api = choice(_apis)
    try:
        details = api.toDict(api.details(pkg))
    except Exception:
        traceback.print_exc()
        abort(500)

    meta, versions = parse_details(details)

    return {"meta": meta, "versions": versions}


@app.route('/download')
def download():
    pkg = request.args.get("pkg", None)
    try:
        version_code = int(request.args.get("version_code", "throws-ValueError"))
    except ValueError:
        abort(400)
    if not pkg or not version_code:
        abort(400)

    api = choice(_apis)
    # TODO: stream response back to improve performance
    try:
        apk = api.download(pkg, version_code)
    except Exception:
        traceback.print_exc()
        abort(500)
    resp = app.response_class(
        response=apk,
        status=200,
        mimetype='application/vnd.android.package-archive'
    )
    return resp


if __name__ == "__main__":
    app.run()
