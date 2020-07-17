import os
import sys
import traceback
from random import choice

from flask import Flask, request, abort

from api.db import Db
from crawler.spiders.util import normalize_rating
from crawler.util import ProxyPool
from protobuf.util import parse_details

sys.path.append("./gplaycrawler/playcrawler")
sys.path.append("./gplaycrawler/playcrawler/googleplayapi")
from googleplayapi.googleplay import GooglePlayAPI

app = Flask(__name__)





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
        api.login(email=email, auth_sub_token=auth_sub_token)
        apis.append(api)
    print("[*] Successfully logged in all Google Play accounts")
    return apis


_apis = load_apis()


@app.route('/ping')
def ping():
    return "pong"


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
