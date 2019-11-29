import re

import scrapy

from pystorecrawler.item import Meta
from pystorecrawler.spiders.util import normalize_rating

id_pattern = "http://slideme\.org/application/(.*)"

class SlideMeSpider(scrapy.Spider):
    name = "slideme_spider"
    start_urls = ['http://slideme.org/']

    def parse(self, response):
        """
        Parse homepage for links to packages
        Example URL: http://slideme.org/

        Args:
            response: scrapy.Response
        """
        # pagination
        next_page = response.css("li.pager-next").css("a::attr(href)").get()
        if next_page:
            full_url = response.urljoin(next_page)
            yield scrapy.Request(full_url,
                                 callback=self.parse)  # TODO: is pagination sufficient or should we follow similar apps too ?

        # find links to other apps
        app_links = response.css("#content").css("div.node.node-mobileapp").css("h2").css("a::attr(href)").getall()
        for link in app_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        """
        Parse the page of a package
        Example URL: http://slideme.org/application/ava-journal

        Args:
            response: scrapy.Response
        """
        # meta data
        meta = dict(
            url=response.url
        )
        title = response.css("h1.title")

        meta["app_name"] = title.css("::text").get().strip()
        meta["app_description"] = "\n".join(response.xpath(
            "//div[@id='content']/div[contains(@class, 'node-mobileapp')]/div[contains(@class, 'content')]/p//text()").getall())
        meta["developer_name"] = response.css("div.submitted a::text").get().strip()
        meta["terms"] = "\n".join(response.xpath(
            "//fieldset[contains(@class, 'group-license')]/div[contains(@class, 'field-field-terms')]//text()").getall())
        meta["privacy_policy"] = "\n".join(response.xpath(
            "//fieldset[contains(@class, 'group-license')]/div[contains(@class, 'field-field-privacy-policy')]//text()").getall())
        m = re.search(id_pattern, response.url)
        if m:
            meta['id'] = m.group(1)

        meta['downloads'] =  response.css("li.downloads::text").get()
        rating = response.css("div.averages-wrapper div.average::text").get()
        meta['user_rating'] = normalize_rating(rating, 5)
        meta['content_rating'] = response.css("div.fieldgroup.group-application div.content div.field-item.odd")[0].css("::text")[-1].get().strip()

        default_language = response.css("div.fieldgroup.group-application div.content div.field-item.odd")[1].css("::text")[-1].get().strip()
        supported_languages = response.css("div.fieldgroup.group-application div.content div.field-item.odd")[2].css("::text")[-1].get().strip().split(", ")
        languages = sorted(supported_languages + [default_language])
        meta['languages'] = languages

        category = "/".join(response.css("li.category a::text").getall())
        meta['categories'] = [category]

        meta['icon_url'] = response.css("h1.title img::attr(src)").get()

        # versions
        versions = dict()
        date = response.css("div.submitted::text")[1].re(".*Updated (.*)")[0]
        version = title.css("span.version::text").get()
        dl_link = response.css("#content div.download-button a::attr(href)").get()
        full_url = response.urljoin(dl_link)
        versions[version] = dict(
            timestamp=date,
            download_url=full_url
        )

        res = Meta(
            meta=meta,
            versions=versions
        )

        yield res
