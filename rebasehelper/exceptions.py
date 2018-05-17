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


class RebaseHelperError(Exception):
    """
    Class representing Error raised inside rebase-helper after intentionally
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


class CheckerNotFoundError(RuntimeError):
    """
    Error indicating failure unable to find checker binary.
    """
    pass


class DownloadError(Exception):
    """
    Exception indicating that download of a file failed.
    """
    pass


class ParseError(Exception):

    pass


class LookasideCacheError(Exception):

    """Exception indicating a problem accessing lookaside cache"""

    pass
