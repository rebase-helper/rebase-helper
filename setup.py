#!/usr/bin/python
# -*- coding: utf-8 -*-


import os
import distutils.command.sdist
from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES
from scripts.include import *

project_name            = "rebase-helper"
project_dirs            = ["rebase-helper"]
project_url             = "http://github.com/phracek/rebase-helper"
project_author          = "Red Hat, Inc."
project_author_email    = "phracek@redhat.com"
project_description     = "Rebase Helper"
package_name            = "%s" % project_name
package_module_name     = project_name
package_version         = [ 0, 1, 1, "", "" ]


script_files    = []

data_files  = {
        "/usr/bin": [
            "rebaser/rebase-helper.py"
        ],
}

# override default tarball format with bzip2
distutils.command.sdist.sdist.default_format = {'posix':'bztar',}

if os.path.isdir(".git"):
    # we're building from a git repo -> store version tuple to __init__.py
    if package_version[3] == "git":
        force = True
        git_version = get_git_version(os.path.dirname(__file__))
        git_date = get_git_date(os.path.dirname(__file__))
        package_version[4] = "%s.%s" % (git_date,git_version)

    for i in project_dirs:
        file_name = os.path.join(i, "version.py")
        write_version(file_name, package_version)

# read package version from the module
package_module = __import__(project_dirs[0] + ".version")
package_version = get_version(package_module)
packages = get_packages(project_dirs)

root_dir = os.path.dirname(__file__)
if root_dir != "":
    os.chdir(root_dir)

for scheme in INSTALL_SCHEMES.values():
    scheme["data"] = scheme["purelib"]

setup (
        name            = package_name,
        version         = package_version.replace(" ", "_").replace("-","_"),
        url             = project_url,
        author          = project_author,
        author_email    = project_author_email,
        description     = project_description,
        packages        = packages,
        data_files      = data_files.items(),
        scripts         = script_files,
)
