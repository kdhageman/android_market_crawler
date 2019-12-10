import json
import re
import urllib

import scrapy

from pystorecrawler.item import Meta
from pystorecrawler.spiders.util import normalize_rating

related_tmpl = "http://openbox.mobilem.360.cn/detail/rank?soft_id=%s&cid=%s&start=0&num=100" # an open API for retrieving JSON data about apps
pkg_tmpl = "http://zhushou.360.cn/detail/index/soft_id/%s"

download_count_pattern = "下载：(.*)"
id_pattern = "http://zhushou\.360\.cn/detail/index/soft_id/(\d+)"

class ThreeSixtySpider(scrapy.Spider):
    name = "360_spider"
    start_urls = ['http://zhushou.360.cn']

    def parse(self, response):
        """
        Crawls the homepage for apps
        Example URL: http://zhushou.360.cn

        Args:
            response: scrapy.Response
        :return:
        """
        for pkg_page in response.css("div.ctcon.ctconw * a.sicon::attr(href)").getall():
            full_url = response.urljoin(pkg_page)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        Example URL: http://zhushou.360.cn/detail/index/soft_id/3947500

        Args:
            response: scrapy.Response
        """
        # meta data
        meta = dict(
            url=response.url
        )
        meta['app_name'] = response.css("#app-name > span::attr(title)").get()
        m = re.search(id_pattern, response.url)
        if m:
            meta['id'] = m.group(1)

        m = re.search(download_count_pattern, response.css("span.s-3::text").get())
        if m:
            meta['downloads'] = m.group(1)

        info_table = response.css("div.base-info > table")
        meta['developer_name'] = info_table.css("tr")[0].css("td::text")[0].get()
        language = info_table.css("tr")[2].css("td::text")[0].get()
        meta['languages'] = [language]
        meta['app_description'] = "\n".join(response.css("div.breif::text").getall()).strip() # TODO: remove 'update content'

        user_rating = response.css("span.js-votepanel::text").get()
        meta['user_rating'] = normalize_rating(user_rating, 10)
        meta['categories'] = response.css("div.app-tags a::text").getall()
        meta['icon_url'] = response.css("#app-info-panel img::attr(src)").get()

        # find download link
        versions = dict()
        date = info_table.css("tr")[0].css("td::text")[1].get()
        version = info_table.css("tr")[1].css("td::text")[0].get()
        dl_ref = response.css("a.js-downLog::attr(href)").get()
        dl_link = urllib.parse.parse_qs(dl_ref)['url'][0]

        versions[version] = dict(
            timestamp=date,
            download_url=dl_link
        )

        res = Meta(
            meta=meta,
            versions=versions
        )

        yield res

        # try to find a set of related apps by performing request against API
        if meta['id']:
            for cid in range(21): # anecdotal evidence that cids up to 20 are allowed
                related_url = related_tmpl % (meta['id'], cid)
                yield scrapy.Request(related_url, callback=self.parse_related, priority=-10)

    def parse_related(self, response):
        data = json.loads(response.body)
        if data:
            for appdata in data:
                full_url = pkg_tmpl % appdata['soft_id']
                yield scrapy.Request(full_url, callback=self.parse_pkg_page)