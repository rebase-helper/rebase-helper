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

from __future__ import print_function
import shutil
import os
import six

from rebasehelper.utils import ProcessHelper
from rebasehelper.utils import PathHelper
from rebasehelper.utils import KojiHelper
from rebasehelper.utils import CoprHelper
from rebasehelper.utils import TemporaryEnvironment
from rebasehelper.logger import logger


koji_builder = True
try:
    import koji
    from pyrpkg.cli import TaskWatcher
    from OpenSSL import SSL
except ImportError:
    koji_builder = False


build_tools = {}


def register_build_tool(build_tool):
    build_tools[build_tool.CMD] = build_tool
    return build_tool


class SourcePackageBuildError(RuntimeError):
    """
    Error indicating failure to build Source Package.
    """
    pass


class BinaryPackageBuildError(RuntimeError):
    """
    Error indicating failure to build Binary Package
    """
    pass


class BuildTemporaryEnvironment(TemporaryEnvironment):
    """
    Class representing temporary environment.
    """

    TEMPDIR_SOURCES = TemporaryEnvironment.TEMPDIR + '_SOURCES'
    TEMPDIR_SPEC = TemporaryEnvironment.TEMPDIR + '_SPEC'
    TEMPDIR_SPECS = TemporaryEnvironment.TEMPDIR + '_SPECS'
    TEMPDIR_RESULTS = TemporaryEnvironment.TEMPDIR + '_RESULTS'

    def __init__(self, sources, patches, spec, results_dir):
        super(BuildTemporaryEnvironment, self).__init__(self._build_env_exit_callback)
        self._env['results_dir'] = results_dir
        self.sources = sources
        self.patches = patches
        self.spec = spec

    def __enter__(self):
        obj = super(BuildTemporaryEnvironment, self).__enter__()
        log_message = "Copying '%s' to '%s'"
        # create the directory structure
        self._create_directory_sctructure()
        # copy sources
        for source in self.sources:
            logger.debug(log_message, source, self._env[self.TEMPDIR_SOURCES])
            shutil.copy(source, self._env[self.TEMPDIR_SOURCES])
        # copy patches
        for patch in self.patches:
            logger.debug(log_message, patch, self._env[self.TEMPDIR_SOURCES])
            shutil.copy(patch, self._env[self.TEMPDIR_SOURCES])
        # copy SPEC file
        spec_name = os.path.basename(self.spec)
        self._env[self.TEMPDIR_SPEC] = os.path.join(self._env[self.TEMPDIR_SPECS], spec_name)
        shutil.copy(self.spec, self._env[self.TEMPDIR_SPEC])
        logger.debug(log_message, self.spec, self._env[self.TEMPDIR_SPEC])

        return obj

    def _create_directory_sctructure(self):
        """Function creating the directory structure in the TemporaryEnvironment."""
        raise NotImplementedError('The create directory function has to be implemented in child class!')

    def _build_env_exit_callback(self, results_dir, **kwargs):
        """
        The function that is called just before the destruction of the TemporaryEnvironment.
        It copies packages and logs into the results directory.

        :param results_dir: absolute path to results directory
        :return: 
        """
        os.makedirs(results_dir)
        log_message = "Copying '%s' '%s' to '%s'"
        # copy logs
        for log in PathHelper.find_all_files(kwargs[self.TEMPDIR_RESULTS], '*.log'):
            logger.debug(log_message, 'log', log, results_dir)
            shutil.copy(log, results_dir)
        # copy packages
        for package in PathHelper.find_all_files(kwargs[self.TEMPDIR], '*.rpm'):
            logger.debug(log_message, 'package', package, results_dir)
            shutil.copy(package, results_dir)


class RpmbuildTemporaryEnvironment(BuildTemporaryEnvironment):
    """
    Class representing temporary environment for RpmbuildBuildTool.
    """

    TEMPDIR_RPMBUILD = TemporaryEnvironment.TEMPDIR + '_RPMBUILD'
    TEMPDIR_BUILD = TemporaryEnvironment.TEMPDIR + '_BUILD'
    TEMPDIR_BUILDROOT = TemporaryEnvironment.TEMPDIR + '_BUILDROOT'
    TEMPDIR_RPMS = TemporaryEnvironment.TEMPDIR + '_RPMS'
    TEMPDIR_SRPMS = TemporaryEnvironment.TEMPDIR + '_SRPMS'

    def _create_directory_sctructure(self):
        # create rpmbuild directory structure
        for dir_name in ['RESULTS', 'rpmbuild']:
            self._env[self.TEMPDIR + '_' + dir_name.upper()] = os.path.join(
                self._env[self.TEMPDIR], dir_name)
            logger.debug("Creating '%s'",
                         self._env[self.TEMPDIR + '_' + dir_name.upper()])
            os.makedirs(self._env[self.TEMPDIR + '_' + dir_name.upper()])
        for dir_name in ['BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS',
                         'SRPMS']:
            self._env[self.TEMPDIR + '_' + dir_name] = os.path.join(
                self._env[self.TEMPDIR_RPMBUILD],
                dir_name)
            logger.debug("Creating '%s'",
                         self._env[self.TEMPDIR + '_' + dir_name])
            os.makedirs(self._env[self.TEMPDIR + '_' + dir_name])


class MockTemporaryEnvironment(BuildTemporaryEnvironment):
    """
    Class representing temporary environment for MockBuildTool.
    """

    def _create_directory_sctructure(self):
        # create directory structure
        for dir_name in ['SOURCES', 'SPECS', 'RESULTS']:
            self._env[self.TEMPDIR + '_' + dir_name] = os.path.join(
                self._env[self.TEMPDIR], dir_name)
            logger.debug("Creating '%s'",
                         self._env[self.TEMPDIR + '_' + dir_name])
            os.makedirs(self._env[self.TEMPDIR + '_' + dir_name])


class BuildToolBase(object):
    """
    Base class for various build tools
    """

    DEFAULT = False

    @classmethod
    def match(cls, cmd=None, *args, **kwargs):
        """Checks if tool name matches the desired one."""
        raise NotImplementedError()

    @classmethod
    def build(cls, *args, **kwargs):
        """
        Build binaries from the sources.

        Keyword arguments:
        spec -- path to a SPEC file
        sources -- list with absolute paths to SOURCES
        patches -- list with absolute paths to PATCHES
        results_dir -- path to DIR where results should be stored

        Returns:
        dict with:
        'srpm' -> absolute path to SRPM
        'rpm' -> list of absolute paths to RPMs
        'logs' -> list of absolute paths to logs
        """
        raise NotImplementedError()

    @classmethod
    def get_logs(cls):
        """
        Get logs from previously failed build
        Returns:
        dict with
        'logs' -> list of absolute paths to logs
        """
        raise NotImplementedError()

    @classmethod
    def _do_build_srpm(cls, spec, workdir, results_dir):
        """
        Build SRPM using rpmbuild.

        :param spec: abs path to SPEC file inside the rpmbuild/SPECS in workdir.
        :param workdir: abs path to working directory with rpmbuild directory
                        structure, which will be used as HOME dir.
        :param results_dir: abs path to dir where the log should be placed.
        :return: If build process ends successfully returns abs path
                 to built SRPM, otherwise 'None'.
        """
        logger.info("Building SRPM")
        spec_loc, spec_name = os.path.split(spec)
        output = os.path.join(results_dir, "build.log")

        cmd = ['rpmbuild', '-bs', spec_name]
        ret = ProcessHelper.run_subprocess_cwd_env(cmd,
                                                   cwd=spec_loc,
                                                   env={'HOME': workdir},
                                                   output=output)

        if ret != 0:
            return None
        else:
            return PathHelper.find_first_file(workdir, '*.src.rpm')

    @classmethod
    def _build_srpm(cls, spec, sources, patches, results_dir):
        """
        Builds the SRPM using rpmbuild

        :param spec: absolute path to the SPEC file.
        :param sources: list with absolute paths to SOURCES
        :param patches: list with absolute paths to PATCHES
        :param results_dir: absolute path to DIR where results should be stored
        :return: absolute path to SRPM, list with absolute paths to logs
        """
        # build SRPM
        srpm_results_dir = os.path.join(results_dir, "SRPM")
        with RpmbuildTemporaryEnvironment(sources, patches, spec,
                                          srpm_results_dir) as tmp_env:
            env = tmp_env.env()
            tmp_dir = tmp_env.path()
            tmp_spec = env.get(RpmbuildTemporaryEnvironment.TEMPDIR_SPEC)
            tmp_results_dir = env.get(
                RpmbuildTemporaryEnvironment.TEMPDIR_RESULTS)
            srpm = cls._do_build_srpm(tmp_spec, tmp_dir, tmp_results_dir)

        if srpm is None:
            cls.logs = [l for l in PathHelper.find_all_files(srpm_results_dir, '*.log')]
            raise SourcePackageBuildError("Building SRPM failed!")
        else:
            logger.info("Building SRPM finished successfully")

        # srpm path in results_dir
        srpm = os.path.join(srpm_results_dir, os.path.basename(srpm))
        logger.debug("Successfully built SRPM: '%s'", str(srpm))
        # gather logs
        logs = [l for l in PathHelper.find_all_files(srpm_results_dir, '*.log')]
        logger.debug("logs: '%s'", str(logs))

        return srpm, logs

    @staticmethod
    def get_builder_options(**kwargs):
        builder_options = kwargs.get('builder_options', None)
        if builder_options is not None:
            return filter(None, kwargs['builder_options'].split(" "))
        return None


@register_build_tool
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


@register_build_tool
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


@register_build_tool
class KojiBuildTool(BuildToolBase):
    """
    Class representing Koji build tool.
    """

    CMD = "koji"
    logs = []
    koji_helper = None

    # Taken from https://github.com/fedora-infra/the-new-hotness/blob/develop/fedmsg.d/hotness-example.py
    koji_web = "koji.fedoraproject.org"
    server = "https://%s/kojihub" % koji_web
    weburl = "http://%s/koji" % koji_web
    git_url = 'http://pkgs.fedoraproject.org/cgit/{package}.git'
    opts = {'scratch': True}
    target_tag = 'rawhide'
    priority = 30

    # Taken from  https://github.com/fedora-infra/the-new-hotness/blob/develop/hotness/buildsys.py#L78-L123

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def _scratch_build(cls, source, **kwargs):
        session = cls.koji_helper.session_maker()
        remote = cls.koji_helper.upload_srpm(session, source)
        task_id = session.build(remote, cls.target_tag, cls.opts, priority=cls.priority)
        if kwargs['builds_nowait']:
            return None, None, task_id
        weburl = cls.weburl + '/taskinfo?taskID=%i' % task_id
        logger.info('Koji task_id is here:\n' + weburl)
        session.logout()
        task_dict = cls.koji_helper.watch_koji_tasks(session, [task_id])
        task_list = []
        package_failed = False
        for key in six.iterkeys(task_dict):
            if task_dict[key] == koji.TASK_STATES['FAILED']:
                package_failed = True
            task_list.append(key)
        rpms, logs = cls.koji_helper.download_scratch_build(session,
                                                            task_list,
                                                            os.path.dirname(source).replace('SRPM', 'RPM'))
        if package_failed:
            weburl = '%s/taskinfo?taskID=%i' % (cls.weburl, task_list[0])
            logger.info('RPM build failed %s', weburl)
            logs.append(weburl)
            cls.logs.append(weburl)
            raise BinaryPackageBuildError
        logs.append(weburl)
        return rpms, logs, task_id

    @classmethod
    def get_logs(cls):
        return {'logs': cls.logs}

    @classmethod
    def build(cls, spec, sources, patches, results_dir, **kwargs):
        """
        Builds the SRPM using rpmbuild
        Builds the RPMs using koji

        :param spec: absolute path to the SPEC file.
        :param sources: list with absolute paths to SOURCES
        :param patches: list with absolute paths to PATCHES
        :param results_dir: absolute path to DIR where results should be stored
        :param upstream_monitoring: specify if build is handled by upstream monitoring
        :return: dict with:
                 'srpm' -> absolute path to SRPM
                 'rpm' -> list with absolute paths to RPMs
                 'logs' -> list with absolute paths to build_logs
        """
        # build SRPM
        srpm, cls.logs = cls._build_srpm(spec, sources, patches, results_dir)
        # build RPMs
        rpm_results_dir = os.path.join(results_dir, "RPM")
        os.makedirs(rpm_results_dir)
        cls.koji_helper = KojiHelper()
        rpms, rpm_logs, koji_task_id = cls._scratch_build(srpm, **kwargs)
        if rpm_logs:
            cls.logs.extend(rpm_logs)
        return {'srpm': srpm,
                'rpm': rpms,
                'logs': cls.logs,
                'koji_task_id': koji_task_id}


@register_build_tool
class CoprBuildTool(BuildToolBase):
    """
    Class representing Copr build tool.
    """

    CMD = "copr"
    logs = []
    copr_helper = None

    prefix = 'rebase-helper-'
    chroot = 'fedora-rawhide-x86_64'
    description = 'Repository containing rebase-helper builds.'
    instructions = '''You can use this repository to test functionality
                      of rebased packages.'''

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def _build_rpms(cls, srpm, name, **kwargs):
        project = cls.prefix + name
        client = cls.copr_helper.get_client()
        cls.copr_helper.create_project(client, project, cls.chroot,
                                       cls.description, cls.instructions)
        build_id = cls.copr_helper.build(client, project, srpm)
        if kwargs['builds_nowait']:
            return None, None, build_id
        build_url = cls.copr_helper.get_build_url(client, build_id)
        logger.info('Copr build is here:\n' + build_url)
        failed = not cls.copr_helper.watch_build(client, build_id)
        destination = os.path.dirname(srpm).replace('SRPM', 'RPM')
        rpms, logs = cls.copr_helper.download_build(client,
                                                    build_id,
                                                    destination)
        if failed:
            logger.info('Copr build failed {}'.format(build_url))
            logs.append(build_url)
            cls.logs.append(build_url)
            raise BinaryPackageBuildError
        logs.append(build_url)
        return rpms, logs, build_id

    @classmethod
    def build(cls, spec, sources, patches, results_dir, **kwargs):
        """
        Builds the SRPM using rpmbuild
        Builds the RPMs using copr

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
        os.makedirs(rpm_results_dir)
        cls.copr_helper = CoprHelper()
        rpms, rpm_logs, build_id = cls._build_rpms(srpm, **kwargs)
        if rpm_logs:
            cls.logs.extend(rpm_logs)
        return {'srpm': srpm,
                'rpm': rpms,
                'logs': cls.logs,
                'copr_build_id': build_id}

    @classmethod
    def get_logs(cls):
        return {'logs': cls.logs}


class Builder(object):
    """
    Class representing a process of building binaries from sources.
    """

    def __init__(self, tool=None):
        if tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._tool_name = tool
        self._tool = None

        for build_tool in build_tools.values():
            if build_tool.match(self._tool_name):
                self._tool = build_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported build tool")

    def __str__(self):
        return "<Builder tool_name='{_tool_name}' tool='{_tool}'>".format(**vars(self))

    def build(self, *args, **kwargs):
        """Build sources."""
        logger.debug("Building sources using '%s'", self._tool_name)
        return self._tool.build(*args, **kwargs)

    def get_logs(self):
        """Get logs."""
        logger.debug("Getting logs '%s'", self._tool_name)
        return self._tool.get_logs()

    @classmethod
    def get_supported_tools(cls):
        """
        Returns a list of supported build tools

        :return: list of supported build tools
        """
        return build_tools.keys()

    @classmethod
    def get_default_tool(cls):
        """Returns default build tool"""
        default = [k for k, v in six.iteritems(build_tools) if v.DEFAULT]
        return default[0] if default else None
