import argparse
import shutil

from tqdm import tqdm


def remove_dirs(dirs):
    for d in tqdm(dirs):
        try:
            shutil.rmtree(d)
        except FileNotFoundError:
            pass


def main(args):
    with open(args.infile, "r") as f:
        dirs_to_remove = [l.strip() for l in f.readlines()]
    remove_dirs(dirs_to_remove)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Removes all directories specified in input file')
    parser.add_argument("--infile", help="Input file of directories to remove", required=True)
    args = parser.parse_args()

    main(args)
