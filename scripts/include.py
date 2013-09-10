# -*- coding: utf-8 -*-


import os
import subprocess


__all__ = (
    "get_module",
    "get_packages",
    "get_files",
    "get_git_date",
    "get_git_version",
    "get_version",
    "write_version",
)


def get_module(path):
    """Convert path to module name."""
    result = []
    head = path
    while head != "":
        head, tail = os.path.split(head)
        result.append(tail)
    return ".".join(reversed(result))


def get_packages(project_dirs):
    """Return packages found in project dirs."""
    packages = []

    for project_dir in project_dirs:
        for dirpath, dirnames, filenames in os.walk(project_dir):
            # ignore dirnames that start with "."
            dir_name = os.path.basename(dirpath)

            if dir_name.startswith(".") or dir_name == "CVS":
                continue

            if "__init__.py" in filenames:
                packages.append(get_module(dirpath))
                continue

    return packages


def get_files(module_name, top_dir):
    """Return list of all files under top_dir."""
    result = []

    module = __import__(module_name)
    module_dir = os.path.dirname(module.__file__)

    for root, dirs, files in os.walk(os.path.join(module_dir, top_dir)):
        for fn in files:
            result.append(os.path.join(top_dir, root, fn)[len(module_dir)+1:])
    return result


def get_git_date(git_repo_path):
    """Return git last commit date in YYYYMMDD format."""
    cmd = "git log -n 1 --pretty=format:%ci"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Not a git repository: %s" % git_repo_path)
    lines = proc.stdout.read().strip().split("\n")
    return lines[0].split(" ")[0].replace("-", "")


def get_git_version(git_repo_path):
    """Return git abbreviated tree hash."""
    cmd = "git log -n 1 --pretty=format:%t"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Not a git repository: %s" % git_repo_path)
    lines = proc.stdout.read().strip().split("\n")
    return lines[0]


def get_version(module):
    """Get version from the module."""
    version_tuple = module.version.VERSION

    if len(version_tuple) != 5:
        raise ValueError("Tuple with 5 records expected.")

    if version_tuple[3] in ("", "final"):
        return "%s.%s.%s" % (version_tuple[0], version_tuple[1], version_tuple[2])

    if version_tuple[4] == "":
        return "%s.%s.%s.%s" % (version_tuple[0], version_tuple[1], version_tuple[2], version_tuple[3])

    return "%s.%s.%s.%s.%s" % (version_tuple[0], version_tuple[1], version_tuple[2], version_tuple[3], version_tuple[4])


def write_version(file_name, version_tuple):
    fo = open(file_name, "w")
    fo.write('VERSION = (%s, %s, %s, "%s", "%s")\n' % tuple(version_tuple))
    fo.close()
