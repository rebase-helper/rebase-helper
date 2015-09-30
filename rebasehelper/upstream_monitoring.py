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
from pprint import pprint
from rebasehelper.cli import CLI
from rebasehelper.logger import LoggerHelper, logger, logger_upstream
from rebasehelper.application import Application
from rebasehelper.exceptions import RebaseHelperError


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

    def __init__(self, ):
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
        pprint(inner)

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

        """ Clonning repository and call rebase-helper """
        logger_upstream.info('Clonning repository %s', self.url)
        try:
            # git clone http://pkgs.fedoraproject.org/cgit/emacs.git/
            git.Git().clone(self.url)
        except git.exc.GitCommandError as gce:
            logger_upstream.error(gce.message)
            return
        os.chdir(self.package)
        logger_upstream.debug(self.arguments)
        cli = CLI(self.arguments)
        try:
            app = Application(cli)
            # TDO After a deep testing app.run() will be used
            #app.run()
            logger_upstream.info(app.kwargs)
            sources = app.prepare_sources()
            app.patch_sources(sources)
            build = app.build_packages()
            if build:
                app.pkgdiff_packages()
            self.patches = app.rebased_patches
            self._print_patches()
            logger_upstream.info(app.debug_log_file)
        except RebaseHelperError as rbe:
            logger_upstream.error(rbe.message)

    def add_upstream_log_file(self):
        """
        Add the application wide debug log file
        :return:
        """
        upstream_log_file = os.path.join('/tmp', 'rebase-helper-upstream.log')
        try:
            LoggerHelper.add_file_handler(logger_upstream,
                                          upstream_log_file,
                                          logging.Formatter("%(asctime)s %(levelname)s\t%(filename)s"
                                                            ":%(lineno)s %(funcName)s: %(message)s"),
                                          logging.DEBUG)
        except (IOError, OSError):
            logger.warning("Can not create debug log '%s'", upstream_log_file)

    def process_messsage(self):

        """ Process message from fedmsg """
        self.arguments = ['-v, --non-interactive', '--buildtool', 'fedpkg']
        self._get_package_version()
        self.parse_fedpkg_conf()
        tempdir = tempfile.mkdtemp(suffix='-rebase-helper')
        cwd = os.getcwd()
        os.chdir(tempdir)
        self._call_rebase_helper()
        os.chdir(cwd)
        shutil.rmtree(tempdir)
