import re

import scrapy
import numpy as np

from crawler.item import Result
from crawler.spiders.util import normalize_rating

dl_pattern = "zhytools.downloadApp\((.*)\);"
id_pattern = "https://appstore\.huawei\.com/app/(.*)"


class HuaweiSpider(scrapy.Spider):
    name = "huawei_spider"

    def start_requests(self):
        for page_id in range(1, 124):
            url = f"https://appstore.huawei.com/topics/{page_id}"
            yield scrapy.Request(url, callback=self.parse_topics)

        for i in [2, 13]:
            for j in range(1, 6):
                url = f"https://appstore.huawei.com/game/list_{i}_0_{j}"
                yield scrapy.Request(url, callback=self.parse)
        yield scrapy.Request('https://appstore.huawei.com/', callback=self.parse)

    def parse(self, response):
        """
        Follow all links to package pages in the page
        Example URL: https://appstore.huawei.com/

        Args:
           response: scrapy.Response
        """
        # find links to packages
        for pkg_link in np.unique(response.css("a::attr(href)").re("/app/.*")):
            yield response.follow(pkg_link, callback=self.parse_pkg_page)

    def parse_topics(self, response):
        """
        Parses a page of topics
        Example URL: https://appstore.huawei.com/topics/
        """
        for topic_link in np.unique(response.css("a::attr(href)").re("/topic/.*")):
            yield response.follow(topic_link, callback=self.parse)

    def parse_pkg_page(self, response):
        """
        Parses the page of a package
        Example URL: https://appstore.huawei.com/app/C31346

        Args:
            response: scrapy.Response
        """
        # meta data
        meta = dict(
            url=response.url
        )

        app_info = response.css("ul.app-info-ul")
        meta["app_name"] = app_info[0].css("span.title::text").get()

        more_info = app_info[1].css("li.ul-li-detail > span::text").getall()
        meta["developer_name"] = more_info[2]

        m = re.search(id_pattern, response.url)
        if m:
            meta['id'] = m.group(1)

        app_description = "\n".join(response.css("#app_strdesc::text").getall()) + "\n"
        app_description += "\n".join(response.css("#app_desc::text").getall())
        meta["app_description"] = app_description

        meta['downloads'] = response.css("ul.app-info-ul")[0].css("span.grey.sub::text").re("下载：(.*)")[0]
        user_rating = response.css("ul.app-info-ul")[0].css("p")[1].css("span::attr(class)").re("score_(.*)")[0]
        meta['user_rating'] = normalize_rating(user_rating, 10)
        meta['icon_url'] = response.css("img.app-ico::attr(src)").get()

        # download link
        versions = dict()

        jsparams = response.css("a.mkapp-btn::attr(onclick)").re(dl_pattern)
        dl_link = jsparams[0].split(",")[5].strip(" '")  # the download link is the 6-th parameter of the js function
        date = more_info[1]
        version = more_info[3]
        versions[version] = dict(
            timestamp=date,
            download_url=dl_link
        )

        res = Result(
            meta=meta,
            versions=versions
        )

        yield res

        # sidebar on the right
        for pkg_link in response.css("div.lay-right a::attr(href)").getall():
            yield response.follow(pkg_link, callback=self.parse_pkg_page)


