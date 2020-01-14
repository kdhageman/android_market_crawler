import unittest
import json
from scripts.util import jsons_from_file, merge_jsons, merge


class TestUtil(unittest.TestCase):
    def test_json_util(self):
        path = "../resources/meta.json"
        with open(path) as f:
            jsons = jsons_from_file(f)
            merged = merge_jsons(jsons)
        self.assertEqual(len(jsons), 2)
        self.assertEqual(len(json.loads(jsons[0])['versions']), 1)  # only one version in the first line
        self.assertEqual(len(json.loads(jsons[1])['versions']), 1)  # only one version in the second line
        self.assertEqual(len(merged['versions']), 2)  # merged json has two versions
        self.assertEqual(merged['meta']['timestamp'], 1)  # last line has a timestamp of 1

    def test_merge(self):
        a = {
            "a": {
                "aa": 0,
                "ab": 1,
            },
            "b": {
                "ba": 2,
                "bb": 3,
            }
        }
        b = {
            "a": {
                "aa": 4,
            },
            "b": {
                "bb": 5,
            }
        }

        merged = merge(a, b)

        expected = {
            "a": {
                "aa": 4,
                "ab": 1,
            },
            "b": {
                "ba": 2,
                "bb": 5,
            }
        }

        self.assertEqual(merged, expected)


if __name__ == '__main__':
    unittest.main()
