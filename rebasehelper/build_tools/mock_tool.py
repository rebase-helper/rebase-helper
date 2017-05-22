# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation; either version 2 of the License, or
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

import os

from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger
from rebasehelper.utils import PathHelper
from rebasehelper.build_helper import BuildTemporaryEnvironment
from rebasehelper.build_helper import BuildToolBase
from rebasehelper.build_helper import BinaryPackageBuildError


class MockTemporaryEnvironment(BuildTemporaryEnvironment):
    """
    Class representing temporary environment for MockBuildTool.
    """

    def _create_directory_structure(self):
        # create directory structure
        for dir_name in ['SOURCES', 'SPECS', 'RESULTS']:
            self._env[self.TEMPDIR + '_' + dir_name] = os.path.join(
                self._env[self.TEMPDIR], dir_name)
            logger.debug("Creating '%s'",
                         self._env[self.TEMPDIR + '_' + dir_name])
            os.makedirs(self._env[self.TEMPDIR + '_' + dir_name])


class MockBuildTool(BuildToolBase):
    """
    Class representing Mock build tool.
    """

    CMD = "mock"
    DEFAULT = True
    logs = []

    @classmethod
    def _build_rpm(cls, srpm, results_dir, root=None, arch=None, builder_options=None):
        """Build RPM using mock."""
        logger.info("Building RPMs")
        output = os.path.join(results_dir, "mock_output.log")

        cmd = [cls.CMD, '--rebuild', srpm, '--resultdir', results_dir]
        if root is not None:
            cmd.extend(['--root', root])
        if arch is not None:
            cmd.extend(['--arch', arch])
        if builder_options is not None:
            cmd.extend(builder_options)

        ret = ProcessHelper.run_subprocess(cmd, output=output)

        if ret != 0:
            return None
        else:
            return [f for f in PathHelper.find_all_files(results_dir, '*.rpm') if not f.endswith('.src.rpm')]

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def get_build_tool_name(cls):
        return cls.CMD

    @classmethod
    def is_default(cls):
        return cls.DEFAULT

    @classmethod
    def accepts_options(cls):
        return True

    @classmethod
    def creates_tasks(cls):
        return False

    @classmethod
    def build(cls, spec, sources, patches, results_dir, root=None, arch=None, **kwargs):
        """
        Builds the SRPM and RPM using mock

        :param spec: absolute path to a SPEC file
        :param sources: list with absolute paths to SOURCES
        :param patches: list with absolute paths to PATCHES
        :param results_dir: absolute path to directory where results will be stored
        :param root: mock root used for building
        :param arch: architecture to build the RPM for
        :return: dict with:
                 'srpm' -> absolute path to SRPM
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to logs
        """
        # build SRPM
        srpm, cls.logs = cls._build_srpm(spec, sources, patches, results_dir)

        # build RPMs
        rpm_results_dir = os.path.join(results_dir, "RPM")
        with MockTemporaryEnvironment(sources, patches, spec, rpm_results_dir) as tmp_env:
            env = tmp_env.env()
            tmp_results_dir = env.get(MockTemporaryEnvironment.TEMPDIR_RESULTS)
            rpms = cls._build_rpm(srpm, tmp_results_dir, builder_options=cls.get_builder_options(**kwargs))
            # remove SRPM - side product of building RPM
            tmp_srpm = PathHelper.find_first_file(tmp_results_dir, "*.src.rpm")
            if tmp_srpm is not None:
                os.unlink(tmp_srpm)

        if rpms is None:
            # We need to be inform what directory to analyze and what spec file failed
            cls.logs.extend([l for l in PathHelper.find_all_files(rpm_results_dir, '*.log')])
            raise BinaryPackageBuildError("Building RPMs failed!", rpm_results_dir, spec)
        else:
            logger.info("Building RPMs finished successfully")

        rpms = [os.path.join(rpm_results_dir, os.path.basename(f)) for f in rpms]
        logger.debug("Successfully built RPMs: '%s'", str(rpms))

        # gather logs
        cls.logs.extend([l for l in PathHelper.find_all_files(rpm_results_dir, '*.log')])
        logger.debug("logs: '%s'", str(cls.logs))

        return {'srpm': srpm,
                'rpm': rpms,
                'logs': cls.logs}

    @classmethod
    def get_logs(cls):
        return {'logs': cls.logs}
