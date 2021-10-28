import unittest

from crawler.pipelines.assetlinks import AssetLinksPipeline, parse_result
from crawler.util import TestCrawler, HttpClient


class AssetLinksPipelineTest(unittest.TestCase):
    def test_process_item(self):
        crawler = TestCrawler()
        client = HttpClient(crawler)
        pipeline = AssetLinksPipeline(client)
        item = dict(
            versions={
                "1.0.0": {
                    "analysis": {
                        "assetlink_domains": {
                            "google.com": ""
                        }
                    }
                }
            }
        )
        res = pipeline.process_item(item, None)
        al = res['versions']['1.0.0']['analysis']['assetlink_domains']['google.com']
        self.assertNotEqual(al, "")

    def test_parse_results(self):
        with open("resources/assetlinks.json", 'r') as f:
            raw = f.read()
        al = parse_result(raw)
        self.assertEqual(len(al), 6)


if __name__ == '__main__':
    unittest.main()
