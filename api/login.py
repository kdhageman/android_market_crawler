import argparse
import sys

import yaml

from db import Db
from tqdm import tqdm

sys.path.append("../gplaycrawler/playcrawler")
sys.path.append("../gplaycrawler/playcrawler/googleplayapi")
from googleplayapi.googleplay import GooglePlayAPI


def main(args):
    with open(args.config, 'r') as f:
        accounts = yaml.load(f, Loader=yaml.FullLoader).get("googleplay", {}).get("accounts", [])

    db = Db(args.sqlite_file)
    creds = db.load_creds()

    for account in tqdm(accounts, desc="accounts"):
        email = account['email']
        password = account['password']
        if email not in creds:
            api = GooglePlayAPI(args.android_id)
            api.login(email=email, password=password)
            auth_sub_token = api.authSubToken
            db.set_token(email, auth_sub_token)


def parse_arguments():
    parser = argparse.ArgumentParser("Script to populate sqlite database with Android credentials")
    parser.add_argument("--android-id", help="ID of Android device", required=True)
    parser.add_argument("--sqlite-file", help="Path to sqlite database", default="accounts.db")
    parser.add_argument("--config", help="Path to YAML configuration file", default="../config/config.yml")
    parser.add_argument("--proxies_file", help="Path to file of proxy addresses", default="../config/proxies.txt")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_arguments()
    main(args)
