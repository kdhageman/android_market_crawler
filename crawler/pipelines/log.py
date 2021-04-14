from datetime import datetime


class LogPipeline:
    def process_item(self, item, spider):
        pkg_name = item['meta']['pkg_name']
        start_time = item.get("__pkg_start_time", None)
        if start_time:
            elapsed = datetime.now() - start_time
            spider.logger.info(f"processed '{pkg_name}' in {elapsed}")
        else:
            spider.logger.info(f"processed '{pkg_name}'")
        return item
