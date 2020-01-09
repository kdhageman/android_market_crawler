from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.structure.graph import Graph
from publicsuffix import PublicSuffixList, fetch

from crawler.item import pkg_name_from_result

psl = fetch()
ps = PublicSuffixList(psl)


class NoApkError(Exception):
    pass


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


def _certs_from_analysis(certs):
    """
    Returns a list of certs from the given analysis dictionary
    Args:
        analysis:

    Returns:

    """
    res = []
    for version in ["v1", "v2", "v3"]:
        try:
            for cert in certs[version]:
                res.append(cert)
        except KeyError:
            pass
    return res


# TODO: upsert
class Store:
    def __init__(self, url="ws://localhost:8182/gremlin", username="", password=""):
        graph = Graph()
        conn = DriverRemoteConnection(url, "g", username=username, password=password)
        self.g = graph.traversal().withRemote(conn)

    def store_result(self, result):
        pkg_name = pkg_name_from_result(result)
        pkg_node = self.get_or_create_package(pkg_name, result["meta"])

        market = result['meta'].get('market', "")
        for version, props in result["versions"].items():
            version_node = self.get_or_create_version(version, market, props)
            self._connect(version_node, pkg_node, "is_version_of")
        pass

    def _connect(self, src, dst, label):
        self.g.V(src.id).addE(label).to(self.g.V(dst.id)).next()

    def get_or_create_package(self, pkg_name, props):
        existing = self._get("pkg", {"pkg_name": pkg_name})
        if existing:
            return existing

        pkg_node = self._create("pkg", {"pkg_name": pkg_name})  # TODO: pass correct properties

        developer = props.get("developer_name")
        if developer:
            dev_node = self._get_or_create("developer", {"developer_name": developer})
            self._connect(dev_node, pkg_node, "develops")

        dev_site = props.get("developer_website")
        if dev_site:
            site_node = self._get_or_create("dev_site", {"site": dev_site})
            self._connect(site_node, pkg_node, "is_developer_site_for")

        dev_mail = props.get("developer_email")
        if dev_mail:
            mail_node = self._get_or_create("dev_mail", {"email": dev_mail})
            self._connect(mail_node, pkg_node, "is_developer_email_for")

        etld = _etld_from_pkg(pkg_name)
        etld_node = self._get_or_create("etld", {"etld": etld})
        self._connect(etld_node, pkg_node, "is_etld_for")

        return pkg_node

    def get_or_create_version(self, version, market, props):
        version_node = self._get_or_create("version", {"version": version, "market": market})  # TODO: pass props

        sha256 = props.get("file_sha256", None)
        if sha256:
            # DONE: get or create APK
            apk_node = self.get_or_create_apk(sha256, props.get("analysis", {}))  # TODO: pass props
            # DONE: create edge between APK and version
            self._connect(apk_node, version_node, "is_apk_for")

        return version_node

    def get_or_create_apk(self, sha256, props={}):
        apk_node = self._get_or_create("apk", {"sha256": sha256})  # pass props
        certs = props.get("certs", {})
        for version in ["v1", "v2", "v3"]:
            for cert in certs.get(version, []):
                cert_sha = cert["sha256"]
                cert_node = self._get_or_create("cert", {"sha256": cert_sha})  # TODO: pass props
                self._connect(apk_node, cert_node, version)

        assetlinks = props.get("assetlink_domains", {})
        for domain, packages in assetlinks.items():
            domain_node = self._get_or_create("domain", {"domain": domain})
            for pkg, shas in packages.items():
                for sha in shas:
                    apk_node = self._get_or_create("apk", {"sha256": sha})
                    self._connect(domain_node, apk_node, "assetlink")

        return apk_node

    def _get(self, label, ids):
        t = self.g.V()
        for idname, identifier in ids.items():
            t = t.has(label, idname, identifier)
        if t.hasNext():
            # already exists
            return t.next()
        return None

    def _create(self, label, ids, props={}):
        q = self.g.addV(label)
        for k, v in ids.items():
            q = q.property(k, v)
        for k, v in props.items():
            q = q.property(k, v)
        return q.next()

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
