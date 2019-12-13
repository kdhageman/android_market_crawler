import argparse
import os
import json

import sys

sys.path.append(os.path.abspath('.'))
from scripts.util import jsons_from_file, merge_jsons, walk_spider_dir


def main(args):
    with open(args.spidertxt, "r") as f:
        spiders = [l.strip() for l in f.readlines()]

    with open(args.outfile, "w") as outf:
        for spider in spiders:
            spiderdir = os.path.join(args.dir, spider)

            if os.path.exists(spiderdir):
                for path in walk_spider_dir(spiderdir, spider):
                    with open(path, "r") as f:
                        jsons = jsons_from_file(f)
                        merged = merge_jsons(jsons)
                        json_line = json.dumps(merged)
                        outf.write(json_line.strip() + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Aggregates JSON outputs from "run_spider.py" scripts')
    parser.add_argument("--dir", help="Directory to traverse", default=".")
    parser.add_argument("--outfile", help="Name of output file", default="meta.combined.json")
    parser.add_argument("--spidertxt", help="File which contains names of spiders", default="config/spider_list.txt")
    args = parser.parse_args()

    main(args)
