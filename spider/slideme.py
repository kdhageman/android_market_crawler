import scrapy


class SlideMeSpider(scrapy.Spider):
    name = "slideme_spider"
    start_urls = ['http://slideme.org//']

    def parse(self, response):
        # pagination
        next_page = response.css("li.pager-next").css("a::attr(href)").get()
        if next_page:
            full_url = response.urljoin(next_page)
            yield scrapy.Request(full_url, callback=self.parse) # TODO: is pagination sufficient or should we follow similar apps too ?

        # find links to other apps
        app_links = response.css("#content").css("div.node.node-mobileapp").css("h2").css("a::attr(href)").getall()
        for link in app_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_pkg_page)

    def parse_pkg_page(self, response):
        meta = {}

        meta["app_name"] = response.css("h1.title::text").get().strip()
        meta["app_description"] = "\n".join(response.css("#content").css("p::text").getall()) # TODO: exclude review
        meta["developer"] = response.css("div.submitted").css("a::text").get().strip()
        meta["privacy_policy"] = "\n".join(response.css("fieldset.fieldgroup.group-license").css("p::text").getall()) # TODO: more sophisticated way of parsing the text

        res = dict(
            meta=meta,
            download_links=[]
        )

        # find download button
        dl_link = response.css("#content").css("div.download-button").css("a::attr(href)").get()
        if dl_link:
            full_url = response.urljoin(dl_link)
            res["download_links"].append(full_url)

        return res
