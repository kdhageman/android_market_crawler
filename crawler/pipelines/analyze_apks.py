from asn1crypto import cms, x509

import numpy as np
from androguard.core.bytecodes.apk import APK
from sentry_sdk import capture_exception

_namespaces = {
    'android': 'http://schemas.android.com/apk/res/android'
}


def except_default(default_val):
    """
    Decorator that returns a default value in case of ANY exception
    """

    def wrapped(f):
        def func(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception:
                return default_val

        return func
    return wrapped


class AnalyzeApkPipeline:
    def process_item(self, item, spider):
        """
        Will perform an analysis on the APK defined in the filepath
        """
        meta = item['meta']

        for version, dat in item['versions'].items():
            filepath = dat.get('file_path', None)
            if filepath:
                try:
                    analysis = analyse(filepath)
                    dat['analysis'] = analysis

                    # obtain pkg_name
                    pkg_name = analysis.get("pkg_name", None)
                    existing_pkg_name = meta.get("pkg_name", None)
                    if pkg_name and not existing_pkg_name:
                        meta['pkg_name'] = pkg_name
                    elif pkg_name and existing_pkg_name and pkg_name != existing_pkg_name:
                        spider.logger.warning(f"pkg name in APK ({pkg_name}) does not match pkg name declared on market ({existing_pkg_name})")

                    item['versions'][version] = dat
                    item['meta'] = meta
                except:
                    pass
        return item


def _assetlinks_domain(host):
    """
    For the given host, extract the domain from which to obtain the asset links domain
    *money.yandex.ru -> money.yandex.ru
    *.example.com -> example.com
    Args: str
        host: host name

    Returns: str
    """
    try:
        while host[0] in ["*", "."]:
            host = host[1:]
    except IndexError:
        # For edge cases such as the domain "."
        return None
    return host


@except_default({})
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

    assetlink_domains = {}
    for uh in unique_man_hosts:
        ald = _assetlinks_domain(uh)
        if ald and ald not in assetlink_domains:
            assetlink_domains[ald] = None
    return assetlink_domains


def parse_cert(cert):
    issuer = dict(cert.issuer.native)
    subject = dict(cert.subject.native)
    not_before = int(cert.not_valid_before.timestamp())
    not_after = int(cert.not_valid_after.timestamp())
    sha256 = cert.sha256.hex()
    pkey_algo = cert.public_key.algorithm
    try:
        pkey_size = cert.public_key.bit_size
    except ValueError:
        pkey_size = 0
    pkey_sha256 = cert.public_key.sha256.hex()

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

    for cert_version, func in [
        ('v1', apk.get_certificates_v1),
        ('v2', apk.get_certificates_v2),
        ('v3', apk.get_certificates_v3),
    ]:
        try:
            for cert in func():
                parsed = parse_cert(cert)
                res[cert_version].append(parsed)
        except Exception:
            pass

    return res


def _uses_permissions_sdk_23(apk):
    res = []
    for uses_permission in apk.find_tags("uses-permission-sdk-23"):
        name = apk.get_value_from_tag(uses_permission, "name")
        max_sdk_version = apk._get_permission_maxsdk(uses_permission)
        res.append([name, max_sdk_version])
    return res


def _uses_permissions_sdk_m(apk):
    res = []
    for uses_permission in apk.find_tags("uses-permission-sdk-m"):
        name = apk.get_value_from_tag(uses_permission, "name")
        max_sdk_version = apk._get_permission_maxsdk(uses_permission)
        res.append([name, max_sdk_version])
    return res


def get_signers(apk):
    res = dict(
        v1=[],
        v2=[],
        v3=[]
    )

    # figure out signers for v1
    sig_names = apk.get_signature_names()
    certs = apk.get_certificates()

    for sig_name in sig_names:
        # extract signer information
        pkcs7msg = apk.get_file(sig_name)
        pkcs7obj = cms.ContentInfo.load(pkcs7msg)
        signer_issuer = pkcs7obj['content']['signer_infos'][0]['sid'].chosen['issuer'].native
        signer_serial = pkcs7obj['content']['signer_infos'][0]['sid'].chosen['serial_number'].native

        for cert in certs:
            cert_issuer = cert['tbs_certificate']['issuer'].native
            cert_serial = cert['tbs_certificate']['serial_number'].native

            if signer_issuer == cert_issuer and signer_serial == cert_serial:
                # print(f"Found v1 certificate '{cert.sha256.hex()[:8]}' for signature file '{sig_name}'")
                res['v1'].append(parse_cert(cert))

    # v2 and v3
    try:
        apk.parse_v2_signing_block()
    except Exception:
        pass

    for signer in apk._v2_signing_data:
        # get first cert in chain, since it is the leaf
        cert_der = signer.signed_data.certificates[0]
        cert = x509.Certificate.load(cert_der)
        # print(f"Found v2 certificate '{cert.sha256.hex()[:8]}' for signature '{signer.signatures[0][1].hex()[:16]}..'")
        res['v2'].append(parse_cert(cert))

    for signer in apk._v3_signing_data:
        cert_der = signer.signed_data.certificates[0]
        cert = x509.Certificate.load(cert_der)
        # print(f"Found v3 certificate '{cert.sha256.hex()[:8]}' for signature '{signer.signatures[0][1].hex()[:16]}..'")
        res['v3'].append(parse_cert(cert))

    return res


@except_default("unknown")
def _get_android_version_name(apk):
    return apk.get_androidversion_name()


@except_default(-1)
def _get_android_version_code(apk):
    return apk.get_androidversion_code() if apk.get_androidversion_code() else -1


@except_default(-1)
def _get_min_sdk_version(apk):
    return apk.get_min_sdk_version()


@except_default(-1)
def _get_max_sdk_version(apk):
    return apk.get_max_sdk_version()


@except_default(-1)
def _get_target_sdk_version(apk):
    return apk.get_target_sdk_version()


@except_default(-1)
def _get_effective_sdk_version(apk):
    return apk.get_effective_target_sdk_version()


def analyse(path):
    """
    Analyses the APK at the given path
    Args:
        path: str

    Returns: dict

    """
    try:
        apk = APK(path, testzip=False)
    except Exception as e:
        capture_exception(e)
        return dict(
            path=path
        )

    res = dict(
        path=path,
        certs=get_certs(apk),
        signers=get_signers(apk),
        pkg_name=apk.package,
        permissions=dict(
            uses=apk.uses_permissions,
            uses_23=_uses_permissions_sdk_23(apk),
            uses_m=_uses_permissions_sdk_m(apk),
            declared=apk.declared_permissions
        ),
        sdk_version=dict(
            min=_get_min_sdk_version(apk),
            max=_get_max_sdk_version(apk),
            target=_get_target_sdk_version(apk),
            effective=_get_effective_sdk_version(apk)
        ),
        android_version=dict(
            name=_get_android_version_name(apk),
            code=_get_android_version_code(apk)
        ),
        assetlink_domains=parse_app_links(apk.get_android_manifest_xml()),
        assetlink_status={}
    )

    return res
