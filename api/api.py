import os
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
    currency = offer[0].currencyCode
    price = offer[0].formattedAmount
    offer_type = offer[0].offerType

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
        price=price,
        offer_type=offer_type,
        restriction=restriction
    )

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
        details = api.details(pkg)
    except Exception:
        traceback.print_exc()
        abort(500)

    meta, versions = parse_details(details)

    return {"meta": meta, "versions": versions}


@app.route('/download')
def download():
    pkg = request.args.get("pkg", None)
    try:
        version_code = int(request.args.get("version_code", "error"))
        offer_type = int(request.args.get("offer_type", "error"))
    except ValueError:
        abort(400)
    if not pkg:
        abort(400)

    api = choice(_apis)
    # TODO: stream response back to improve performance
    try:
        apk = api.download(pkg, version_code, offerType=offer_type)
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
