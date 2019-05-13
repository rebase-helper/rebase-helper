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


class RebaseHelperError(Exception):
    """Class representing Error raised inside rebase-helper after intentionally
    catching some expected and well known exception/error.

    """

    def __init__(self, *args, **kwargs):
        """Constructor of RebaseHelperError"""
        super(RebaseHelperError, self).__init__()
        if not args:
            self.msg = None
        elif len(args) > 1:
            self.msg = args[0] % args[1:]
        else:
            self.msg = args[0]
        self.logfiles = kwargs.get('logfiles')

    def __str__(self):
        return str(self.msg) if self.msg else ''


class CheckerNotFoundError(RuntimeError):
    """Error indicating not being able to find checker binary."""


class DownloadError(Exception):
    """Exception indicating that download of a file failed."""


class ParseError(Exception):
    pass


class LookasideCacheError(Exception):
    """Exception indicating a problem in accessing lookaside cache."""


class SourcePackageBuildError(RuntimeError):
    """Error indicating failure during the build of source package"""

    def __init__(self, *args, **kwargs):
        """Constructor of SourcePackageBuildError.

        Args:
            *args: List of arguments to be stored in the exception instance.
            **kwargs: Keyword arguments containing paths to logs with errors.

        """
        super(SourcePackageBuildError, self).__init__()
        self.args = args
        self.logfile = kwargs.get('logfile')


class BinaryPackageBuildError(RuntimeError):
    """Error indicating failure during the build of binary package."""

    def __init__(self, *args, **kwargs):
        """Constructor of BinaryPackageBuildError.

        Args:
            *args: List of arguments to be stored in the exception instance.
            **kwargs: Keyword arguments containing paths to logs with errors.

        """
        super(BinaryPackageBuildError, self).__init__()
        self.args = args
        # Return code obtained from koji only at this time
        self.return_code = kwargs.get('return_code')
        self.logfile = kwargs.get('logfile')
