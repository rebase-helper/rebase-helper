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

from rebasehelper.plugins.build_tools import MockTemporaryEnvironment, check_mock_privileges
from rebasehelper.plugins.build_tools.srpm import SRPMBuildToolBase
from rebasehelper.exceptions import SourcePackageBuildError
from rebasehelper.helpers.path_helper import PathHelper
from rebasehelper.helpers.process_helper import ProcessHelper
from rebasehelper.logger import CustomLogger


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class Mock(SRPMBuildToolBase):

    CMD: str = 'mock'

    @classmethod
    def _build_srpm(cls, spec, workdir, results_dir, srpm_results_dir, srpm_builder_options):
        """Builds SRPM using mock.

        Args:
            spec: Path to SPEC file to build the SRPM from.
            workdir: Path to working directory with rpmbuild directory structure.
            results_dir: Path to directory where logs will be placed.
            srpm_results_dir: Path to directory where SRPM will be placed.
            srpm_builder_options: Additional mock options.

        Returns:
            Tuple, the first element is path to SRPM, the second is a list of paths
            to logs.

        """
        logger.info("Building SRPM")
        spec_loc = os.path.dirname(spec)
        output = os.path.join(results_dir, "build.log")

        path_to_sources = os.path.join(workdir, 'SOURCES')

        cmd = [cls.CMD, '--isolation', 'simple', '--buildsrpm']
        if srpm_builder_options is not None:
            cmd.extend(srpm_builder_options)
        cmd.extend(['--spec', spec])
        cmd.extend(['--sources', path_to_sources])
        cmd.extend(['--resultdir', results_dir])

        if not check_mock_privileges():
            cmd = ['pkexec'] + cmd

        ret = ProcessHelper.run_subprocess_cwd_env(cmd,
                                                   cwd=spec_loc,
                                                   env={'HOME': workdir},
                                                   output_file=output)

        build_log_path = os.path.join(srpm_results_dir, 'build.log')
        mock_log_path = os.path.join(srpm_results_dir, 'mock_output.log')
        root_log_path = os.path.join(srpm_results_dir, 'root.log')
        logs = []
        for log in PathHelper.find_all_files(results_dir, '*.log'):
            logs.append(os.path.join(srpm_results_dir, os.path.basename(log)))

        if ret == 0:
            return PathHelper.find_first_file(workdir, '*.src.rpm'), logs
        if ret == 1:
            if not os.path.exists(build_log_path) and os.path.exists(mock_log_path):
                logfile = mock_log_path
            else:
                logfile = build_log_path
        else:
            logfile = root_log_path
        raise SourcePackageBuildError("Building SRPM failed!", logfile=logfile, logs=logs)

    @classmethod
    def build(cls, spec, results_dir, **kwargs):
        """
        Build SRPM with chosen SRPM Build Tool

        :param spec: SpecFile object
        :param results_dir: absolute path to DIR where results should be stored
        :return: absolute path to SRPM, list with absolute paths to logs
        """
        sources = spec.get_sources()
        patches = [p.path for p in spec.get_patches()]
        with MockTemporaryEnvironment(sources, patches, spec.path, results_dir) as tmp_env:
            srpm_builder_options = cls.get_srpm_builder_options(**kwargs)

            env = tmp_env.env()
            tmp_dir = tmp_env.path()
            tmp_spec = env.get(MockTemporaryEnvironment.TEMPDIR_SPEC)
            tmp_results_dir = env.get(
                MockTemporaryEnvironment.TEMPDIR_RESULTS)

            srpm, logs = cls._build_srpm(tmp_spec, tmp_dir, tmp_results_dir, results_dir,
                                         srpm_builder_options=srpm_builder_options)

        logger.info("Building SRPM finished successfully")

        # srpm path in results_dir
        srpm = os.path.join(results_dir, os.path.basename(srpm))
        logger.verbose("Successfully built SRPM: '%s'", str(srpm))
        logger.verbose("logs: '%s'", str(logs))

        return dict(srpm=srpm, logs=logs)
