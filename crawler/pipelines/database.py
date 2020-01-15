import os
import sqlite3

import pg8000

from crawler.item import Result
from crawler.util import market_from_spider

_sqlite_tables = [
    ("apks", "sha256 text, path text"),
    ("packages", "pkg_name text, id text, market text, timestamp int"),
    ("versions", "pkg_name text, id text, version text, market text, sha256 text"),
]

_postgres_tables = [
    ("apks", "sha256 char(256), path text"),
    ("packages", "pkg_name text, id text, market varchar(32), timestamp int"),
    ("versions", "pkg_name text, id text, version text, market varchar(32), sha256 char(256)"),
]

_tables_from_dbtype = {
    "sqlite": _sqlite_tables,
    "postgres": _postgres_tables
}


class InvalidParametersError(Exception):
    pass


def _conn_from_params(params):
    """
    Return the database connection given the database settings of the crawler
    Args:
        params: dict

    Returns: database connection
    """
    dbtype = params.get("type", None)
    db_specific_params = params.get(dbtype, None)
    if dbtype == "sqlite":
        filename = db_specific_params.get("dbfile", None)
        conn = sqlite3.connect(filename)
    elif dbtype == "postgres":
        conn = pg8000.connect(**db_specific_params)
    else:
        raise InvalidParametersError

    if not db_specific_params:
        pass
    return conn, dbtype


class _DatabaseConnection:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.cur = self.conn.cursor()
        return self.cur

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_tb is None:
            self.conn.commit()
        else:
            self.conn.rollback()


class DatabasePipeline:
    def __init__(self, conn, dbtype):
        self.conn = conn
        self.dbtype = dbtype

        tables = _tables_from_dbtype[dbtype]
        for table, fields in tables:
            qry = f"CREATE TABLE IF NOT EXISTS {table} ({fields})"
            with _DatabaseConnection(self.conn) as cur:
                cur.execute(qry)

    def path_by_sha(self, sha):
        qry = "SELECT path FROM apks WHERE sha256 = ?"
        with _DatabaseConnection(self.conn) as cur:
            res = cur.execute(qry, (sha,))
            first = res.fetchone()
            return first[0] if first else None
        return None

    def insert(self, table, values=()):
        if self.dbtype == "sqlite":
            qry = f"INSERT INTO {table} VALUES ({', '.join(['?' for v in values])})"
        elif self.dbtype == "postgres":
            qry = f"INSERT INTO {table} VALUES {', '.join(['(%s)' for v in values])}"
        with _DatabaseConnection(self.conn) as cur:
            return cur.execute(qry, values)

    def close_spider(self, spider):
        self.cur.close()
        self.conn.close()


class PreDownloadPackagePipeline(DatabasePipeline):
    def __init__(self, conn, dbtype):
        super().__init__(conn, dbtype)

    @classmethod
    def from_crawler(cls, crawler):
        params = crawler.settings.get("DATABASE_PARAMS")
        conn, dbtype = _conn_from_params(params)
        return cls(conn, dbtype)

    def process_item(self, item, spider):
        if not isinstance(item, Result):
            return item

        self.create_package(item)

        return item

    def create_package(self, item):
        meta = item.get("meta", {})
        market = meta.get('market', "unknown")
        identifier = meta.get("id", None)
        pkg_name = meta.get("pkg_name", None)
        ts = meta.get('timestamp', 0)
        self.insert("packages", (pkg_name, identifier, market, ts))


class PreDownloadVersionPipeline(DatabasePipeline):
    """
    Checks if the APK for a specific version has already been downloaded or not
    """

    def __init__(self, conn, dbtype):
        super().__init__(conn, dbtype)

    @classmethod
    def from_crawler(cls, crawler):
        params = crawler.settings.get("DATABASE_PARAMS")
        conn, dbtype = _conn_from_params(params)
        return cls(conn, dbtype)

    def process_item(self, item, spider):
        if not isinstance(item, Result):
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
                path = self.path_by_sha(existing_sha)
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
        self.select(["sha256"], "versions", ["pkg_name", "id", "version", "market"])
        qry = "SELECT sha256 FROM versions WHERE (pkg_name = ? OR id = ?) AND version = ? and market = ?"
        with _DatabaseConnection(self.conn) as cur:
            res = cur.execute(qry, (pkg_name, identifier, version, market))
            first = res.fetchone()
            return first[0] if first else None
        return None


class PostDownloadPipeline(DatabasePipeline):
    """
    Ensures that (1) duplicate APKs cleaned up and (2) crawls are logged in the database
    """

    def __init__(self, conn, dbtype):
        super().__init__(conn, dbtype)

    @classmethod
    def from_crawler(cls, crawler):
        params = crawler.settings.get("DATABASE_PARAMS")
        conn, dbtype = _conn_from_params(params)
        return cls(conn, dbtype)

    def process_item(self, item, spider):
        if not isinstance(item, Result):
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
            existing_path = self.path_by_sha(sha)
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
