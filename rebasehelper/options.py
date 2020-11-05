# -*- coding: utf-8 -*-
#
# This tool helps you rebase your package to the latest version
# Copyright (C) 2013-2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
# Authors: Petr Hráček <phracek@redhat.com>
#          Tomáš Hozza <thozza@redhat.com>
#          Nikola Forró <nforro@redhat.com>
#          František Nečas <fifinecas@seznam.cz>

import os

from rebasehelper.types import Options
from rebasehelper.constants import CONFIG_PATH, CONFIG_FILENAME, CHANGES_PATCH
from rebasehelper.plugins.plugin_manager import plugin_manager


OPTIONS: Options = [
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
        "default": 0,
        "counter": True,
        "help": "be more verbose",
    },
    {
        "name": ["--color"],
        "choices": ["always", "never", "auto"],
        "default": "auto",
        "help": "colorize the output, defaults to %(default)s",
    },
    {
        "name": ["--background"],
        "choices": ["dark", "light", "auto"],
        "default": "auto",
        "help": "use color scheme for the given background, defaults to %(default)s",
    },
    {
        "name": ["--results-dir"],
        "help": "location where the rebase-helper-results directory will be created",
    },
    {
        "name": ["--workspace-dir"],
        "help": "location where the rebase-helper-workspace directory will be created",
    },
    # tool selection
    {
        "name": ["--buildtool"],
        "choices": plugin_manager.build_tools.get_all_plugins(),
        "available_choices": plugin_manager.build_tools.get_supported_plugins(),
        "default": plugin_manager.build_tools.get_default_plugins(True),
        "help": "build tool to use, defaults to %(default)s",
    },
    {
        "name": ["--srpm-buildtool"],
        "choices": plugin_manager.srpm_build_tools.get_all_plugins(),
        "available_choices": plugin_manager.srpm_build_tools.get_supported_plugins(),
        "default": plugin_manager.srpm_build_tools.get_default_plugins(True),
        "help": "SRPM build tool to use, defaults to %(default)s",
    },
    {
        "name": ["--pkgcomparetool"],
        "choices": plugin_manager.checkers.get_all_plugins(),
        "available_choices": plugin_manager.checkers.get_supported_plugins(),
        "nargs": "?",
        "const": [""],
        "default": plugin_manager.checkers.get_default_plugins(),
        "type": lambda s: s.split(','),
        "help": "set of tools to use for package comparison, defaults to "
                "%(default)s if available",
    },
    {
        "name": ["--outputtool"],
        "choices": plugin_manager.output_tools.get_all_plugins(),
        "available_choices": plugin_manager.output_tools.get_supported_plugins(),
        "default": plugin_manager.output_tools.get_default_plugins(True),
        "help": "tool to use for formatting rebase output, defaults to %(default)s",
    },
    {
        "name": ["--versioneer"],
        "choices": plugin_manager.versioneers.get_all_plugins(),
        "available_choices": plugin_manager.versioneers.get_supported_plugins(),
        "default": None,
        "help": "tool to use for determining latest upstream version",
    },
    # blacklists
    {
        "name": ["--versioneer-blacklist"],
        "choices": plugin_manager.versioneers.get_all_plugins(),
        "available_choices": plugin_manager.versioneers.get_supported_plugins(),
        "nargs": "?",
        "const": [""],
        "default": [],
        "type": lambda s: s.split(","),
        "help": "prevent specified versioneers from being run",
    },
    {
        "name": ["--spec-hook-blacklist"],
        "choices": plugin_manager.spec_hooks.get_all_plugins(),
        "available_choices": plugin_manager.spec_hooks.get_supported_plugins(),
        "nargs": "?",
        "const": [""],
        "default": [],
        "type": lambda s: s.split(","),
        "help": "prevent specified spec hooks from being run",
    },
    {
        "name": ["--build-log-hook-blacklist"],
        "choices": plugin_manager.build_log_hooks.get_all_plugins(),
        "available_choices": plugin_manager.build_log_hooks.get_supported_plugins(),
        "nargs": "?",
        "const": [""],
        "default": [],
        "type": lambda s: s.split(","),
        "help": "prevent specified build log hooks from being run"
    },
    # behavior control
    {
        "name": ["--bugzilla-id"],
        "metavar": "BUG_ID",
        "default": None,
        "help": "do a rebase based on Upstream Release Monitoring bugzilla"
    },
    {
        "name": ["--non-interactive"],
        "default": False,
        "switch": True,
        "dest": "non_interactive",
        "help": "do not interact with user",
    },
    {
        "name": ["--favor-on-conflict"],
        "choices": ["downstream", "upstream", "off"],
        "default": "off",
        "dest": "favor_on_conflict",
        "help": "favor downstream or upstream changes when conflicts appear",
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
        "name": ["--apply-changes"],
        "default": False,
        "switch": True,
        "help": "apply {} after a successful rebase".format(CHANGES_PATCH),
    },
    {
        "name": ["--disable-inapplicable-patches"],
        "default": False,
        "switch": True,
        "dest": "disable_inapplicable_patches",
        "help": "disable inapplicable patches in rebased SPEC file",
    },
    {
        "name": ["--keep-comments"],
        "default": False,
        "switch": True,
        "dest": "keep_comments",
        "help": "do not remove associated comments when removing patches from spec file",
    },
    {
        "name": ["--skip-version-check"],
        "default": False,
        "switch": True,
        "help": "force rebase even if current version is newer than requested version",
    },
    {
        "name": ["--update-sources"],
        "default": False,
        "switch": True,
        "help": "update \"sources\" file and upload new sources to lookaside cache",
    },
    {
        "name": ["--skip-upload"],
        "default": False,
        "switch": True,
        "help": "skip uploading new sources to lookaside cache",
    },
    {
        "name": ["--force-build-log-hooks"],
        "default": False,
        "switch": True,
        "help": "enforce running of build log hooks (even in non-interactive mode)",
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
        "name": ["--lookaside-cache-preset"],
        "choices": ["fedpkg", "rhpkg", "rhpkg-sha512"],
        "default": "fedpkg",
        "help": "use specified lookaside cache configuration preset, defaults to %(default)s",
    },
    {
        "name": ["--changelog-entry"],
        "default": "- New upstream release %{version}",
        "help": "text to use as changelog entry, can contain RPM macros, which will be expanded",
    },
    {
        "name": ["--no-changelog-entry"],
        "default": False,
        "switch": True,
        "help": "do not add a changelog entry at all",
    },
    {
        "name": ["--config-file"],
        "default": os.path.join(CONFIG_PATH, CONFIG_FILENAME),
        "help": "path to a configuration file, defaults to %(default)s",
    },
    {
        "name": ["-D", "--define"],
        "default": [],
        "append": True,
        "dest": "rpmmacros",
        "metavar": "'MACRO EXPR'",
        "help": "define an rpm macro, can be used multiple times",
    },
    # sources
    {
        "name": ["sources"],
        "metavar": "SOURCES",
        "nargs": "?",
        "default": None,
        "help": "version number or filename of the new source archive",
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
