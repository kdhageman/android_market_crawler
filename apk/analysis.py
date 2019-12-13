from lxml import etree
import numpy as np
from zipfile import BadZipFile

from androguard.core.bytecodes.apk import APK

_namespaces = {
    'android': 'http://schemas.android.com/apk/res/android'
}

def _assetlinks_domain(host):
    """
    For the given host, extract the domain from which to obtain the asset links domain
    *money.yandex.ru -> money.yandex.ru
    *.example.com -> example.com
    Args: str
        host: host name

    Returns: str
    """
    while host[0] in ["*", "."]:
        host = host[1:]
    return host

def parse_app_links(man):
    """
    Parse the manifest.xml document for app links
    Args:
        man: lxml.Element

    Returns: list of str
    """
    # find all domain names to be verified for app linking purposes
    man_hosts = man.xpath("//intent-filter[@android:autoVerify='true']/data/@android:host", namespaces=_namespaces)
    unique_man_hosts = np.unique(man_hosts)

    assetlink_domains = []
    for uh in unique_man_hosts:
        ald = _assetlinks_domain(uh)
        if ald not in assetlink_domains:
            assetlink_domains.append(ald)
    return assetlink_domains


def parse_cert(cert):
    issuer = dict(cert.issuer.native)
    subject = dict(cert.subject.native)
    not_before = int(cert.not_valid_before.timestamp())
    not_after = int(cert.not_valid_after.timestamp())
    sha256 = cert.sha256.hex()
    pkey_algo = cert.public_key.algorithm
    pkey_size = cert.public_key.bit_size
    pkey_sha256 = cert.sha256.hex()

    return dict(
        issuer=issuer,
        subject=subject,
        not_before=not_before,
        not_after=not_after,
        sha256=sha256,
        pkey=dict(
            algo=pkey_algo,
            size=pkey_size,
            sha256=pkey_sha256
        )
    )


def get_certs(apk):
    res = dict(
        v1=[],
        v2=[],
        v3=[]
    )

    for cert in apk.get_certificates_v1():
        parsed = parse_cert(cert)
        res['v1'].append(parsed)

    for cert in apk.get_certificates_v2():
        parsed = parse_cert(cert)
        res['v2'].append(parsed)

    for cert in apk.get_certificates_v3():
        parsed = parse_cert(cert)
        res['v3'].append(parsed)

    return res

def _uses_permissions_sdk_23(apk):
    res = []
    for uses_permission in apk.find_tags("uses-permission-sdk-23"):
        name = apk.get_value_from_tag(uses_permission, "name")
        max_sdk_version = apk._get_permission_maxsdk(uses_permission)
        res.append([name, max_sdk_version])
    return res

def analyse(path):
    """
    Analyses the APK at the given path
    Args:
        path: str

    Returns: dict

    """
    try:
        apk = APK(path)
    except BadZipFile:
        print(f"bad zip file: {path}")
        return dict(
            path=path
        )

    res = dict(
        path=path,
        certs=get_certs(apk),
        pkg_name=apk.package,
        permissions=dict(
            uses=apk.uses_permissions,
            uses_23=_uses_permissions_sdk_23(apk),
            declared=apk.declared_permissions
        ),
        sdk_version=dict(
            min=apk.get_min_sdk_version(),
            max=apk.get_max_sdk_version(),
            target=apk.get_target_sdk_version(),
            effective=apk.get_effective_target_sdk_version()
        ),
        android_version=dict(
            name=apk.get_androidversion_name(),
            code=apk.get_androidversion_code()
        ),
        assetlink_domains=parse_app_links(apk.get_android_manifest_xml())
    )

    return res
