import scrapy


class Result(scrapy.Item):
    meta = scrapy.Field()
    versions = scrapy.Field()
