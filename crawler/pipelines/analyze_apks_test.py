import unittest

from lxml import etree

from crawler.item import Result
from crawler.pipelines.analyze_apks import AnalyzeApkPipeline, parse_app_links, _assetlinks_domain


# TODO: remote test
class AnalyzeApkPipelineTest(unittest.TestCase):
    def test_process_item(self):
        pipeline = AnalyzeApkPipeline()
        item = Result(
            versions={
                '1.0.0': {
                    "file_path": "/work/git/test_project/app/build/outputs/apk/debug/app-debug.apk"
                }
            }
        )
        res = pipeline.process_item(item, None)
        pass


class TestAnalysis(unittest.TestCase):
    def test_assetlinks_domain(self):
        cases = [
            ("*money.yandex.ru", "money.yandex.ru"),
            ("*.example.com", "example.com")
        ]
        for inp, expected in cases:
            actual = _assetlinks_domain(inp)
            self.assertEqual(actual, expected)

    def test_parse_app_links(self):
        manxml = etree.parse("resources/AndroidManifest.xml")
        parsed = parse_app_links(manxml)


if __name__ == '__main__':
    unittest.main()
