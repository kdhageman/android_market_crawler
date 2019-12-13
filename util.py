import json

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
        j = json.loads(st)
        res['meta'] = j['meta'] # meta field in result equals the last json string, and thus the last timestamp
        for version, dat in j['versions'].items():
            if version not in res['versions']:
                res['versions'][version] = dat
    return res
