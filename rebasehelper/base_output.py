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

import six


class OutputData(object):
    """
    This is base class for Output Tool
    All information are stored here
    """
    def __init__(self):
        self.summary_information = {}

    def update_info(self, name,  data):
        """
        Function insert a new field into summary_information
        section is called name and represents text and their
        relevant data.
        """
        if name in self.summary_information:
            for key, value in six.iteritems(data):
                self.summary_information[name][key] = value
        else:
            self.summary_information[name] = {}
            self.summary_information[name] = data

    def get_key(self, key):
        try:
            return self.summary_information[key]
        except KeyError:
            return None

    def get_specific_value(self, key, value):
        result = {}
        try:
            res = self.get_key(key)
            for text, data in six.iteritems(res):
                if text == value:
                    result = data
        except KeyError:
            return None
        except AttributeError:
            return None
        else:
            return result

    def get_info(self):
        return self.summary_information


class OutputLogger(object):
    """
    The class represents information gathered during
    rebase-helper operation
    patch class, check classes
    """
    out_logger = OutputData()

    @classmethod
    def set_info_text(cls, text, data):
        cls.set_output('information', text, data)

    @classmethod
    def set_patch_output(cls, text, data):
        """
        Method stores information from patch class
        :param patch_name Name of patch class
        :param text: text provided by patch class
        """
        cls.set_output('patch', text, data)

    @classmethod
    def set_checker_output(cls, text, data):
        """
        Method stores information from checker class
        :param checker_name: Checker name like pkgdiff
        :param text
        :param data: text from checker class.
        :return:
        """
        cls.set_output('checker', text, data)

    @classmethod
    def set_output(cls, name, text, data):
        new_dict = {text: data}
        cls.out_logger.update_info(name, new_dict)

    @classmethod
    def set_build_data(cls, version, data):
        cls.set_output('build', version, data)

    @classmethod
    def get_all(cls):
        return cls.out_logger.get_info()

    @classmethod
    def get_build(cls, version):
        return cls.out_logger.get_specific_value('build', version)

    @classmethod
    def get_patches(cls, version):
        return cls.out_logger.get_specific_value('patch', version)

    @classmethod
    def get_checkers(cls):
        return cls.out_logger.get_key('checker')

    @classmethod
    def get_summary_info(cls):
        return cls.out_logger.get_key('information')
