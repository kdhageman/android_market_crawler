import json
import re

import requests
import scrapy

url_pattern = "https://www\.apkmonk\.com/download-app/(.*)/(.*)/"
dl_url_tmpl = "https://www.apkmonk.com/down_file/?pkg=%s&key=%s"


class ApkMonkSpider(scrapy.Spider):
    name = "apkmonk_spider"
    start_urls = ['https://www.apkmonk.com/']

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps
        :param response:
        :return:
        """
        # trending and top picks
        for pkg_link in response.css("div.col.l8.m8.s12 * div.section.side-padding-8 * a::attr(href)").getall():
            full_url = response.urljoin(pkg_link)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        :param response:
        :return:
        """
        meta = dict()
        meta['app_name'] = response.css("h1::text").get()
        trows = response.css("div.box")[1].css("table * tr")
        meta['version'] = trows[0].css("td > span::text").get()
        meta['developer_name'] = trows[3].css("td > span::text").get()
        meta['pkg_name'] =  trows[7].css("td::text").getall()[1]

        res = dict(
            meta=meta,
            download_urls=[],
        )

        # TODO: previous versions?

        button_url = response.css("#download_button::attr(href)").get()
        if button_url:
            m = re.search(url_pattern, button_url)
            if m:
                pkg = m.group(1)
                key = m.group(2)
                full_url = dl_url_tmpl % (pkg, key)

                headers = {
                    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"
                }

                r = requests.get(full_url, headers=headers)
                dl_url = json.loads(r.content)['url']
                res['download_urls'].append(dl_url)

        return res