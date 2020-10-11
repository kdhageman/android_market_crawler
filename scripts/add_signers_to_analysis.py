import argparse
import json
import logging
import math
import os
import queue
import sys
from multiprocessing import Queue, Process

from sqlalchemy import create_engine, text

sys.path.append(os.path.abspath('.'))
from crawler.pipelines.analyze_apks import analyse

_version_table = "versions"
_column = "meta_new"


def update_analysis(q_tasks, q_progress, db_string):
    engine = create_engine(db_string)

    while True:
        try:
            idx, m = q_tasks.get_nowait()
        except queue.Empty:
            break

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

        # bump progress
        q_progress.put(None)


def progress(q, rowcount):
    i = 0
    perc_limit = math.ceil(rowcount / 1000)

    while True:
        try:
            q.get()
        except queue.Empty:
            break

        i += 1

        if i % perc_limit == 0:
            perc = i / rowcount * 100
            msg = f"{perc:.2f}%"
            print(msg)



def main(args):
    """
    Adds signer information (i.e. the certificates that actually signed the .apk, not *all* certificates in the .apk) to every row in the 'versions' table.
    Reads the current information from the 'meta' column, and create a 'meta_new' column, as to keep the old column as a backup
    """
    for namespace, level in [
        ("androguard", logging.ERROR)
    ]:
        logger = logging.getLogger(namespace)
        logger.setLevel(level)

    logging.basicConfig(
        format='%(asctime)s - %(name)s-10s - %(levelname)-8s %(message)s',
        level=logging.INFO
    )
    log = logging.getLogger("main")

    db_string = f"postgres://{args.postgres_user}:{args.postgres_password}@{args.postgres_host}:{args.postgres_port}/{args.postgres_db}"
    engine = create_engine(db_string)

    log.info("Fetching from database..")
    with engine.connect() as conn:
        # qry = f"SELECT id, meta FROM versions WHERE meta is not null AND {_column} is null"
        qry = f"SELECT id, meta FROM versions WHERE meta is not null LIMIT 10"
        result_set = conn.execute(qry)
    log.info("Fetched from database!")

    q_tasks = Queue()
    q_progress = Queue()

    processes = []

    # fill queue of tasks
    for idx, m in result_set:
        task = (idx, m)
        q_tasks.put(task)

    # create task processes
    for i in range(args.nprocesses):
        p = Process(target=update_analysis, args=(q_tasks, q_progress, db_string))
        processes.append(p)
        p.start()

    # create progress process
    p_progress = Process(target=progress, args=(q_progress, result_set.rowcount))
    p_progress.start()

    for p in processes:
        p.join()

    p_progress.terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Read "versions" table from database, and adds a "signers" field to the analysis in the "meta" column')
    parser.add_argument("--postgres-user", default="postgres")
    parser.add_argument("--postgres-password", default="postgres")
    parser.add_argument("--postgres-host", default="127.0.0.1")
    parser.add_argument("--postgres-port", default=5432)
    parser.add_argument("--postgres-db", default="postgres")
    parser.add_argument("--nprocesses", default=1, type=int)

    args = parser.parse_args()

    main(args)
