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

import configparser
import os

from rebasehelper.options import OPTIONS, traverse_options
from rebasehelper.constants import CONFIG_PATH, CONFIG_FILENAME


class Config:

    def __init__(self, config_file=None):
        self.path_to_config = self.get_config_path(config_file)
        self.config = self.get_config()

    def __getattr__(self, name):
        return self.config.get(name)

    @staticmethod
    def get_config_path(config_file):
        # ensure XDG_CONFIG_HOME is set
        if 'XDG_CONFIG_HOME' not in os.environ:
            os.environ['XDG_CONFIG_HOME'] = os.path.expandvars(os.path.join('$HOME', '.config'))
        path = os.path.expandvars(config_file or os.path.join(CONFIG_PATH, CONFIG_FILENAME))
        return os.path.abspath(path)

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
