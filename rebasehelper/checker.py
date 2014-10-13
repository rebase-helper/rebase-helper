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
import six

from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.base_output import OutputLogger
from xml.etree import ElementTree

check_tools = {}


def register_check_tool(check_tool):
    check_tools[check_tool.CMD] = check_tool
    return check_tool


class BaseChecker(object):
    """ Base class used for testing tool run on final pkgs. """

    @classmethod
    def match(cls, *args, **kwargs):
        """
        Checks if the tool name match the class implementation. If yes, returns
        True, otherwise returns False.
        """
        raise NotImplementedError()

    @classmethod
    def run_check(cls, *args, **kwargs):
        """
        Perform the check itself and return results.
        """
        raise NotImplementedError()


@register_check_tool
class PkgDiffTool(BaseChecker):
    """ Pkgdiff compare tool. """
    CMD = "pkgdiff"
    pkgdiff_results_filename = 'pkgdiff_reports.html'
    results_dir = ''
    workspace_dir = ''
    pkgdiff_results_dir = ''
    results_dict = {}

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def _create_xml(cls, name, input_structure):
        file_name = os.path.join(cls.results_dir, name + ".xml")
        tags = {'version': input_structure.get('version', ""),
                'group': input_structure.get('name', ''),
                'packages': input_structure.get('rpm', [])}
        lines = []
        for key, value in tags.items():
            new_value = value if isinstance(value, str) else '\n'.join(value)
            lines.append('<{0}>\n{1}\n</{0}>\n'.format(key, new_value))

        try:
            with open(file_name, 'w') as f:
                f.writelines(lines)
        except IOError:
            raise RebaseHelperError("Unable to create XML file for pkgdiff tool '{0}'".format(file_name))

        return file_name

    @classmethod
    def _fill_dictionary(cls):
        """
        Parsed files.xml and symbols.xml and fill dictionary
        :return:
        """
        XML_FILES = ['files.xml', 'symbols.xml']
        XML_TAGS = ['added', 'removed', 'changed', 'moved', 'renamed']
        for tag in XML_TAGS:
            cls.results_dict[tag] = []
        for file_name in [os.path.join(cls.results_dir, x) for x in XML_FILES]:
            logger.info('Processing {0} file.'.format(file_name))
            try:
                with open(file_name, "r") as f:
                    lines = f.readlines()
                    lines.insert(0, '<pkgdiff>')
                    lines.append('</pkgdiff>')
                    pkgdiff_tree = ElementTree.fromstringlist(lines)
                    for tag in XML_TAGS:
                        for pkgdiff in pkgdiff_tree.findall('.//' + tag):
                            cls.results_dict[tag].extend(pkgdiff.text.split())
            except IOError:
                continue

    @classmethod
    def _update_added_removed(cls, key):
        update = []
        removed_things = ['.build-id', '.dwz']
        for items in cls.results_dict[key]:
            # TODO for now we are skipping the .build-id files
            removed = [x for x in removed_things if x in items]
            if removed:
                continue
            # We find whether file exists in 'moved' section
            # If yes then do not include in key set
            found = [x for x in cls.results_dict['moved'] if items in x]
            if not found:
                update.append(items)
        return update

    @classmethod
    def process_xml_results(cls):
        cls._fill_dictionary()
        for items in ['added', 'removed']:
            cls.results_dict[items] = cls._update_added_removed(items)

        return cls.results_dict


    @classmethod
    def run_check(cls, **kwargs):
        """ Compares old and new RPMs using pkgdiff """
        cls.results_dir = kwargs.get('results_dir', '')
        cls.workspace_dir = os.path.join(kwargs.get('workspace_dir', ''), cls.CMD)
        cls.pkgdiff_results_full_path = os.path.join(cls.results_dir, cls.pkgdiff_results_filename)
        # create the workspace directory
        os.makedirs(cls.workspace_dir)

        versions = ['old', 'new']
        cmd = [cls.CMD]
        for version in versions:
            old = OutputLogger.get_build(version)
            if old:
                file_name = cls._create_xml(version, input_structure=old)
                cmd.append(file_name)
        cmd.append('-extra-info')
        cmd.append(cls.results_dir)
        cmd.append('-report-path')
        cmd.append(cls.pkgdiff_results_full_path)
        ret_code = ProcessHelper.run_subprocess(cmd, output=ProcessHelper.DEV_NULL)
        """
         From pkgdiff source code:
         ret_code 0 means unchanged
         ret_code 1 means Changed
         other return codes means error
        """
        if int(ret_code) != 0 and int(ret_code) != 1:
            raise RebaseHelperError('Execution of {0} failed.\nCommand line is: {1}'.format(cls.CMD, cmd))
        OutputLogger.set_info_text('Result HTML page from pkgdiff is store in: ', cls.pkgdiff_results_full_path)
        return cls.process_xml_results()


class Checker(object):
    """
    Class representing a process of checking final packages.
    """

    def __init__(self, tool=None):
        if tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._tool_name = tool
        self._tool = None

        for check_tool in check_tools.values():
            if check_tool.match(self._tool_name):
                self._tool = check_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported checking tool")

    def __str__(self):
        return "<Checker tool_name='{_tool_name}' tool={_tool}>".format(**vars(self))

    def run_check(self, **kwargs):
        """ Run the check """
        logger.debug("Checker: Running tests on packages using '{0}'".format(self._tool_name))
        return self._tool.run_check(**kwargs)

    @classmethod
    def get_supported_tools(cls):
        """ Return list of supported tools """
        return check_tools.keys()