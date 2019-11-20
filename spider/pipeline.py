import requests


class DownloadApksPipeline:
    """
    Retrieves APKs from a set of URLs
    """

    def process_item(self, item, spider):
        item["files"] = []

        for url in item.get("download_urls", []):
            r = requests.get(url, allow_redirects=True)
            if r.status_code == 200:
                item["files"].append(r.content)
        return item
