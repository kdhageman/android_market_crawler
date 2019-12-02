import scrapy


class PackageListSpider(scrapy.Spider):
    """
    A superclass that reads
    """
    def start_requests(self):
        pkg_files = self.settings.get("PACKAGE_FILES", [])
        for pkg_file in pkg_files:

            with open(pkg_file) as f:
                line = f.readline()
                while line:
                    url = self.url_by_package(line.strip())
                    yield scrapy.Request(url, priority=50, callback=self.parse_pkg_page)
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

