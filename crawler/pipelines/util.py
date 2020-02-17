from influxdb import InfluxDBClient as InfluxClient
from datetime import datetime, timezone

from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from sentry_sdk import capture_exception


class InfluxDBClient:
    def __init__(self, params):
        self.points = []
        self.c = None
        if params:
            self.c = InfluxClient(**params)

    def _add_point(self, point, t):
        point['time'] = t
        self.points.append(point)

    def add_point(self, point):
        t = str(datetime.now(timezone.utc))
        self._add_point(point, t)

    def add_points(self, points):
        t = str(datetime.now(timezone.utc))
        for point in points:
            self._add_point(point, t)

    def _send(self, spider):
        if self.c:
            try:
                self.c.write_points(self.points)
            except (InfluxDBClientError, InfluxDBServerError) as e:
                spider.logger.warning(e)
                capture_exception(e)
        self.points = []
