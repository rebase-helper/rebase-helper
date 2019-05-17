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
import tempfile

from rebasehelper.temporary_environment import TemporaryEnvironment


class TestTemporaryEnvironment:
    """ TemporaryEnvironment class tests. """

    def test_with_statement(self):
        with TemporaryEnvironment() as temp:
            path = temp.path()
            assert path != ''
            assert os.path.exists(path)
            assert os.path.isdir(path)
            env = temp.env()
            assert env.get(temp.TEMPDIR, None) is not None
            assert env.get(temp.TEMPDIR, None) == path

        assert not os.path.exists(path)
        assert not os.path.isdir(path)

    def test_with_statement_exception(self):
        path = ''

        try:
            with TemporaryEnvironment() as temp:
                path = temp.path()
                raise RuntimeError()
        except RuntimeError:
            pass

        assert not os.path.exists(path)
        assert not os.path.isdir(path)

    def test_with_statement_callback(self):
        tmp_file, tmp_path = tempfile.mkstemp(text=True)
        os.close(tmp_file)

        def callback(**kwargs):
            path = kwargs.get(TemporaryEnvironment.TEMPDIR, '')
            assert path != ''
            with open(tmp_path, 'w') as f:
                f.write(path)

        with TemporaryEnvironment(exit_callback=callback) as temp:
            path = temp.path()

        with open(tmp_path, 'r') as f:
            assert f.read() == path

        os.unlink(tmp_path)

    def test_with_statement_callback_exception(self):
        path = ''
        tmp_file, tmp_path = tempfile.mkstemp(text=True)
        os.close(tmp_file)

        def callback(**kwargs):
            path = kwargs.get(TemporaryEnvironment.TEMPDIR, '')
            assert path != ''
            with open(tmp_path, 'w') as f:
                f.write(path)

        try:
            with TemporaryEnvironment(exit_callback=callback) as temp:
                path = temp.path()
                raise RuntimeError()
        except RuntimeError:
            pass

        with open(tmp_path, 'r') as f:
            assert f.read() == path

        os.unlink(tmp_path)
