import re
import urllib

import scrapy

download_count_pattern = "下载：(.*)"
id_pattern = "http://zhushou\.360\.cn/detail/index/soft_id/(\d+)"

class ThreeSixtySpider(scrapy.Spider):
    name = "360_spider"
    start_urls = ['http://zhushou.360.cn']

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps
        :param response:
        :return:
        """
        # TODO: use JSON API for discovering apps
        # http://openbox.mobilem.360.cn/Guessyoulike/detail?softId=95487&start=0&count=30
        # http://openbox.mobilem.360.cn/detail/rank?soft_id=77208&cid=0&start=0&num=1000

        # TODO: more apps?
        for pkg_page in response.css("div.ctcon.ctconw * a.sicon::attr(href)").getall():
            full_url = response.urljoin(pkg_page)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Crawls the page of a single app
        :param response:
        :return:
        """
        # meta data
        meta = dict()
        meta['app_name'] = response.css("#app-name > span::attr(title)").get()
        m = re.search(id_pattern, response.url)
        if m:
            meta['id'] = m.group(1)

        m = re.search(download_count_pattern, response.css("span.s-3::text").get())
        if m:
            meta['downloads'] = m.group(1)

        info_table = response.css("div.base-info > table")
        meta['developer_name'] = info_table.css("tr")[0].css("td::text")[0].get()
        meta['updated'] = info_table.css("tr")[0].css("td::text")[1].get()
        meta['version'] = info_table.css("tr")[1].css("td::text")[0].get()
        meta['language'] = info_table.css("tr")[2].css("td::text")[0].get()
        meta['app_description'] = "\n".join(response.css("div.breif::text").getall()).strip() # TODO: remove 'update content'

        res = dict(
            meta=meta,
            download_urls=[],
        )
        # TODO: links to other packages

        # find download link
        dl_ref = response.css("a.js-downLog::attr(href)").get()
        if dl_ref:
            dl_link = urllib.parse.parse_qs(dl_ref)['url'][0]
            res['download_urls'].append(dl_link)

        return res