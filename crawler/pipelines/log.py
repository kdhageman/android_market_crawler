from datetime import datetime
import time

from crawler.pipelines.util import timed
from crawler.util import get_identifier


class LogPipeline:
    @timed("LogPipeline")
    def process_item(self, item, spider):
        identifier = get_identifier(item['meta'])
        start_time = item.get("__pkg_start_time", None)
        if start_time:
            elapsed = datetime.now() - start_time
            spider.logger.info(f"processed '{identifier}' in {elapsed}")
            del item['__pkg_start_time']
        else:
            spider.logger.info(f"processed '{identifier}'")
        pause(3, spider.crawler)
        return item


def pause(t, crawler):
    """
    Pause the crawler 't' seconds
    """
    try:
        crawler.engine.pause()
        time.sleep(t)
    finally:
        crawler.engine.unpause()
