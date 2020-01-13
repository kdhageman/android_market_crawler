from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.structure.graph import Graph
from publicsuffix import PublicSuffixList, fetch

from crawler.item import pkg_name_from_result, Result

psl = fetch()
ps = PublicSuffixList(psl)


class NoApkError(Exception):
    pass


def _props(d, remove_keys=[], flatten_keys=[], replace_keys={}):
    res = d.copy()
    for remove_key in remove_keys:
        if remove_key in res:
            del res[remove_key]

    for flatten_key in flatten_keys:
        if flatten_key in res:
            for k, v in res[flatten_key].items():
                res[f"{flatten_key}_{k}"] = v
            del res[flatten_key]

    for original, new in replace_keys.items():
        if original in res:
            res[new] = res[original]
            del res[original]
    return res


def _meta_props(result: Result):
    meta = result["meta"]
    remove_keys = [
        "pkg_name",
        "developer_name",
        "developer_email",
        "developer_website"
    ]
    return _props(meta, remove_keys=remove_keys)


def _version_props(props):
    remove_keys = [
        "analysis",
        "file_sha256",
        "file_size",
        "file_path"
    ]
    replace_keys = {
        "timestamp": "time"
    }
    return _props(props, remove_keys=remove_keys, replace_keys=replace_keys)


def _apk_props(analysis):
    remove_keys = [
        "certs",
        "assetlink_domains",
        "permissions"
    ]
    flatten_keys = [
        "android_version",
        "sdk_version",
    ]
    return _props(analysis, remove_keys=remove_keys, flatten_keys=flatten_keys)


def _dn_from_dict(d):
    matches = [
        ("country_name", "C"),
        ("state_or_province_name", "ST"),
        ("locality_name", "L"),
        ("organization_name", "O"),
        ("organizational_unit_name", "OU"),
        ("common_name", "CN")
    ]
    res_list = []
    for match, mapping in matches:
        if match in d:
            res_list.append(f"/{mapping}={d[match]}")  # ST=Madrid
    return "".join(res_list)


def _cert_props(props):
    remove_keys = [
        "sha256"
    ]
    flatten_keys = [
        "pkey"
    ]
    for key in ["subject", "issuer"]:
        vals = props[key]
        dn = _dn_from_dict(vals)
        props[key] = dn
    for key in ["not_before", "not_after"]:
        val = props[key]
        props[key] = str(val)
    return _props(props, remove_keys=remove_keys, flatten_keys=flatten_keys)


def _etld_from_pkg(pkg_name):
    """
    Return the eTLD for the given package name
    Args:
        pkg_name:

    Returns:
    """
    reverse_list = pkg_name.split(".")[::-1]
    res = ps.get_public_suffix(".".join(reverse_list))
    if "." not in res:
        res = ".".join(reverse_list[-2:])
    return res


# TODO: permissions in APKs
class Store:
    def __init__(self, url="ws://localhost:8182/gremlin", username="", password="", enabled=False):
        graph = Graph()
        self.conn = DriverRemoteConnection(url, "g", username=username, password=password)
        self.g = graph.traversal().withRemote(self.conn)

    def close(self):
        self.conn.close()

    def store_result(self, result):
        pkg_name = pkg_name_from_result(result)
        self.get_or_create_package(pkg_name, result)

    def _connect(self, src, dst, label, properties={}):
        t = self.g.V(src.id).addE(label).to(self.g.V(dst.id))
        for k, v in properties.items():
            t = t.property(k, v)
        t.next()

    def get_or_create_package(self, pkg_name, props):
        pkg_node = self._get_or_create("pkg", {"pkg_name": pkg_name})

        meta_node = self.create_meta(pkg_name, props)
        self._connect(meta_node, pkg_node, "is_meta_for")

        etld = _etld_from_pkg(pkg_name)
        etld_node = self._get_or_create("etld", {"etld": etld})
        self._connect(etld_node, pkg_node, "is_etld_for")

        return pkg_node

    def create_meta(self, pkg_name, result):
        meta_props = _meta_props(result)
        meta_node = self._get_or_create("meta", meta_props)

        meta, versions = result["meta"], result["versions"]
        market = meta.get('market', "")
        developer = meta.get("developer_name", None)
        if developer:
            dev_node = self._get_or_create("developer", {"developer_name": developer, "market": market})
            self._connect(dev_node, meta_node, "develops")

        dev_site = meta.get("developer_website", None)
        if dev_site:
            site_node = self._get_or_create("dev_site", {"site": dev_site})
            self._connect(site_node, meta_node, "is_developer_site_for")

        dev_mail = meta.get("developer_email", None)
        if dev_mail:
            mail_node = self._get_or_create("dev_mail", {"email": dev_mail})
            self._connect(mail_node, meta_node, "is_developer_email_for")

        for version, version_props in versions.items():
            version_node = self.get_or_create_version(pkg_name, version, market, version_props)
            self._connect(version_node, meta_node, "is_version_of")

        return meta_node

    def get_or_create_version(self, pkg_name, version, market, props):
        version_props = _version_props(props)
        version_node = self._get_or_create("version", {"pkg_name": pkg_name, "version": version, "market": market},
                                           props=version_props)

        sha256 = props.get("file_sha256", None)
        if sha256:
            apk_node = self.get_or_create_apk(sha256, props=props.get("analysis", {}))
            self._connect(apk_node, version_node, "is_apk_for")

        return version_node

    def get_or_create_apk(self, sha256, props={}):
        self._get("apk", {"sha256": sha256})

        apk_props = _apk_props(props)
        apk_node = self._get_or_create("apk", {"sha256": sha256}, props=apk_props)
        certs = props.get("certs", {})
        for version in ["v1", "v2", "v3"]:
            for cert in certs.get(version, []):
                cert_props = _cert_props(cert)
                cert_fingerprint = cert["sha256"]
                cert_node = self._get("cert", {"fingerprint": cert_fingerprint})
                if cert_node:
                    cert_properties = self.g.V(cert_node.id).valueMap().next()
                    if not cert_properties or "subject" not in self.g.V(cert_node.id).valueMap().next():
                        # must update the cert
                        self._update(cert_node, cert_props)
                else:
                    cert_node = self._create("cert", {"fingerprint": cert_fingerprint}, props=cert_props)
                self._connect(apk_node, cert_node, version)

        assetlinks = props.get("assetlink_domains", {})
        for domain, packages in assetlinks.items():
            domain_node = self._get_or_create("domain", {"domain": domain})
            self._connect(apk_node, domain_node, "is_in_intentfilter")

            for pkg, shas in packages.items():
                for sha in shas:
                    cert_node = self._get_or_create("cert", {"fingerprint": sha})
                    self._connect(domain_node, cert_node, "is_in_assetlinks", {"pkg_name": pkg})

        return apk_node

    def _get(self, label, ids):
        t = self.g.V()
        for idname, identifier in ids.items():
            t = t.has(label, idname, identifier)
        if t.hasNext():
            # already exists
            return t.valueMap().next()
        return None

    def _create(self, label, ids, props={}):
        q = self.g.addV(label)
        for k, v in ids.items():
            q = q.property(k, v)
        for k, v in props.items():
            q = q.property(k, v if v else "")
        return q.next()

    def _update(self, node, props={}):
        q = self.g.V(node.id)
        for k, v in props.items():
            q = q.property(k, v)
        q.next()

    def _get_or_create(self, label, ids, props={}):
        """
        Returns (and if not exists also creates) a node identified by 'id'
        Args:
            label: the type of the node
            idname: the name of the attribute that uniquely identifies the node
            id: the uniquely identifying identifier
            props: properties to create the node by

        Returns:
            The existing or newly created node
        """
        existing = self._get(label, ids)
        if existing:
            return existing

        return self._create(label, ids, props)
