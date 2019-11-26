def version_name(orig, versions):
    """
    Finds a unique version name for the given version.
    Example: "1.0.0" -> "1.0.0-2", "1.0.0" -> "1.0.0-3"

    Args:
        orig: str
            version to find a new version from
        versions: dict
            dictionary whose keys are existings versions

    Returns: str

    """
    version = orig
    c = 1
    while version in versions:
        version = f"{version}-{c}"
    return version