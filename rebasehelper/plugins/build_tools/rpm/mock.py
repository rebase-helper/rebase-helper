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

import logging
import os
from typing import cast

from rebasehelper.helpers.process_helper import ProcessHelper
from rebasehelper.helpers.path_helper import PathHelper
from rebasehelper.logger import CustomLogger
from rebasehelper.plugins.build_tools import MockTemporaryEnvironment, check_mock_privileges, get_mock_logfile_path
from rebasehelper.plugins.build_tools.rpm import BuildToolBase
from rebasehelper.exceptions import BinaryPackageBuildError


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class Mock(BuildToolBase):  # pylint: disable=abstract-method
    """
    Class representing Mock build tool.
    """

    DEFAULT: bool = True
    ACCEPTS_OPTIONS: bool = True

    CMD: str = 'mock'

    @classmethod
    def _build_rpm(cls, srpm, results_dir, rpm_results_dir, root=None, arch=None, builder_options=None):
        """Builds RPMs using mock.

        Args:
            srpm: Path to SRPM.
            results_dir: Path to directory where logs will be placed.
            rpm_results_dir: Path to directory where rpms will be placed.
            root: Path to where chroot will be built
            arch: Target architectures for the build.
            builder_options: Additional options for mock.

        Returns:
            Tuple where first element is list of paths to built RPMs and
            the second element is list of paths to logs.

        """
        logger.info("Building RPMs")
        output = os.path.join(results_dir, "mock_output.log")

        cmd = [cls.CMD, '--old-chroot', '--rebuild', srpm, '--resultdir', results_dir]
        if root is not None:
            cmd.extend(['--root', root])
        if arch is not None:
            cmd.extend(['--arch', arch])
        if builder_options is not None:
            cmd.extend(builder_options)

        if not check_mock_privileges():
            cmd = ['pkexec'] + cmd

        ret = ProcessHelper.run_subprocess(cmd, output_file=output)
        logs = []
        for log in PathHelper.find_all_files(results_dir, '*.log'):
            logs.append(os.path.join(rpm_results_dir, os.path.basename(log)))

        if ret == 0:
            return [f for f in PathHelper.find_all_files(results_dir, '*.rpm') if not f.endswith('.src.rpm')], logs
        else:
            logfile = get_mock_logfile_path(ret, rpm_results_dir, tmp_path=results_dir)
        raise BinaryPackageBuildError("Building RPMs failed!", rpm_results_dir, logfile=logfile, logs=logs)

    @classmethod
    def build(cls, spec, results_dir, srpm, **kwargs):
        """
        Builds the RPMs using mock

        :param spec: SpecFile object
        :param results_dir: absolute path to directory where results will be stored
        :param srpm: absolute path to SRPM
        :param root: mock root used for building
        :param arch: architecture to build the RPM for
        :return: dict with:
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to logs
        """
        sources = spec.get_sources()
        patches = [p.path for p in spec.get_patches()]
        with MockTemporaryEnvironment(sources, patches, spec.path, results_dir) as tmp_env:
            env = tmp_env.env()
            tmp_results_dir = env.get(MockTemporaryEnvironment.TEMPDIR_RESULTS)
            rpms, logs = cls._build_rpm(srpm, tmp_results_dir, results_dir,
                                        builder_options=cls.get_builder_options(**kwargs))
            # remove SRPM - side product of building RPM
            tmp_srpm = PathHelper.find_first_file(tmp_results_dir, "*.src.rpm")
            if tmp_srpm is not None:
                os.unlink(tmp_srpm)

        logger.info("Building RPMs finished successfully")

        rpms = [os.path.join(results_dir, os.path.basename(f)) for f in rpms]
        logger.verbose("Successfully built RPMs: '%s'", str(rpms))
        logger.verbose("logs: '%s'", str(logs))

        return dict(rpm=rpms, logs=logs)
