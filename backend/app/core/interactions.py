"""Canonical endpoints and versioning for undirected interaction datasets."""


def undirected_pair(u: str, v: str) -> tuple[str, str]:
    return (u, v) if u <= v else (v, u)


def undirected_dataset_version(version: str) -> str:
    suffix = "-undirected-v1"
    base, separator, grain = version.rpartition(":")
    if separator and grain in ("weekly", "monthly"):
        return undirected_dataset_version(base) + separator + grain
    return version if version.endswith(suffix) else version + suffix
