import scrapy


class TencentSpider(scrapy.Spider):
    name = "tencent_spider"
    start_urls = ['https://android.myapp.com/']

    def parse(self, response):
        # find all links to
        for link in response.css("a::attr(href)").re("../myapp/detail.htm\?apkName=.*"):
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            yield scrapy.Request(next_page, callback=self.parse)  # add URL to set of URLs to crawl

        # find meta data
        # TODO: implement

        # find download button
        for url in response.css("a::attr(data-apkurl"):
            yield {"datap-apkurl": url}
