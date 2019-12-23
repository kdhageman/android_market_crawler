import os
import sqlite3

from crawler.item import Meta

_tables = [
    ("apks", "sha256 text, path text"),
    ("packages", "id text, pkg_name text, market text, timestamp int"),
]


class SqlitePipeline:
    def __init__(self, dbfile="crawl.db"):
        self.conn = sqlite3.connect(dbfile)
        for table, fields in _tables:
            qry = f"CREATE TABLE IF NOT EXISTS {table} ({fields})"
            with self.conn:
                self.conn.execute(qry)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(**crawler.settings.get("SQLITE_PARAMS"))

    def process_item(self, item, spider):
        if not isinstance(item, Meta):
            return item

        self.create_package(item)

        for version, dat in item.get("versions", {}).items():
            sha = dat.get("file_sha256", "")
            path = dat.get("file_path", "")

            existing_path = None
            if sha:
                existing_path = self.sha_exists(sha)
            if not existing_path:
                spider.logger.info(f"creating unseen '{sha}'")
                self.create_sha(sha, path)
            else:
                spider.logger.info(f"seen '{sha}' before")
                if existing_path[0] != path:
                    # there exists an APK on a different path, so delete the one we just downloaded
                    dat['file_path'] = existing_path[0]
                    os.remove(path)
            item['versions'][version] = dat
        return item

    def create_package(self, item):
        meta = item.get("meta", {})
        market = meta.get('market', "unknown")
        identifier = meta.get("id", None)
        pkg_name = meta.get("pkg_name", None)
        ts = meta.get('timestamp', 0)
        qry = "INSERT INTO packages VALUES (?, ?, ?, ?)"
        with self.conn:
            self.conn.execute(qry, (identifier, pkg_name, market, ts))

    def sha_exists(self, sha):
        qry = "SELECT path FROM apks WHERE sha256 = ?"
        with self.conn:
            res = self.conn.execute(qry, (sha,))
            return res.fetchone()

    def create_sha(self, sha, path):
        qry = "INSERT INTO apks VALUES (?, ?)"
        with self.conn:
            res = self.conn.execute(qry, (sha, path))
