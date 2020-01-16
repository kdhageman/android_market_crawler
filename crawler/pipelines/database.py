import os

from sqlalchemy import create_engine
from sqlalchemy.sql import text

from crawler.item import Result
from crawler.util import market_from_spider

_sqlite_tables = [
    ("apks", "sha256 text, path text"),
    ("packages", "pkg_name text, id text, market text, timestamp int, ads_status int, app_ads_status int, icon_success bool, privacy_policy_status int"),
    ("versions", "pkg_name text, id text, version text, market text, sha256 text, success int"),
]

_postgres_tables = [
    ("apks", "sha256 char(256), path text"),
    ("packages", "pkg_name text, id text, market varchar(32), timestamp int, ads_status int, app_ads_status int, icon_success boolean, privacy_policy_status int"),
    ("versions", "pkg_name text, id text, version text, market varchar(32), sha256 char(256), success int"),
]

_tables_from_dbtype = {
    "sqlite": _sqlite_tables,
    "postgres": _postgres_tables
}


class InvalidParametersError(Exception):
    pass


def _postgres_dsn_from_params(params):
    host = params.get("host")
    port = params.get("port")
    username = params.get("username")
    password = params.get("password")
    database = params.get("database")

    return f"postgresql+pg8000://{username}:{password}@{host}:{port}/{database}"


def _engine_from_params(params):
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
        dsn = f"sqlite:///{filename}"
        engine = create_engine(dsn)
    elif dbtype == "postgres":
        dsn = _postgres_dsn_from_params(db_specific_params)
        engine = create_engine(dsn)
    else:
        raise InvalidParametersError

    return engine, dbtype


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
    def __init__(self, engine, dbtype):
        self.engine = engine
        self.dbtype = dbtype

        tables = _tables_from_dbtype[dbtype]
        for table, fields in tables:
            qry = text(f"CREATE TABLE IF NOT EXISTS {table} ({fields})")
            with self.engine.connect() as con:
                con.execute(qry)

    def path_by_sha(self, sha):
        qry = text("SELECT path FROM apks WHERE sha256 = :sha")
        with self.engine.connect() as con:
            res = con.execute(qry, sha=sha)
            first = res.fetchone()
            return first[0] if first else None
        return None


class PreDownloadPackagePipeline(DatabasePipeline):
    def __init__(self, engine, dbtype):
        super().__init__(engine, dbtype)

    @classmethod
    def from_crawler(cls, crawler):
        params = crawler.settings.get("DATABASE_PARAMS")
        engine, dbtype = _engine_from_params(params)
        return cls(engine, dbtype)

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
        ads_status = meta.get("ads_status", None)
        app_ads_status = meta.get("app_ads_status", None)
        icon_status = meta.get("icon_success", None)
        privacy_policy_status = meta.get("privacy_policy_status", None)
        with self.engine.connect() as con:
            qry = text("INSERT INTO packages VALUES (:pkg_name, :identifier, :market, :ts, :ads_status, :app_ads_status, :icon_status, :privacy_policy_status)")
            vals = dict(
                pkg_name=pkg_name,
                identifier=identifier,
                market=market,
                ts=ts,
                ads_status=ads_status,
                app_ads_status=app_ads_status,
                icon_status=icon_status,
                privacy_policy_status=privacy_policy_status
            )
            con.execute(qry, **vals)


class PreDownloadVersionPipeline(DatabasePipeline):
    """
    Checks if the APK for a specific version has already been downloaded or not
    """

    def __init__(self, engine, dbtype):
        super().__init__(engine, dbtype)

    @classmethod
    def from_crawler(cls, crawler):
        params = crawler.settings.get("DATABASE_PARAMS")
        engine, dbtype = _engine_from_params(params)
        return cls(engine, dbtype)

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
        with self.engine.connect() as con:
            qry = text("SELECT sha256 FROM versions WHERE (pkg_name = :pkg_name OR id = :identifier) AND version = :version and market = :market")
            vals = dict(
                pkg_name=pkg_name,
                identifier=identifier,
                version=version,
                market=market
            )
            res = con.execute(qry, **vals)
            first = res.fetchone()
            return first[0] if first else None
        return None


class PostDownloadPipeline(DatabasePipeline):
    """
    Ensures that (1) duplicate APKs cleaned up and (2) crawls are logged in the database
    """

    def __init__(self, engine, dbtype):
        super().__init__(engine, dbtype)

    @classmethod
    def from_crawler(cls, crawler):
        params = crawler.settings.get("DATABASE_PARAMS")
        engine, dbtype = _engine_from_params(params)
        return cls(engine, dbtype)

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
            status = dat.get("file_success", None)
            if not sha:
                continue

            if "skip" in dat:
                del dat['skip']
            else:
                # we have not seen this version beforehand
                self.create_version(pkg_name, identifier, version, market, sha, status)

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

    def create_version(self, pkg_name, identifier, version, market, sha, status):
        with self.engine.connect() as con:
            qry = text("INSERT INTO versions VALUES (:pkg_name, :identifier, :version, :market, :sha, :status)")
            vals = dict(
                pkg_name=pkg_name,
                identifier=identifier,
                version=version,
                market=market,
                sha=sha,
                status=status
            )
            con.execute(qry, **vals)

    def sha_exists(self, sha):
        with self.engine.connect() as con:
            qry = text("SELECT path FROM apks WHERE sha256 = :sha")
            vals = dict(
                sha=sha
            )
            res = con.execute(qry, **vals)
            return res.fetchone()

    def create_sha(self, sha, path):
        with self.engine.connect() as con:
            qry = text("INSERT INTO apks VALUES (:sha, :path)")
            vals = dict(
                sha=sha,
                path=path
            )
            con.execute(qry, **vals)
