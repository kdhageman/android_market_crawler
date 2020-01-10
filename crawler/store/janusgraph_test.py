import json
import unittest

from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.structure.graph import Graph

from crawler.item import Result
from crawler.store.janusgraph import Store, _etld_from_pkg, _apk_props, _dn_from_dict


def connect(url, username="", password=""):
    graph = Graph()
    conn = DriverRemoteConnection(url, 'g', username=username, password=password)
    return conn, graph.traversal().withRemote(conn)


class TestStore(unittest.TestCase):
    url = "ws://localhost:8182/gremlin"

    def setUp(self):
        self.s = Store(self.url)
        conn, g = connect(self.url)
        # remove all vertices and edges
        g.V().drop().iterate()
        g.E().drop().iterate()
        conn.close()

    def tearDown(self):
        self.s.close()

    def test_store_result(self):
        with open("resources/meta.1.json") as f:
            raw = f.read()
        parsed = json.loads(raw)

        result = Result(
            meta=parsed['meta'],
            versions=parsed['versions']
        )
        self.s.store_result(result)

        class Case:
            def __init__(self, label, expected_count, expected_edges):
                self.label = label
                self.expected_count = expected_count
                self.expected_edges = expected_edges

        cases = [
            Case("pkg", 1, 2),
            Case("meta", 1, 5),
            Case("developer", 1, 1),
            Case("dev_site", 1, 1),
            Case("dev_mail", 1, 1),
            Case("etld", 1, 1),
            Case("version", 1, 2),
            Case("apk", 1, 5),
            Case("cert", 2, 5),
            Case("domain", 1, 3)
        ]

        conn, g = connect(self.url)
        for case in cases:
            actual_count = g.V().hasLabel(case.label).count().next()
            self.assertEqual(actual_count, case.expected_count)
            actual_edges = g.V().hasLabel(case.label).both().count().next()
            self.assertEqual(actual_edges, case.expected_edges)
        conn.close()

        with open("resources/meta.2.json") as f:
            raw = f.read()
        parsed = json.loads(raw)

        result = Result(
            meta=parsed['meta'],
            versions=parsed['versions']
        )
        self.s.store_result(result)

    def test_etld_from_pkg(self):
        class Case:
            def __init__(self, pkg, expected):
                self.pkg = pkg
                self.expected = expected

        cases = [
            Case("uk.co.example.www", "example.co.uk"),
            Case("ctrip.android.view", "android.ctrip")
        ]
        for case in cases:
            etld = _etld_from_pkg(case.pkg)
            self.assertEqual(etld, case.expected)

    def test_apk_props(self):
        with open("resources/meta.1.json") as f:
            raw = f.read()
        parsed = json.loads(raw)

        analysis = parsed['versions']["9.9"]["analysis"]
        apk_props = _apk_props(analysis)

        expected_props = [
            "path",
            "pkg_name",
            "sdk_version_min",
            "sdk_version_max",
            "sdk_version_target",
            "sdk_version_effective",
            "android_version_name",
            "android_version_code",
        ]
        for expected_prop in expected_props:
            self.assertTrue(expected_prop in apk_props)
        self.assertEqual(len(expected_props), len(apk_props))

    def test_dn_from_dict(self):
        d = {
            "country_name": "US",
            "state_or_province_name": "California",
            "locality_name": "Mountain View",
            "organization_name": "Google Inc.",
            "organizational_unit_name": "Android",
            "common_name": "Android"
        }
        expected = "/C=US/ST=California/L=Mountain View/O=Google Inc./OU=Android/CN=Android"

        actual = _dn_from_dict(d)
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
