import struct
from datetime import datetime
import scrapy

from crawler.pipelines.database import _engine_from_params
from crawler.util import market_from_spider


class PackageListSpider(scrapy.Spider):
    """
    A superclass that starts with feeding the URL list with packages from (1) a file list and (2) the packages in the database
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.package_files_only = False
        self.recursive = self.crawler.settings.get("RECURSIVE", False)

    def start_requests(self):
        self.retrieve_package_files = self.settings.get("RETRIEVE_PACKAGE_FILES", False)
        self.retrieve_base_requests = self.settings.get("RETRIEVE_BASE_REQUESTS", False)
        self.retrieve_from_db = self.settings.get("RETRIEVE_FROM_DB", False)

        meta = {
            'dont_redirect': True,
            '__pkg_start_time': datetime.now()
        }

        # re-crawl packages from database
        if self.retrieve_from_db:
            self.logger.debug("retrieving from db")
            params = self.settings.get("DATABASE_PARAMS")
            engine, _ = _engine_from_params(params)

            market = market_from_spider(self)
            qry = f"SELECT distinct pkg_name FROM packages WHERE pkg_name is not null and pkg_name != '' AND market = '{market}'"
            try:
                with engine.connect() as con:
                    res = con.execute(qry)
            finally:
                engine.dispose()

            rows = res.fetchall()
            for row in rows:
                url = self.url_by_package(row.pkg_name.strip())
                yield scrapy.Request(url, priority=-1, callback=self.parse_pkg_page, meta=meta)
        else:
            self.logger.debug("NOT retrieving from db")

        # read from package files
        if self.retrieve_package_files:
            self.logger.debug("retrieving from package files")
            pkg_files = self.settings.get("PACKAGE_FILES", [])
            for pkg_file in pkg_files:
                self.logger.debug(f"fetching packages from '{pkg_file}'")
                with open(pkg_file, 'r') as f:
                    line = f.readline()
                    while line:
                        pkg = line.strip()
                        self.logger.debug(f"- '{pkg}'")
                        url = self.url_by_package(pkg)
                        yield scrapy.Request(url, priority=-1, callback=self.parse_pkg_page, meta=meta)
                        line = f.readline()
        else:
            self.logger.debug("NOT retrieving from package files")

        # crawl the store as usual
        if self.retrieve_base_requests:
            self.logger.debug("retrieving from base requests")
            for req in self.base_requests(meta=meta):
                yield req
        else:
            self.logger.debug("NOT retrieving from base requests")

    def base_requests(self, meta={}):
        raise NotImplementedError()

    def parse(self, response):
        raise NotImplementedError()

    def url_by_package(self, pkg):
        raise NotImplementedError()

    def parse_pkg_page(self, response):
        raise NotImplementedError()


def version_name(orig, versions):
    """
    Finds a unique version name for the given version.
    Example: "1.0.0" -> "1.0.0 (2)", "1.0.0" -> "1.0.0 (3)"

    Args:
        orig: str
            version to find a new version from
        versions: dict
            dictionary whose keys are existings versions

    Returns: str

    """
    version = orig
    c = 2
    while version in versions:
        version = f"{orig} ({c})"
        c +=1
    return version


def normalize_rating(rating, maxval):
    """
    Normalizes a (string) rating between 0 and a max value to a float between 0 and 100
    Returns -1 if rating cannot be determined

    Args:
        rating : str
            between 0 and maxval

    Returns: float
        between 0 and 100
    """
    if not rating:
        return -1

    try:
        floatval = float(rating)
        mult_factor = 100/maxval
        return float(floatval) * mult_factor
    except ValueError:
        # rating is not a float value
        return -1


def read_int(byte_array, start):
    return struct.unpack("!L", byte_array[start:][0:4])[0]


def to_big_int(byte_array):
    array = byte_array[::-1]  # reverse array
    out = 0
    for key, value in enumerate(array):
        decoded = struct.unpack("B", bytes([value]))[0]
        out = out | decoded << key * 8
    return out
