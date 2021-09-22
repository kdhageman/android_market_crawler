class StatuscodeMiddleware:
    def process_spider_output(self, response, result, spider):
        status_code = response.status
        if status_code >= 300:
            # error code
            try:
                spider.handle_status(status_code)
            except:
                # ignore any exception
                pass
        return result
