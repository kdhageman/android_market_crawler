import random
import time
import unittest

from crawler.util import BackoffProxyPool, TestCrawler


class TestProxyPool(unittest.TestCase):
    def test_available_proxies(self):
        proxies = [
            "proxy1",
            "proxy2"
        ]
        crawler = TestCrawler()
        pp = BackoffProxyPool(crawler, proxies)

        available = pp._available_proxies()
        self.assertEqual(["proxy1", "proxy2"], available)

        pp.backoff("proxy1", milliseconds=10)
        pp.backoff("proxy2", milliseconds=20)

        available = pp._available_proxies()
        self.assertEqual([], available)

        time.sleep(0.015)  # sleep 15 ms
        available = pp._available_proxies()
        self.assertEqual(["proxy1"], available)

        time.sleep(0.01)  # sleep another 10 ms
        available = pp._available_proxies()
        self.assertEqual(["proxy1", "proxy2"], available)

    def test_get_proxy(self):
        proxies = [
            "proxy1",
            "proxy2"
        ]
        crawler = TestCrawler()
        pp = BackoffProxyPool(crawler, proxies)

        # both should be seen
        expected_vals = ["proxy1", "proxy1", "proxy2"]
        for expected_val in expected_vals:
            proxy, waittime = pp._get_proxy()
            self.assertEqual(proxy, expected_val)

        # proxy1 is backing off, so only proxy2
        pp.backoff("proxy1", milliseconds=1)

        expected_vals = ["proxy2", "proxy2", "proxy2"]
        for expected_val in expected_vals:
            proxy, waittime = pp._get_proxy()
            self.assertEqual(proxy, expected_val)

        time.sleep(0.002)

        # back to default state, because proxy1 not backing off anymore
        random.seed(1)
        expected_vals = ["proxy1", "proxy1", "proxy2"]
        for expected_val in expected_vals:
            proxy, _ = pp._get_proxy()
            self.assertEqual(proxy, expected_val)

        # proxy2 is backing off, so only proxy1
        pp.backoff("proxy2", milliseconds=1)
        expected_vals = ["proxy1", "proxy1", "proxy1"]
        for expected_val in expected_vals:
            proxy, _ = pp._get_proxy()
            self.assertEqual(proxy, expected_val)

        # both backing off, expect to see a backoff time returned
        pp.backoff("proxy1", milliseconds=1)
        pp.backoff("proxy2", milliseconds=1)
        _, waittime = pp._get_proxy()
        self.assertNotEqual(waittime, 0)


if __name__ == '__main__':
    unittest.main()
