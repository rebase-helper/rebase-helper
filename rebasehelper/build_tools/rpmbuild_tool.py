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
from rebasehelper.utils import RpmHelper
from rebasehelper.utils import ConsoleHelper
from rebasehelper.build_helper import RpmbuildTemporaryEnvironment
from rebasehelper.build_helper import BuildToolBase
from rebasehelper.build_helper import BinaryPackageBuildError
from rebasehelper.exceptions import RebaseHelperError


class RpmbuildBuildTool(BuildToolBase):
    """
    Class representing rpmbuild build tool.
    """

    CMD = "rpmbuild"
    logs = []

    @classmethod
    def _build_rpm(cls, srpm, workdir, results_dir, builder_options=None):
        """
        Build RPM using rpmbuild.

        :param srpm: abs path to SRPM
        :param workdir: abs path to working directory with rpmbuild directory
                        structure, which will be used as HOME dir.
        :param results_dir: abs path to dir where the log should be placed.
        :return: If build process ends successfully returns list of abs paths
                 to built RPMs, otherwise 'None'.
        """
        logger.info("Building RPMs")
        output = os.path.join(results_dir, "build.log")

        cmd = [cls.CMD, '--rebuild', srpm]
        if builder_options is not None:
            cmd.extend(builder_options)
        ret = ProcessHelper.run_subprocess_cwd_env(cmd,
                                                   env={'HOME': workdir},
                                                   output=output)

        if ret != 0:
            return None
        else:
            return [f for f in PathHelper.find_all_files(workdir, '*.rpm') if not f.endswith('.src.rpm')]

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
    def prepare(cls, spec):
        """
        Checks if all build dependencies are installed. If not, asks user whether they should be installed.
        If he agrees, installs build dependencies using PolicyKit.

        :param spec: SpecFile object
        """
        req_pkgs = spec.get_requires()
        if not RpmHelper.all_packages_installed(req_pkgs):
            if ConsoleHelper.get_message('\nSome build dependencies are missing. Do you want to install them now'):
                if RpmHelper.install_build_dependencies(spec.get_path()) != 0:
                    raise RebaseHelperError('Failed to install build dependencies')

    @classmethod
    def build(cls, spec, sources, patches, results_dir, **kwargs):
        """
        Builds the SRPM and RPMs using rpmbuild

        :param spec: absolute path to the SPEC file.
        :param sources: list with absolute paths to SOURCES
        :param patches: list with absolute paths to PATCHES
        :param results_dir: absolute path to DIR where results should be stored
        :return: dict with:
                 'srpm' -> absolute path to SRPM
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to build_logs
        """
        # build SRPM
        srpm, cls.logs = cls._build_srpm(spec, sources, patches, results_dir)

        # build RPMs
        rpm_results_dir = os.path.join(results_dir, "RPM")
        with RpmbuildTemporaryEnvironment(sources, patches, spec, rpm_results_dir) as tmp_env:
            env = tmp_env.env()
            tmp_dir = tmp_env.path()
            tmp_results_dir = env.get(RpmbuildTemporaryEnvironment.TEMPDIR_RESULTS)
            rpms = cls._build_rpm(srpm, tmp_dir, tmp_results_dir, builder_options=cls.get_builder_options(**kwargs))

        if rpms is None:
            cls.logs.extend([l for l in PathHelper.find_all_files(rpm_results_dir, '*.log')])
            raise BinaryPackageBuildError("Building RPMs failed!")
        else:
            logger.info("Building RPMs finished successfully")

        # RPMs paths in results_dir
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

