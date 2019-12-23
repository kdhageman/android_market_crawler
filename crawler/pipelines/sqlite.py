import os
import sqlite3

from crawler.item import Meta
from crawler.util import market_from_spider

_tables = [
    ("apks", "sha256 text, path text"),
    ("packages", "pkg_name text, id text, market text, timestamp int"),
    ("versions", "pkg_name text, id text, version text, market text, sha256 text"),
]


def path_by_sha(conn, sha):
    qry = "SELECT path FROM apks WHERE sha256 = ?"
    with conn:
        res = conn.execute(qry, (sha,))
        first = res.fetchone()
        return first[0] if first else None


class SqlitePipeline:
    def __init__(self, dbfile):
        self.conn = sqlite3.connect(dbfile)
        for table, fields in _tables:
            qry = f"CREATE TABLE IF NOT EXISTS {table} ({fields})"
            with self.conn:
                self.conn.execute(qry)


class PreDownloadPackagePipeline(SqlitePipeline):
    def __init__(self, dbfile="crawl.db"):
        super().__init__(dbfile)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(**crawler.settings.get("SQLITE_PARAMS"))

    def process_item(self, item, spider):
        if not isinstance(item, Meta):
            return item

        self.create_package(item)

        return item

    def create_package(self, item):
        meta = item.get("meta", {})
        market = meta.get('market', "unknown")
        identifier = meta.get("id", None)
        pkg_name = meta.get("pkg_name", None)
        ts = meta.get('timestamp', 0)
        qry = "INSERT INTO packages VALUES (?, ?, ?, ?)"
        with self.conn:
            self.conn.execute(qry, (pkg_name, identifier, market, ts))


class PreDownloadVersionPipeline(SqlitePipeline):
    """
    Checks if the APK for a specific version has already been downloaded or not
    """

    def __init__(self, dbfile="crawl.db"):
        super().__init__(dbfile)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(**crawler.settings.get("SQLITE_PARAMS"))

    def process_item(self, item, spider):
        if not isinstance(item, Meta):
            return item

        meta = item.get("meta", {})
        versions = item.get("versions", {})

        pkg_name = meta.get("pkg_name", None)
        identifier = meta.get("id", None)
        market = market_from_spider(spider)
        for version, dat in versions.items():
            existing_sha = self.version_exists(pkg_name, identifier, version, market)
            if existing_sha:
                spider.logger.info(f"seen version '{version}' of '{pkg_name if pkg_name else identifier}' before")
                path = path_by_sha(self.conn, existing_sha)
                dat['skip'] = True
                dat['file_sha256'] = existing_sha
                dat['file_path'] = path
                versions[version] = dat
        item['versions'] = versions
        return item

    def version_exists(self, pkg_name, identifier, version, market):
        """
        Returns the SHA256 value of the apk for the given tuple of values
        """
        qry = "SELECT sha256 FROM versions WHERE (pkg_name = ? OR id = ?) AND version = ? and market = ?"
        with self.conn:
            res = self.conn.execute(qry, (pkg_name, identifier, version, market))
            first = res.fetchone()
            return first[0] if first else None


class PostDownloadPipeline(SqlitePipeline):
    """
    Ensures that (1) duplicate APKs cleaned up and (2) crawls are logged in the database
    """

    def __init__(self, dbfile="crawl.db"):
        super().__init__(dbfile)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(**crawler.settings.get("SQLITE_PARAMS"))

    def process_item(self, item, spider):
        if not isinstance(item, Meta):
            return item

        meta = item.get("meta", {})
        versions = item.get("versions", {})

        pkg_name = meta.get("pkg_name")
        identifier = meta.get("id")
        market = market_from_spider(spider)
        for version, dat in versions.items():
            sha = dat.get("file_sha256", "")
            path = dat.get("file_path", "")
            if not sha:
                continue

            if "skip" in dat:
                del dat['skip']
            else:
                # we have not seen this version beforehand
                self.create_version(pkg_name, identifier, version, market, sha)

            # check if another APK with same hash exists
            existing_path = path_by_sha(self.conn, sha)
            if not existing_path:
                spider.logger.info(f"creating unseen path for '{sha}'")
                self.create_sha(sha, path)
            else:
                spider.logger.info(f"seen '{sha}' before")
                if existing_path != path:
                    # there exists an APK on a different path, so delete the one we just downloaded
                    dat['file_path'] = existing_path[0]
                    os.remove(path)

            item['versions'][version] = dat
        return item

    def create_version(self, pkg_name, identifier, version, market, sha):
        qry = "INSERT INTO versions VALUES (?, ?, ?, ?, ?)"
        with self.conn:
            self.conn.execute(qry, (pkg_name, identifier, version, market, sha))

    def sha_exists(self, sha):
        qry = "SELECT path FROM apks WHERE sha256 = ?"
        with self.conn:
            res = self.conn.execute(qry, (sha,))
            return res.fetchone()

    def create_sha(self, sha, path):
        qry = "INSERT INTO apks VALUES (?, ?)"
        with self.conn:
            res = self.conn.execute(qry, (sha, path))
