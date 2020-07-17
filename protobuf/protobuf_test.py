import os
from unittest import TestCase

from protobuf.protobuf import GooglePlayApi


class TestGooglePlayApi(TestCase):
    android_id = os.getenv("ANDROID_ID")
    email = os.getenv("ANDROID_EMAIL")
    password = os.getenv("ANDROID_PASSWORD")

    pkg_name = "com.google.android.apps.maps"

    lang = 'en_US'
    api = GooglePlayApi(android_id, lang)

    api.login(email=email, password=password)
    meta, versions = api.details(pkg_name)

    for k, v in versions.items():
        version_code = v['code']
        downloaded = api.download(pkg_name, version_code)
