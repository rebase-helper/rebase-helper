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
import ConfigParser
import ast
import tempfile
import git
import os
import shutil
import logging
import six
import tempfile
import pprint

from rebasehelper.cli import CLI
from rebasehelper.logger import LoggerHelper, logger, logger_upstream
from rebasehelper.application import Application
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.output_tool import OutputLogger


class UpstreamMonitoringError(RuntimeError):

    """Error indicating problems with Git"""

    pass


class UpstreamMonitoring(object):

    """ Class represents upstream monitoring service"""

    fedpkg_file = '/etc/rpkg/fedpkg.conf'
    anonymous_url = 'anongiturl'
    package = ''
    arguments = []
    patches = {}
    url = ''
    version = ''
    dir_name = ''
    tmp = tempfile.mkdtemp(prefix='rhu-', dir='/var/tmp')
    report_file = ''
    result_rh = 0
    rh_stuff = {}

    def __init__(self):
        self.name = None
        self.endpoint = None
        self.topic = None
        self.msg = None
        self.arguments = []

    def add_message(self, name, endpoint, topic, msg):
        self.name = name
        self.endpoint = endpoint
        self.topic = topic
        self.msg = msg

    def add_thn_info(self, dir_name, package, version):
        self.package = package
        self.version = version
        self.dir_name = dir_name

    def parse_fedpkg_conf(self):

        """
        Function parse /etc/rpkg/fedpkg.conf file
        and return anonymous URL address for clonning package
        :return:
        """
        config = ConfigParser.RawConfigParser()
        config.readfp(open(self.fedpkg_file))
        section = 'fedpkg'
        fields = {}
        if config.has_section(section):
            for option in config.options(section):
                fields[option] = config.get(section, option)
        self.url = fields.get(self.anonymous_url).replace('%(module)s', self.package)

    def _get_package_version(self):

        """ Get package and version from fedmsg  """
        inner = self.msg['msg'].get('message', self.msg['msg'])
        distros = [p['distro'] for p in inner['packages']]

        for package in inner['packages']:
            self.package = package['package_name']
            self.version = inner['upstream_version']
            logger_upstream.info('Package %s', self.package)
            self.arguments.append(self.version)

    def _print_patches(self):
        if self.patches['deleted']:
            logger_upstream.info('Following patches were deleted %s', ','.join(self.patches['deleted']))
        for patch in self.patches['unapplied']:
            # Remove duplicates
            self.patches['modified'] = [x for x in self.patches['modified'] if patch not in x]
        if self.patches['modified']:
            logger_upstream.info('Following patches were modified %s', ','.join([os.path.basename(x) for x in self.patches['modified']]))
        if self.patches['unapplied']:
            logger_upstream.info('Following patches were unapplied %s', ','.join(self.patches['unapplied']))

    def _call_rebase_helper(self):

        logger_upstream.debug(self.arguments)
        cli = CLI(self.arguments)
        pprint.pprint(self.arguments)
        try:
            rh_app = Application(cli)
            rh_app.set_upstream_monitoring()
            # TDO After a deep testing app.run() will be used
            self.result_rh = rh_app.run()
            #logger_upstream.info(rh_app.kwargs)
            #sources = rh_app.prepare_sources()
            #rh_app.patch_sources(sources)
            #build = rh_app.build_packages()
            #if build:
            #    rh_app.pkgdiff_packages()
            #rh_app.print_summary()
            logger_upstream.info(rh_app.debug_log_file)
            self.report_file = rh_app.report_log_file
            self.log_files = rh_app.get_all_log_files()
        except RebaseHelperError:
            raise

        return self.result_rh

    def get_rebased_patches(self):
        """
        Function returns a list of patches either
        '': [list_of_deleted_patches]
        :return:
        """
        patches = False
        output_patch_string = []
        for key, val in six.iteritems(OutputLogger.get_patches()):
            if key:
                output_patch_string.append('Following patches has been %s:\n%s' % (key, val))
                patches = True
        if not patches:
            output_patch_string.append('Patches were not touched. All were applied properly')
        return output_patch_string

    def get_build_log(self):
        result = {}
        build_logs = OutputLogger.get_build('new')['logs']
        rpm_pkgs = []
        if 'rpm' in OutputLogger.get_build('new'):
            rpm_pkgs = OutputLogger.get_build('new')['rpm']
        build_logs = [x for x in build_logs if x.startswith('http')]
        if rpm_pkgs:
            result[0] = build_logs
        else:
            result[1] = build_logs
        return result

    def get_output_log(self):
        return self.report_file

    def get_checkers(self):
        checkers = {}
        if OutputLogger.get_checkers():
            for check, data in six.iteritems(OutputLogger.get_checkers()):
                for log, text in six.iteritems(data):
                    checkers[check] = log
        return checkers

    def get_rh_logs(self):
        return self.log_files

    def add_upstream_log_file(self):
        """
        Add the application wide debug log file
        :return:
        """
        upstream_log_file = os.path.join(self.tmp, 'rebase-helper-upstream.log')
        try:
            LoggerHelper.add_file_handler(logger_upstream,
                                          upstream_log_file,
                                          logging.Formatter("%(asctime)s %(levelname)s\t%(filename)s"
                                                            ":%(lineno)s %(funcName)s: %(message)s"),
                                          logging.DEBUG)
        except (IOError, OSError):
            logger.warning("Can not create debug log '%s'", upstream_log_file)

    def _get_rh_stuff(self):
        self.rh_stuff['build_log'] = self.get_build_log()
        self.rh_stuff['patches'] = self.get_rebased_patches()
        self.rh_stuff['logs'] = self.get_rh_logs()
        self.rh_stuff['checkers'] = self.get_checkers()

    def process_thn(self):
        self.arguments = ['--non-interactive', '--buildtool', 'fedpkg']
        self.arguments.append(self.version)
        cwd = os.getcwd()
        os.chdir(self.dir_name)
        try:
            self.result_rh = self._call_rebase_helper()
            self._get_rh_stuff()
        except RebaseHelperError as rbe:
            logging.error('Rebase helper failed with %s' % rbe.message)
            os.chdir(cwd)
            return 1
        os.chdir(cwd)
        return self.result_rh, self.rh_stuff
