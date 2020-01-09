from influxdb import InfluxDBClient as InfluxClient


class InfluxDBClient:
    def __init__(self, params):
        self.c = None
        if params:
            self.c = InfluxClient(**params)

    def write_points(self, *args, **kwargs):
        if self.c:
            self.c.write_points(*args, **kwargs)
