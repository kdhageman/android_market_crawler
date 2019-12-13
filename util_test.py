import unittest
import json
from util import jsons_from_file, merge_jsons


class TestUtil(unittest.TestCase):
    def test_json_util(self):
        path = "resources/meta.json"
        with open(path) as f:
            jsons = jsons_from_file(f)
            merged = merge_jsons(jsons)
        self.assertEqual(len(jsons), 2)
        self.assertEqual(len(json.loads(jsons[0])['versions']), 1) # only one version in the first line
        self.assertEqual(len(json.loads(jsons[1])['versions']), 1) # only one version in the second line
        self.assertEqual(len(merged['versions']), 2) # merged json has two versions
        self.assertEqual(merged['meta']['timestamp'], 1)# last line has a timestamp of 1


if __name__ == '__main__':
    unittest.main()
