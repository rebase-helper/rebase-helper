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

import os.path

from six.moves import configparser

from rebasehelper.options import OPTIONS, traverse_options
from rebasehelper.constants import CONFIG_FILE


class Conf:
    def __init__(self, config_file):
        self.path_to_config = self.get_conf_path(config_file)
        self.config = self.get_config()

    @staticmethod
    def get_conf_path(config_file):
        if not config_file:
            path = os.environ.get('XDG_CONFIG_HOME', os.path.expandvars('$HOME/.config'))
            config_file = os.path.join(path, CONFIG_FILE)
            return config_file
        return os.path.abspath(config_file)

    def get_config(self):
        conf = {}
        if os.path.isfile(self.path_to_config):
            config = configparser.ConfigParser()
            config.read(self.path_to_config)
            for section in config.sections():
                conf.update({k.replace('-', '_'): v for k, v in config.items(section)})

        return conf

    def merge(self, cli):
        self.config.update(vars(cli.args))

        for option in traverse_options(OPTIONS):
            args = [n.lstrip('-').replace('-', '_') for n in option['name'] if n.startswith('--')]
            if args:
                dest = args[0]

            if dest and dest not in self.config:
                self.config[dest] = option.get('default')

    def __getattr__(self, name):
        return self.config.get(name)
