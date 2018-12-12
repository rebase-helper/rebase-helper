# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
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
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>

import pkg_resources
import six

from rebasehelper.logger import logger
from rebasehelper.results_store import results_store


class BaseBuildLogHook(object):
    """Base class for a build log hook."""

    @classmethod
    def get_name(cls):
        raise NotImplementedError()

    @classmethod
    def get_categories(cls):
        raise NotImplementedError()

    @classmethod
    def format(cls, data):
        """Formats build log hook output to a readable text form."""
        raise NotImplementedError()

    @classmethod
    def run(cls, spec_file, rebase_spec_file, results_dir, **kwargs):
        raise NotImplementedError()


class BuildLogHookRunner(object):
    def __init__(self):
        self.build_log_hooks = {}
        for entrypoint in pkg_resources.iter_entry_points('rebasehelper.build_log_hooks'):
            try:
                build_log_hook = entrypoint.load()
            except ImportError:
                # silently skip broken plugin
                continue
            try:
                self.build_log_hooks[build_log_hook.get_name()] = build_log_hook
            except (AttributeError, NotImplementedError):
                # silently skip broken plugin
                continue

    def run(self, spec_file, rebase_spec_file, non_interactive, force_build_log_hooks, **kwargs):
        """Runs all build log hooks.

        Args:
            spec_file (rebasehelper.specfile.SpecFile): Original SpecFile object.
            rebase_spec_file (rebasehelper.specfile.SpecFile): Rebased SpecFile object.
            kwargs (dict): Keyword arguments from instance of Application.

        Returns:
            bool: Whether build log hooks made some changes to the SPEC file.

        """
        changes_made = False
        if not non_interactive or force_build_log_hooks:
            blacklist = kwargs.get('build_log_hook_blacklist', [])
            for name, build_log_hook in six.iteritems(self.build_log_hooks):
                if name in blacklist:
                    continue
                categories = build_log_hook.get_categories()
                if not categories or spec_file.category in categories:
                    logger.info('Running %s build log hook.', name)
                    result = build_log_hook.run(spec_file, rebase_spec_file, **kwargs) or {}
                    results_store.set_build_log_hooks_result(name, result)
                    if result:
                        changes_made = True
        return changes_made

    def get_supported_tools(self):
        return self.build_log_hooks.keys()

    @staticmethod
    def get_all_tools():
        return [entrypoint.name for entrypoint in pkg_resources.iter_entry_points('rebasehelper.build_log_hooks')]


# Global instance of BuildLogHookRunner. It is enough to load it once per application run.
build_log_hook_runner = BuildLogHookRunner()
