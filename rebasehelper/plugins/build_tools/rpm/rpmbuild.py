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
from rebasehelper.helpers.input_helper import InputHelper
from rebasehelper.helpers.path_helper import PathHelper
from rebasehelper.helpers.rpm_helper import RpmHelper
from rebasehelper.logger import CustomLogger
from rebasehelper.plugins.build_tools import RpmbuildTemporaryEnvironment
from rebasehelper.plugins.build_tools.rpm import BuildToolBase
from rebasehelper.exceptions import RebaseHelperError, BinaryPackageBuildError


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class Rpmbuild(BuildToolBase):  # pylint: disable=abstract-method
    """
    Class representing rpmbuild build tool.
    """

    ACCEPTS_OPTIONS: bool = True

    CMD: str = 'rpmbuild'

    @classmethod
    def _build_rpm(cls, srpm, workdir, results_dir, rpm_results_dir, builder_options=None):
        """Builds RPMs using rpmbuild

        Args:
            srpm: Path to SRPM.
            workdir: Path to working directory with rpmbuild directory structure.
            results_dir: Path to directory where logs will be placed.
            rpm_results_dir: Path to directory where RPMs will be placed.
            builder_options: Additional options for rpmbuild.

        Returns:
            Tuple, the first element is a list of paths to built RPMs,
            the second is a list of paths to logs.

        """
        logger.info("Building RPMs")
        output = os.path.join(results_dir, "build.log")

        cmd = [cls.CMD, '--rebuild', srpm]
        if builder_options is not None:
            cmd.extend(builder_options)
        ret = ProcessHelper.run_subprocess_cwd_env(cmd,
                                                   env={'HOME': workdir},
                                                   output_file=output)

        build_log_path = os.path.join(rpm_results_dir, 'build.log')
        logs = []
        for log in PathHelper.find_all_files(results_dir, '*.log'):
            logs.append(os.path.join(rpm_results_dir, os.path.basename(log)))

        if ret == 0:
            return [f for f in PathHelper.find_all_files(workdir, '*.rpm') if not f.endswith('.src.rpm')], logs
        # An error occurred, raise an exception
        raise BinaryPackageBuildError("Building RPMs failed!", results_dir, logfile=build_log_path, logs=logs)

    @classmethod
    def prepare(cls, spec, conf):
        """
        Checks if all build dependencies are installed. If not, asks user whether they should be installed.
        If he agrees, installs build dependencies using PolicyKit.

        :param spec: SpecFile object
        """
        if not RpmHelper.all_packages_installed(spec.header.requires):
            question = '\nSome build dependencies are missing. Do you want to install them now'
            if conf.non_interactive or InputHelper.get_message(question):
                if RpmHelper.install_build_dependencies(spec.path, assume_yes=conf.non_interactive) != 0:
                    raise RebaseHelperError('Failed to install build dependencies')

    @classmethod
    def build(cls, spec, results_dir, srpm, **kwargs):
        """
        Builds the RPMs using rpmbuild

        :param spec: SpecFile object
        :param results_dir: absolute path to DIR where results should be stored
        :param srpm: absolute path to SRPM
        :return: dict with:
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to build_logs
        """
        sources = spec.get_sources()
        patches = [p.path for p in spec.get_patches()]
        with RpmbuildTemporaryEnvironment(sources, patches, spec.path, results_dir) as tmp_env:
            env = tmp_env.env()
            tmp_dir = tmp_env.path()
            tmp_results_dir = env.get(RpmbuildTemporaryEnvironment.TEMPDIR_RESULTS)
            rpms, logs = cls._build_rpm(srpm, tmp_dir, tmp_results_dir, results_dir,
                                        builder_options=cls.get_builder_options(**kwargs))

        logger.info("Building RPMs finished successfully")

        # RPMs paths in results_dir
        rpms = [os.path.join(results_dir, os.path.basename(f)) for f in rpms]
        logger.verbose("Successfully built RPMs: '%s'", str(rpms))
        logger.verbose("logs: '%s'", str(logs))

        return dict(rpm=rpms, logs=logs)
