from datetime import datetime, timezone
from influxdb_client import InfluxDBClient as InfluxClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from sentry_sdk import capture_exception


class InfluxDBClient:
    def __init__(self, params={}):
        self.points = []
        self.api = None
        self.c = None

        enabled = params.get("enabled", False)
        if enabled:
            url = params.get("server-url", None)
            token = params.get("auth-token", None)
            org = params.get("organisation", None)
            bucket = params.get("bucket", None)
            self.bucket = bucket
            self.c = InfluxClient(url=url, token=token, org=org)
            self.api = self.c.write_api(write_options=SYNCHRONOUS)

    def _add_point(self, point, t):
        point['time'] = t
        point = Point.from_dict(point)
        self.points.append(point)

    def add_point(self, point):
        if self.api:
            t = str(datetime.now(timezone.utc))
            self._add_point(point, t)

    def add_points(self, points):
        if self.api:
            t = str(datetime.now(timezone.utc))
            for point in points:
                self._add_point(point, t)

    def send(self, spider):
        if self.api:
            try:
                self.api.write(bucket=self.bucket, record=self.points)
            except (InfluxDBClientError, InfluxDBServerError) as e:
                spider.logger.warning(e)
                capture_exception(e)
            finally:
                self.points = []

    def close(self):
        if self.api:
            self.c.close()
