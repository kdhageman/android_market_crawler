import scrapy

from crawler.pipelines.database import _engine_from_params
from crawler.util import market_from_spider


class PackageListSpider(scrapy.Spider):
    """
    A superclass that starts with feeding the URL list with packages from (1) a file list and (2) the packages in the database
    """
    def start_requests(self):
        # read from packages database table
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

        # read from database
        for row in rows:
            url = self.url_by_package(row.pkg_name.strip())
            meta = {'dont_redirect': True}
            yield scrapy.Request(url, priority=-1, callback=self.parse_pkg_page, meta=meta)

        # read from package files
        pkg_files = self.settings.get("PACKAGE_FILES", [])
        for pkg_file in pkg_files:

            with open(pkg_file, 'r') as f:
                line = f.readline()
                while line:
                    url = self.url_by_package(line.strip())
                    meta = {'dont_redirect': True}
                    yield scrapy.Request(url, priority=-1, callback=self.parse_pkg_page, meta=meta)
                    line = f.readline()

        return True

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

