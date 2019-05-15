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

import shutil

from rebasehelper.logger import logger
from rebasehelper.helpers.path_helper import PathHelper


class TemporaryEnvironment:

    """Class representing a temporary environment (directory) that can be used as a workspace.

    Works as a context manager.

    """

    TEMPDIR: str = 'TEMPDIR'

    def __init__(self, exit_callback=None):
        self._env = {}
        self._exit_callback = exit_callback

    def __enter__(self):
        self._env[self.TEMPDIR] = PathHelper.get_temp_dir()
        logger.debug("Created environment in '%s'", self.path())
        return self

    def __exit__(self, *args):
        # run callback before removing the environment
        try:
            self._exit_callback(**self.env())
        except TypeError:
            pass
        else:
            logger.debug("Exit callback executed successfully")

        shutil.rmtree(self.path(), onerror=lambda func, path, excinfo: shutil.rmtree(path))
        logger.debug("Destroyed environment in '%s'", self.path())

    def __str__(self):
        return "<TemporaryEnvironment path='%s'>", self.path()

    def path(self):
        """Gets the path to the temporary environment.

        Returns:
            str: Absolute path to the temporary environment.

        """
        return self._env.get(self.TEMPDIR, '')

    def env(self):
        """Gets a copy of _env dictionary.

        Returns:
            dict: Copy of _env dictionary.

        """
        return self._env.copy()
