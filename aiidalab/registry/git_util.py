from urllib.parse import urlparse

from dulwich.client import get_transport_and_path_from_url


def get_git_branches(git_url):
    t, p = get_transport_and_path_from_url(git_url)
    branches = t.get_refs(p)
    res = {}
    for key, value in branches.items():
        res[key.decode("utf-8")] = value.decode("utf-8")
    return res


def get_git_author(git_url):
    return urlparse(git_url).path.split("/")[1]
