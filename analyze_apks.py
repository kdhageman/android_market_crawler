import argparse
import os
import json

from apk.analysis import analyse
from util import walk_spider_dir


def main(args):
    with open(args.spidertxt, "r") as f:
        spiders = [l.strip() for l in f.readlines()]

    with open(args.outfile, "w") as outf:
        for spider in spiders:
            spiderdir = os.path.join(args.dir, spider)

            if os.path.exists(spiderdir):
                for path in walk_spider_dir(spiderdir, spider, regex=".*\.apk"):
                    with open(path, "r") as f:
                        a = analyse(f.name)
                        outf.write(json.dumps(a).strip() + "\n")
                        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze all APKs')
    parser.add_argument("--dir", help="Directory to traverse", default=".")
    parser.add_argument("--spidertxt", help="File which contains names of spiders", default="config/spider_list.txt")
    parser.add_argument("--outfile", help="Name of output file", default="apks.json")
    args = parser.parse_args()

    main(args)
