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
import subprocess
import tempfile

from rebasehelper.constants import SYSTEM_ENCODING
from rebasehelper.logger import logger


class ProcessHelper:

    """Class for executing subprocesses."""

    DEV_NULL: str = os.devnull

    @staticmethod
    def run_subprocess(cmd, input_file=None, output_file=None, ignore_stderr=False):
        """Runs the specified command in a subprocess.

        Args:
            cmd (iterable): A sequence of program arguments.
            input_file (str, typing.BytesIO): File to read the input from.
            output_file (str, typing.BytesIO): File to write the output of the command to.
            ignore_stderr (bool): Whether to ignore stderr output.

        Returns:
            int: Exit code of the subprocess.

        """
        return ProcessHelper.run_subprocess_cwd(cmd,
                                                input_file=input_file,
                                                output_file=output_file,
                                                ignore_stderr=ignore_stderr)

    @staticmethod
    def run_subprocess_cwd(cmd, cwd=None, input_file=None, output_file=None, ignore_stderr=False, shell=False):
        """Runs the specified command in a subprocess in a different working directory.

        Args:
            cmd (iterable): A sequence of program arguments.
            cwd (str): Working directory for the command.
            input_file (str, typing.BytesIO): File to read the input from.
            output_file (str, typing.BytesIO): File to write the output of the command to.
            ignore_stderr (bool): Whether to ignore stderr output.
            shell (bool): Whether to run the command in a shell.

        Returns:
            int: Exit code of the subprocess.

        """
        return ProcessHelper.run_subprocess_cwd_env(cmd,
                                                    cwd=cwd,
                                                    input_file=input_file,
                                                    output_file=output_file,
                                                    ignore_stderr=ignore_stderr,
                                                    shell=shell)

    @staticmethod
    def run_subprocess_env(cmd, env=None, input_file=None, output_file=None, ignore_stderr=False, shell=False):
        """Runs the specified command in a subprocess with a redefined environment.

        Args:
            cmd (iterable): A sequence of program arguments.
            env (dict): Environment variables for the new process.
            input_file (str, typing.BytesIO): File to read the input from.
            output_file (str, typing.BytesIO): File to write the output of the command to.
            ignore_stderr (bool): Whether to ignore stderr output.
            shell (bool): Whether to run the command in a shell.

        Returns:
            int: Exit code of the subprocess.

        """
        return ProcessHelper.run_subprocess_cwd_env(cmd,
                                                    env=env,
                                                    input_file=input_file,
                                                    output_file=output_file,
                                                    ignore_stderr=ignore_stderr,
                                                    shell=shell)

    @staticmethod
    def run_subprocess_cwd_env(cmd, cwd=None, env=None, input_file=None, output_file=None, ignore_stderr=False,
                               shell=False):
        """Runs the specified command in a subprocess in a different working directory with a redefined environment.

        Args:
            cmd (iterable): A sequence of program arguments.
            cwd (str): Working directory for the command.
            env (dict): Environment variables for the new process.
            input_file (str, typing.BytesIO): File to read the input from.
            output_file (str, typing.BytesIO): File to write the output of the command to.
            ignore_stderr (bool): Whether to ignore stderr output.
            shell (bool): Whether to run the command in a shell.

        Returns:
            int: Exit code of the subprocess.

        """
        close_out_file = False
        close_in_file = False

        logger.debug("cmd=%s, cwd=%s, env=%s, input_file=%s, output_file=%s, shell=%s",
                     str(cmd), str(cwd), str(env), str(input_file), str(output_file), str(shell))

        # write the output to a file/file-like object?
        try:
            out_file = open(output_file, 'wb')
        except TypeError:
            out_file = output_file
        else:
            close_out_file = True

        # read the input from a file/file-like object?
        try:
            in_file = open(input_file, 'r')
        except TypeError:
            in_file = input_file
        else:
            close_in_file = True

        # we need to rewind the file object pointer to the beginning
        try:
            in_file.seek(0)
        except AttributeError:
            # we don't mind - in_file might be None
            pass

        # check if in_file has fileno() method - which is needed for Popen
        try:
            in_file.fileno()
        except (AttributeError, OSError):
            spooled_in_file = tempfile.SpooledTemporaryFile(mode='w+b')
            try:
                in_data = in_file.read()
            except AttributeError:
                spooled_in_file.close()
            else:
                spooled_in_file.write(in_data.encode(SYSTEM_ENCODING))
                spooled_in_file.seek(0)
                in_file = spooled_in_file
                close_in_file = True

        # need to change environment variables?
        if env is not None:
            local_env = os.environ.copy()
            local_env.update(env)
        else:
            local_env = None

        if out_file:
            stdout = subprocess.PIPE
        else:
            stdout = None

        with open(os.devnull, 'wb') as devnull:
            sp = subprocess.Popen(cmd,
                                  stdin=in_file,
                                  stdout=stdout,
                                  stderr=devnull if ignore_stderr else subprocess.STDOUT,
                                  cwd=cwd,
                                  env=local_env,
                                  shell=shell)

        if out_file is not None:
            # read the output
            for line in sp.stdout:
                try:
                    out_file.write(line.decode(SYSTEM_ENCODING))
                except TypeError:
                    out_file.write(line)
            # TODO: Need to figure out how to send output to stdout (without logger) and to logger
            # else:
            #   logger.debug(line.rstrip("\n"))

        # we need to rewind the file object pointer to the beginning
        try:
            out_file.seek(0)
        except AttributeError:
            # we don't mind - out_file might be None
            pass

        if close_out_file:
            out_file.close()

        if close_in_file:
            in_file.close()

        sp.wait()

        logger.debug("subprocess exited with return code %s", str(sp.returncode))

        return sp.returncode
