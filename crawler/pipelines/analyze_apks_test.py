import unittest

from lxml import etree

from crawler.pipelines.analyze_apks import AnalyzeApkPipeline, parse_app_links, _assetlinks_domain, \
    _get_android_version_name


# TODO: remote test
class AnalyzeApkPipelineTest(unittest.TestCase):
    def test_process_item(self):
        pipeline = AnalyzeApkPipeline()
        item = dict(
            meta={
                "pkg_name": "com.apple.test"
            },
            versions={
                '1.0.0': {
                    "file_path": "/Volumes/Samsung_T5/data/apps/pystorecrawler/apks/3e1886c02c744716fb7d9381b82cc6a8c86e800ec0e2b4a0656609df7b3bb4ab.apk"
                }
            }
        )
        res = pipeline.process_item(item, None)
        pass


class TestAnalysis(unittest.TestCase):
    def test_assetlinks_domain(self):
        cases = [
            ("*money.yandex.ru", "money.yandex.ru"),
            ("*.example.com", "example.com"),
            (".", None)
        ]
        for inp, expected in cases:
            actual = _assetlinks_domain(inp)
            self.assertEqual(actual, expected)

    def test_parse_app_links(self):
        manxml = etree.parse("resources/AndroidManifest.xml")
        parsed = parse_app_links(manxml)
        expected = {
            'money.yandex.ru': None
        }
        self.assertEqual(parsed, expected)

    def test_android_get_version_name(self):
        class _Apk:
            def __init__(self, raise_exc):
                self.raise_exc = raise_exc

            def get_androidversion_name(self):
                if self.raise_exc:
                    raise Exception("Exception!")
                else:
                    return "version_name"

        testcases = [
            (False, "version_name"),
            (True, "unknown")
        ]

        for apk_param, expected in testcases:
            apk = _Apk(apk_param)
            actual = _get_android_version_name(apk)
            self.assertEqual(expected, actual)


if __name__ == '__main__':
    unittest.main()
