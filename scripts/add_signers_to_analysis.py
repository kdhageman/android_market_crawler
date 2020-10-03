import argparse
import json
import logging
import math

from sqlalchemy import create_engine, text

from crawler.pipelines.analyze_apks import analyse

_version_table = "versions"
_column = "meta_new"


def main(args):
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO
    )
    log = logging.getLogger("main")

    db_string = f"postgres://{args.postgres_user}:{args.postgres_password}@{args.postgres_host}:{args.postgres_port}/{args.postgres_db}"
    engine = create_engine(db_string)

    with engine.connect() as conn:
        qry = "SELECT id, meta FROM versions WHERE meta is not null"
        result_set = conn.execute(qry)

    rowcount = result_set.rowcount
    perc_limit = math.ceil(rowcount / 1000)

    for i, (idx, m) in enumerate(result_set):
        meta, versions = m.values()

        for v, dat in versions.items():
            file_path = dat.get("file_path", "")
            new_analysis = analyse(file_path)
            dat['analysis'] = new_analysis
            versions[v] = dat

        jsonstr = json.dumps(dict(meta=meta, versions=versions))

        with engine.connect() as conn:
            qry = text(f"UPDATE {_version_table} SET {_column} = :jsonstr WHERE id = :idx")
            vals = dict(
                idx=idx,
                jsonstr=jsonstr
            )
            conn.execute(qry, vals)

        if i % perc_limit == 0:
            perc = i / rowcount * 100
            log.info(f"{perc:.2f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Read "versions" table from database, and adds a "signers" field to the analysis in the "meta" column')
    parser.add_argument("--postgres-user", default="postgres")
    parser.add_argument("--postgres-password", default="postgres")
    parser.add_argument("--postgres-host", default="127.0.0.1")
    parser.add_argument("--postgres-port", default=5432)
    parser.add_argument("--postgres-db", default="postgres")

    args = parser.parse_args()

    main(args)
