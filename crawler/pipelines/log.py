from datetime import datetime
import time
from crawler.util import get_identifier


class LogPipeline:
    def __init__(self, pause_interval):
        self.pause_interval = pause_interval

    @classmethod
    def from_settings(cls, settings):
        pause_interval = settings.get("PAUSE_INTERVAL", 3)
        return cls(pause_interval)

    def process_item(self, item, spider):
        identifier = get_identifier(item['meta'])
        start_time = item.get("__pkg_start_time", None)
        if start_time:
            elapsed = datetime.now() - start_time
            spider.logger.info(f"processed '{identifier}' in {elapsed}")
            del item['__pkg_start_time']
        else:
            spider.logger.info(f"processed '{identifier}'")
        pause(self.pause_interval, spider.crawler)
        return item


def pause(t, crawler):
    """
    Pause the crawler 't' seconds
    """
    if not t:
        return
    try:
        crawler.engine.pause()
        time.sleep(t)
    finally:
        crawler.engine.unpause()
