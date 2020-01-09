import json
import unittest

from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.structure.graph import Graph

from crawler.item import Result
from crawler.store.janusgraph import Store, _etld_from_pkg


def connect(url, username="", password=""):
    graph = Graph()
    conn = DriverRemoteConnection(url, 'g', username=username, password=password)
    return graph.traversal().withRemote(conn)


class TestStore(unittest.TestCase):
    url = "ws://localhost:8182/gremlin"

    def setUp(self):
        self.s = Store(self.url)
        g = connect(self.url)
        # remove all vertices and edges
        g.V().drop().iterate()
        g.E().drop().iterate()

    def test_init(self):
        with open("resources/meta.json") as f:
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
            Case("pkg", 1, 5),
            Case("developer", 1, 1),
            Case("dev_site", 1, 1),
            Case("dev_mail", 1, 1),
            Case("etld", 1, 1),
            Case("version", 1, 2),
            Case("apk", 1, 4),
            Case("cert", 1, 3)
        ]

        g = connect(self.url)
        for case in cases:
            actual_count = g.V().hasLabel(case.label).count().next()
            self.assertEqual(actual_count, case.expected_count)
            actual_edges = g.V().hasLabel(case.label).both().count().next()
            self.assertEqual(actual_edges, case.expected_edges)

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


if __name__ == '__main__':
    unittest.main()
