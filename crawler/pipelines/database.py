import json
import os
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.sql import text

from crawler.item import Result

_version_table = "versions"

_sqlite_tables = [
    ("apks", "sha256 text, path text"),
    ("packages", "pkg_name text, id text, market text"),
    (_version_table, "pkg_name text, market_id text, version text, market text, sha256 text, timestamp timestamp, meta json, id int"),
]

_postgres_tables = [
    ("apks", "sha256 varchar(256), path text"),
    ("packages", "pkg_name text, id text, market varchar(32)"),
    (_version_table, "pkg_name text, market_id text, version text, market varchar(32), sha256 varchar(64), timestamp timestamp, meta json, id serial"),
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
        connect_args = {
            "timeout": 300  # 5 minutes
        }
        engine = create_engine(dsn, pool_size=1, max_overflow=0, connect_args=connect_args)
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
    def __init__(self, crawler):
        rootdir = crawler.settings.get('CRAWL_ROOTDIR', "/tmp/crawl")
        params = crawler.settings.get("DATABASE_PARAMS")
        engine, dbtype = _engine_from_params(params)

        self.engine = engine
        self.dbtype = dbtype
        self.outdir = os.path.join(rootdir, "apks")

        tables = _tables_from_dbtype[dbtype]
        for table, fields in tables:
            qry = text(f"CREATE TABLE IF NOT EXISTS {table} ({fields})")
            self.execute(qry)

    def path_by_sha(self, sha):
        qry = text("SELECT path FROM apks WHERE sha256 = :sha")
        vals = dict(
            sha=sha
        )
        res = self.execute(qry, vals)
        first = res.fetchone()
        return first[0] if first else None

    def execute(self, qry, vals={}):
        """
        Executes a database query
        Afterwards, cleans up the connection to the db
        """
        try:
            with self.engine.connect() as con:
                return con.execute(qry, **vals)
        finally:
            self.engine.dispose()


class PostDownloadPackagePipeline(DatabasePipeline):
    def __init__(self, crawler):
        super().__init__(crawler)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_item(self, item, spider):
        self.create_package(item)

        return item

    def create_package(self, item):
        meta = item.get("meta", {})

        pkg_name = meta.get("pkg_name", None)
        identifier = meta.get("id", None)
        market = meta.get('market', "unknown")

        if not self.pkg_exists(pkg_name, identifier, market):
            qry = text("INSERT INTO packages VALUES (:pkg_name, :identifier, :market)")
            vals = dict(
                pkg_name=pkg_name,
                identifier=identifier,
                market=market
            )
            self.execute(qry, vals)

    def pkg_exists(self, pkg_name, identifier, market):
        """
        Returns whether the given package exists or not
        """
        qry = text("SELECT * FROM packages WHERE (pkg_name = :pkg_name OR id = :identifier) AND market = :market")
        vals = dict(
            pkg_name=pkg_name,
            identifier=identifier,
            market=market
        )
        res = self.execute(qry, vals)
        first = res.fetchone()
        return first[0] if first else None


class PreDownloadVersionPipeline(DatabasePipeline):
    """
    Checks if the APK for a specific version has already been downloaded or not
    """

    def __init__(self, crawler):
        super().__init__(crawler)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_item(self, item, spider):
        meta = item.get("meta", {})
        versions = item.get("versions", {})

        pkg_name = meta.get("pkg_name", None)
        identifier = meta.get("id", None)
        market = meta.get('market', "unknown")

        for version, dat in versions.items():
            # if version exists, skip downloading it
            existing_sha, existing_meta = self.version_exists(pkg_name, identifier, version, market)
            if existing_sha:
                spider.logger.info(f"seen version '{version}' of '{pkg_name if pkg_name else identifier}' before")
                path = self.path_by_sha(existing_sha)
                dat['skip'] = True  # marks that downloading is being skipped in other pipelines
                dat['file_sha256'] = existing_sha
                dat['file_path'] = path
            if existing_meta:
                existing_analysis = existing_meta['versions'].get(version, {}).get('analysis', None)
                if existing_analysis:
                    dat['analysis'] = existing_analysis
                meta['pkg_name'] = existing_meta['meta'].get('pkg_name', None)
            versions[version] = dat

        item['versions'] = versions
        item['meta'] = meta
        return item

    def version_exists(self, pkg_name, identifier, version, market):
        """
        Returns the SHA256 value and meta information of the apk for the given tuple of values
        In case of multiple entries in the database, use the most recent information
        """
        qry = text(
            f"SELECT sha256, meta FROM {_version_table} WHERE (pkg_name = :pkg_name OR market_id = :identifier) AND version = :version and market = :market ORDER BY timestamp DESC")
        vals = dict(
            pkg_name=pkg_name,
            identifier=identifier,
            version=version,
            market=market
        )
        res = self.execute(qry, vals)
        res_sha256 = None
        res_meta = None
        while not res_sha256 and not res_meta:
            record = res.fetchone()
            if not record:
                break
            sha256, meta = record
            if not res_sha256 and sha256:
                res_sha256 = sha256
            if not res_meta and meta:
                res_meta = meta
        return res_sha256, res_meta


class PostDownloadPipeline(DatabasePipeline):
    """
    Ensures that (1) duplicate APKs cleaned up and (2) crawls are logged in the database
    """

    def __init__(self, crawler):
        super().__init__(crawler)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_item(self, item, spider):
        meta = item.get("meta", {})
        versions = item.get("versions", {})
        store_item = {'meta': meta, 'versions': versions}

        pkg_name = meta.get("pkg_name")
        identifier = meta.get("id")
        market = meta.get("market")
        ts = datetime.fromtimestamp(meta.get("timestamp"))

        # remove potentially senstive data from item
        for version, dat in versions.items():
            for sensitive_field in ["headers", "cookies"]:
                try:
                    del(dat[sensitive_field])
                except KeyError:
                    pass
            versions[version] = dat

        # create row for every version, and write ALL versions data to the database
        for version, dat in versions.items():
            sha = dat.get("file_sha256", None)
            if not dat.get("skip", False):
                # we must have downloaded the file
                path = dat.get("file_path", None)

                # create new row in 'apks' table if never seen SHA before
                if sha and not self.path_by_sha(sha):
                    self.create_sha(sha, path)

            # create version in database
            jsonstr = json.dumps(store_item)
            self.create_version(pkg_name, identifier, version, market, sha, ts, jsonstr)
        return item

    def create_version(self, pkg_name, identifier, version, market, sha, ts, jsonstr):
        with self.engine.connect() as con:
            qry = text(f"INSERT INTO {_version_table} (pkg_name, market_id, version, market, sha256, timestamp, meta) VALUES (:pkg_name, :identifier, :version, :market, :sha, :ts, :jsonstr)")
            vals = dict(
                pkg_name=pkg_name,
                identifier=identifier,
                version=version,
                market=market,
                sha=sha,
                ts=ts,
                jsonstr=jsonstr
            )
            con.execute(qry, vals)

    def create_sha(self, sha, path):
        qry = text("INSERT INTO apks VALUES (:sha, :path)")
        vals = dict(
            sha=sha,
            path=path
        )
        self.execute(qry, vals)
