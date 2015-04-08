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
from rebasehelper.cli import CLI
from rebasehelper.logger import logger
from rebasehelper.application import Application
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.utils import defenc


class UpstreamMonitoringError(RuntimeError):

    """Error indicating problems with Git"""

    pass


class UpstreamMonitoring(object):

    """ Class represents upstream monitoring service"""

    fedpkg_file = '/etc/rpkg/fedpkg.conf'
    anonymous_url = 'anongiturl'
    package = ''
    arguments = ['--non-interactive']
    patches = {}
    url = ''

    def __init__(self, name, endpoint, topic, msg):
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
        module_name = 'module'
        fields = {}
        if config.has_section(section):
            for option in config.options(section):
                fields[option] = config.get(section, option)
        self.url = fields.get(self.anonymous_url).replace('%(module)s', self.package)

    def _get_package_version(self, msg):
        try:
            rebase_helper_msg = ast.literal_eval(self.msg['msg']['log'].encode('utf-8'))
        except ValueError:
            logger.debug('Wrong value in request from upstream monitoring service')
            return
        except SyntaxError:
            logger.debug('wrong request from upstream monitoring service')
            return
        self.package = rebase_helper_msg.get('package')
        self.version = rebase_helper_msg.get('version')
        self.arguments.append(self.version)

    def _print_patches(self):
        if self.patches['deleted']:
            logger.info('Following patches were deleted %s' % self.patches['deleted'])
        for patch in self.patches['unapplied']:
            # Remove duplicates
            self.patches['modified'] = [x for x in self.patches['modified'] if patch not in x]
        if self.patches['modified']:
            logger.info('Following patches were modified %s' % [os.path.basename(x) for x in self.patches['modified']])
        if self.patches['unapplied']:
            logger.info('Following patches were unapplied %s' % self.patches['unapplied'])

    def _call_rebase_helper(self, tempdir):
        logger.info('Clonning repository {0}'.format(self.url))
        git.Git().clone(self.url)
        os.chdir(self.package)
        cli = CLI(self.arguments)
        try:
            app = Application(cli)
            app.run()
            self.patches = app.rebased_patches
            self._print_patches()
            logger.info(app.debug_log_file)
        except RebaseHelperError as rbe:
            logger.error(rbe.message)

    def process_messsage(self):
        print ('NEW REQUEST')
        print('TOPIC:', self.topic)
        print('MSG:', self.msg)
        if self.topic == 'org.fedoraproject.dev.logger.log':
            self._get_package_version(self.msg)
            self.parse_fedpkg_conf()
            tempdir = tempfile.mkdtemp(suffix='-rebase-helper')
            cwd = os.getcwd()
            os.chdir(tempdir)
            self._call_rebase_helper(tempdir)
            os.chdir(cwd)