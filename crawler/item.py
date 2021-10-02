class NoPkgError(Exception):
    pass

def pkg_name_from_result(result):
    meta = result["meta"]
    pkg_name = meta.get("pkg_name", None)
    if pkg_name:
        return pkg_name

    for version, d in result["versions"].items():
        analysis = d.get("analysis", None)
        if analysis:
            pkg_name = analysis.get("pkg_name")
            if pkg_name:
                return pkg_name

    raise NoPkgError
