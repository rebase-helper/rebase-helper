# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

from rebasehelper.build_helper import Builder, SRPMBuilder
from rebasehelper.checker import checkers_runner
from rebasehelper.output_tool import BaseOutputTool
from rebasehelper.versioneer import versioneers_runner


OPTIONS = [
    # basic
    {
        "name": ["--version"],
        "default": False,
        "switch": True,
        "help": "show rebase-helper version and exit",
    },
    # output control
    {
        "name": ["-v", "--verbose"],
        "default": False,
        "switch": True,
        "help": "be more verbose (recommended)",
    },
    {
        "name": ["--color"],
        "choices": ["always", "never", "auto"],
        "default": "auto",
        "help": "colorize the output, defaults to %(default)s",
    },
    {
        "name": ["--results-dir"],
        "help": "directory where rebase-helper output will be stored",
    },
    # action control
    [
        {
            "name": ["-p", "--patch-only"],
            "default": False,
            "switch": True,
            "help": "only apply patches",
        },
        {
            "name": ["-b", "--build-only"],
            "default": False,
            "switch": True,
            "help": "only build SRPM and RPMs",
        },
        {
            "name": ["--comparepkgs-only"],
            "default": False,
            "dest": "comparepkgs",
            "metavar": "COMPAREPKGS_DIR",
            "help": "compare already built packages, %(metavar)s must be a directory "
                    "with the following structure: <dir_name>/{old,new}/RPM",
        },
    ],
    {
        "name": ["-c", "--continue"],
        "default": False,
        "switch": True,
        "dest": "cont",
        "help": "continue previously interrupted rebase",
    },
    # tool selection
    {
        "name": ["--buildtool"],
        "choices": Builder.get_supported_tools(),
        "default": Builder.get_default_tool(),
        "help": "build tool to use, defaults to %(default)s",
    },
    {
        "name": ["--srpm-buildtool"],
        "choices": SRPMBuilder.get_supported_tools(),
        "default": SRPMBuilder.get_default_tool(),
        "help": "SRPM build tool to use, defaults to %(default)s",
    },
    {
        "name": ["--pkgcomparetool"],
        "choices": checkers_runner.get_supported_tools(),
        "default": checkers_runner.get_default_tools(),
        "type": lambda s: s.split(','),
        "help": "set of tools to use for package comparison, defaults to %(default)s",
    },
    {
        "name": ["--outputtool"],
        "choices": BaseOutputTool.get_supported_tools(),
        "default": BaseOutputTool.get_default_tool(),
        "help": "tool to use for formatting rebase output, defaults to %(default)s",
    },
    {
        "name": ["--versioneer"],
        "choices": versioneers_runner.get_available_versioneers(),
        "default": None,
        "help": "tool to use for determining latest upstream version",
    },
    # behavior control
    {
        "name": ["--non-interactive"],
        "default": False,
        "switch": True,
        "dest": "non_interactive",
        "help": "do not interact with user",
    },
    {
        "name": ["--not-download-sources"],
        "default": False,
        "switch": True,
        "help": "do not download sources",
    },
    {
        "name": ["-w", "--keep-workspace"],
        "default": False,
        "switch": True,
        "help": "do not remove workspace directory after finishing",
    },
    {
        "name": ["--disable-inapplicable-patches"],
        "default": False,
        "switch": True,
        "dest": "disable_inapplicable_patches",
        "help": "disable inapplicable patches in rebased SPEC file",
    },
    {
        "name": ["--get-old-build-from-koji"],
        "default": False,
        "switch": True,
        "help": "do not build old sources, download latest build from Koji instead",
    },
    {
        "name": ["--skip-version-check"],
        "default": False,
        "switch": True,
        "help": "force rebase even if current version is newer than requested version",
    },
    # remote builder options
    {
        "name": ["--builds-nowait"],
        "default": False,
        "switch": True,
        "help": "do not wait for remote builds to finish",
    },
    {
        "name": ["--build-tasks"],
        "dest": "build_tasks",
        "metavar": "OLD_TASK,NEW_TASK",
        "type": lambda s: s.split(','),
        "help": "comma-separated remote build task ids",
    },
    # additional local builder options
    {
        "name": ["--builder-options"],
        "default": None,
        "metavar": "BUILDER_OPTIONS",
        "help": "enable arbitrary local builder option(s), enclose %(metavar)s in quotes "
                "to pass more than one",
    },
    {
        "name": ["--srpm-builder-options"],
        "default": None,
        "metavar": "SRPM_BUILDER_OPTIONS",
        "help": "enable arbitrary local srpm builder option(s), enclose %(metavar)s in quotes "
                "to pass more than one",
    },
    # misc
    {
        "name": ["--changelog-entry"],
        "default": "- New upstream release %{version}",
        "help": "text to use as changelog entry, can contain RPM macros, which will be expanded",
    },
    {
        "name": ["--conf"],
        "help": "custom path to configuration file",
    },
    # sources
    {
        "name": ["sources"],
        "metavar": "SOURCES",
        "nargs": "?",
        "default": None,
        "help": "new upstream sources",
    },
]


def traverse_options(options):
    group_index = 0
    for opt in options:
        if isinstance(opt, list):
            for inner_opt in opt:
                yield dict(group=group_index, **inner_opt)
            group_index += 1
        else:
            yield opt
