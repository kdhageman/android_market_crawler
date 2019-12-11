import argparse
import os
from tqdm import tqdm


def last_json_from_file(f):
    """
    Reads last JSON from file f
    Allows reading files that do not separate JSON content by a newline character
    """
    content = f.read()
    buf = ""
    bcount = 0
    for i in range(len(content) - 1, -1, -1):
        c = content[i]
        buf = c + buf
        if c == "}":
            bcount += 1
        elif c == "{":
            bcount -= 1
            if bcount == 0:
                # last bracket
                return buf
    return ""

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

    json_lines = []
    for spider in spiders:
        spiderdir = os.path.join(args.dir, spider)

        if os.path.exists(spiderdir):
            for f in walk_spider_dir(spiderdir, spider):
                json_line = last_json_from_file(f)
                json_lines.append(json_line)

    with open(args.outfile, "w") as f:
        for json_line in json_lines:
            f.write(json_line.strip() + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Aggregates JSON outputs from "run_spider.py" scripts')
    parser.add_argument("--dir", help="Directory to traverse", default=".")
    parser.add_argument("--outfile", help="Name of output file", default="out.json")
    parser.add_argument("--spidertxt", help="File which contains names of spiders", default="spider_list.txt")
    args = parser.parse_args()

    main(args)
