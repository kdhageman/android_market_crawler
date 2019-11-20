import scrapy

pkg_pattern = "https://f-droid\.org/en/packages/(.*)/"


class ApkMirrorSpider(scrapy.Spider):
    name = "apkmirror_spider"
    start_urls = ['https://www.apkmirror.com/']

    def parse(self, response):
        """
        Crawls the pages with the paginated list of apps
        :param response:
        :return:
        """
        # follow pagination
        a_to_next = response.css("a.nextpostslink::attr(href)").get()
        if a_to_next:
            next_page = response.urljoin(a_to_next)
            yield scrapy.Request(next_page, callback=self.parse)  # add URL to set of URLs to crawl

        # links to packages
        for link in response.css("a.fontBlack::attr(href)").getall():
            next_page = response.urljoin(link)  # build absolute URL based on relative link
            yield scrapy.Request(next_page, callback=self.parse_pkg_page)  # add URL to set of URLs to crawl

    # TODO: by combining meta info from pkg page and download page, we store redundant information
    def parse_pkg_page(self, response):
        header = response.css("div.site-header-contents")

        developer_name = header.css("h3").css("a::text").get()
        app_name = header.css("h1::text").get()
        app_description = "\n".join(response.css("#description").css("div.notes::text").getall()).strip()

        res = dict(
            meta=dict(
                developer_name=developer_name,
                app_name=app_name,
                app_description=app_description
            ),
            download_urls=[],
        )

        list_widgets = response.css("#content").css("div.listWidget")
        for variant_link in list_widgets[0].css("div.table").css("a::attr(href)").getall():
            full_link = response.urljoin(variant_link)
            yield scrapy.Request(full_link, callback=self.parse_download_page, meta=res)

        # TODO: download all different versions

    def parse_download_page(self, response):
        """
        Parses the page with an apps download link
        :param response:
        :return:
        """
        res = response.meta

        # meta data
        appspec = response.css("#file").css("div.appspec-row")[0].css("div.appspec-value")
        res["meta"]["version"] = appspec.css("::text").getall()[0]

        m = appspec.css("::text")[2].re("Package: (.*)")
        if m:
            res["meta"]["pkg_name"] = m[0]

        # find download link
        dl = response.css("a.downloadButton::attr(href)").get()
        if dl:
            res["download_urls"].append(response.urljoin(dl))

        return res
