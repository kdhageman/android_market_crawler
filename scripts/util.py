import json
import os
from json import JSONDecodeError

from tqdm import tqdm
import re


def jsons_from_file(f):
    """
    Reads all valid JSON strings from file f
    Allows reading files that do not separate JSON content by a newline character
    """
    jsons = []
    content = f.read()
    buf = ""
    bcount = 0
    for c in content:
        buf += c
        if c == "{":
            bcount += 1
        elif c == "}":
            bcount -= 1
            if bcount == 0:
                jsons.append(buf)
                buf = ""
    return jsons


def merge_jsons(jsons):
    """
    Merges a list of meta JSON strings
    Args:
        jsons: list of str

    Returns: str
    """
    res = {
        'versions': {}
    }
    for st in jsons:
        try:
            j = json.loads(st)
            res['meta'] = j['meta']  # meta field in result equals the last json string, and thus the last timestamp
            for version, dat in j['versions'].items():
                if version not in res['versions']:
                    res['versions'][version] = dat
        except JSONDecodeError:
            pass
    return res


def walk_spider_dir(spiderdir, spider, regex="meta.json"):
    """
    Generator
    """
    pkgs = [d for d in os.listdir(spiderdir) if os.path.isdir(os.path.join(spiderdir, d))]
    for pkg in tqdm(pkgs, desc=spider, total=len(pkgs)):
        walkdir = os.path.join(spiderdir, pkg)
        for root, dirs, files in os.walk(walkdir):
            for file in files:
                if re.search(regex, file):
                    fullpath = os.path.join(root, file)
                    yield fullpath


def merge(a, b):
    """
    Merges two dictionaries, where the values of b overwrite a
    Args:
        a: original dictionary
        b: dictionary that overwrites a

    Returns:
        merged dictionary
    """
    res = a.copy()
    for k, v in b.items():
        if isinstance(v, dict):
            res[k] = merge(a.get(k, {}), v)
        else:
            res[k] = v
    return res
