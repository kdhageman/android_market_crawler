class LogPipeline:
    def process_item(self, item, spider):
        pkg_name = item['meta']['pkg_name']
        spider.logger.info(f"processed '{pkg_name}'")
        return item
