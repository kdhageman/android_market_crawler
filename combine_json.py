import argparse
import os
from tqdm import tqdm
import json

from util import jsons_from_file, merge_jsons


def walk_spider_dir(spiderdir, spider):
    """
    Generator
    """
    pkgs = [d for d in os.listdir(spiderdir) if os.path.isdir(os.path.join(spiderdir, d))]
    for pkg in tqdm(pkgs, desc=spider, total=len(pkgs)):
        walkdir = os.path.join(spiderdir, pkg)
        for root, dirs, files in os.walk(walkdir):
            for file in files:
                if file == "meta.json":
                    fullpath = os.path.join(root, file)
                    with open(fullpath, "r") as f:
                        yield f


def main(args):
    with open(args.spidertxt, "r") as f:
        spiders = [l.strip() for l in f.readlines()]

    all_merged = []
    for spider in spiders:
        spiderdir = os.path.join(args.dir, spider)

        if os.path.exists(spiderdir):
            for f in walk_spider_dir(spiderdir, spider):
                jsons = jsons_from_file(f)
                merged = merge_jsons(jsons)
                all_merged.append(merged)

    with open(args.outfile, "w") as f:
        for l in all_merged:
            json_line = json.dumps(l)
            f.write(json_line.strip() + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Aggregates JSON outputs from "run_spider.py" scripts')
    parser.add_argument("--dir", help="Directory to traverse", default=".")
    parser.add_argument("--outfile", help="Name of output file", default="out.json")
    parser.add_argument("--spidertxt", help="File which contains names of spiders", default="spider_list.txt")
    args = parser.parse_args()

    main(args)
