import scrapy

class PackageName(scrapy.Item):
    name = scrapy.Field()

class Meta(scrapy.Item):
    meta = scrapy.Field()
    versions = scrapy.Field()