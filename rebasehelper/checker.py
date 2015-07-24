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
import re
from six import StringIO

from rebasehelper.utils import ProcessHelper, RpmHelper
from rebasehelper.logger import logger
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.base_output import OutputLogger
from rebasehelper import settings
from xml.etree import ElementTree

check_tools = {}


def register_check_tool(check_tool):
    check_tools[check_tool.CMD] = check_tool
    return check_tool


class BaseChecker(object):
    """ Base class used for testing tool run on final pkgs. """

    @classmethod
    def match(cls, cmd):
        """
        Checks if the tool name match the class implementation. If yes, returns
        True, otherwise returns False.
        """
        raise NotImplementedError()

    @classmethod
    def run_check(cls, results_dir):
        """
        Perform the check itself and return results.
        """
        raise NotImplementedError()

@register_check_tool
class RpmDiffTool(BaseChecker):
    """ RpmDiff compare tool."""
    CMD = "rpmdiff"

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def _get_rpms(cls, rpm_list):
        rpm_dict = {}
        for rpm_name in rpm_list:
            rpm_dict[RpmHelper.get_info_from_rpm(rpm_name, 'name')] = rpm_name
        return rpm_dict

    @classmethod
    def _unpack_rpm(cls, rpm_name):
        pass
    @classmethod
    def _analyze_logs(cls, output, results_dict):
        removed_things = ['.build-id', '.dwz', 'PROVIDE', 'REQUIRES']
        for line in output:
            line = line.encode('ascii', 'ignore')
            if [x for x in removed_things if x in line]:
                continue

            fields = line.strip().split()
            logger.debug(fields)
            if 'removed' in line:
                results_dict['removed'].append(fields[1])
                continue
            if 'added' in line:
                results_dict['added'].append(fields[1])
                continue
            #'S.5........' for regexp
            regexp = '(S)+\.(5)+\.\.\.\.\.\.\.\.'
            match = re.search(regexp, fields[0])
            if match:
                results_dict['changed'].append(fields[1])
        return results_dict

    @classmethod
    def update_added_removed(cls, results_dict):
        added = []
        removed = []
        for item in results_dict['removed']:
            found = [x for x in results_dict['added'] if os.path.basename(item) in x]
            if not found:
                removed.append(item)

        for item in results_dict['added']:
            found = [x for x in results_dict['removed'] if os.path.basename(item) in x]
            if not found:
                removed.append(item)
        results_dict['added'] = added
        results_dict['removed'] = removed
        return results_dict

    @classmethod
    def run_check(cls, results_dir):
        """ Compares old and new RPMs using pkgdiff """
        results_dict = {}

        for tag in settings.CHECKER_TAGS:
            results_dict[tag] = []
        cls.results_dir = results_dir

        # Only S (size), M(mode) and 5 (checksum) are now important
        not_catched_flags = ['T', 'F', 'G', 'U', 'V', 'L', 'D', 'N']
        old_pkgs = cls._get_rpms(OutputLogger.get_build('old').get('rpm', None))
        new_pkgs = cls._get_rpms(OutputLogger.get_build('new').get('rpm', None))
        for key, value in six.iteritems(old_pkgs):
            cmd = [cls.CMD]
            # TODO modify to online command
            for x in not_catched_flags:
                cmd.extend(['-i', x])
            cmd.append(value)
            # We would like to build correct old package against correct new packages
            cmd.append(new_pkgs[key])
            output = StringIO()
            ProcessHelper.run_subprocess(cmd, output=output)
            results_dict = cls._analyze_logs(output, results_dict)

        results_dict = cls.update_added_removed(results_dict)
        # TODO Check for changed files and
        # remove them from 'removed' and 'added'
        #cls._unpack_rpm(old_pkgs)
        #cls._unpack_rpm(new_pkgs)
        #cls._find_file_diffs(old_pkgs, new_pkgs)
        return results_dict


@register_check_tool
class PkgDiffTool(BaseChecker):
    """ Pkgdiff compare tool. """
    CMD = "pkgdiff"
    pkgdiff_results_filename = 'pkgdiff_reports.html'
    files_xml = "files.xml"
    results_dir = ''

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
            raise RebaseHelperError("Unable to create XML file for pkgdiff tool '%s'", file_name)

        return file_name

    @classmethod
    def _remove_not_changed_files(cls, file_list):
        file_list = [x for x in file_list if not x.endswith('(0%)')]
        # We need to return string without percentage
        return file_list


    @classmethod
    def fill_dictionary(cls, result_dir):
        """
        Parsed files.xml and symbols.xml and fill dictionary
        :return:
        """
        XML_FILES = ['files.xml', 'symbols.xml']
        results_dict = {}

        for tag in settings.CHECKER_TAGS:
            results_dict[tag] = []
        for file_name in [os.path.join(result_dir, x) for x in XML_FILES]:
            logger.info('Processing %s file.', file_name)
            try:
                with open(file_name, "r") as f:
                    lines = f.readlines()
                    lines.insert(0, '<pkgdiff>')
                    lines.append('</pkgdiff>')
                    pkgdiff_tree = ElementTree.fromstringlist(lines)
                    for tag in settings.CHECKER_TAGS:
                        for pkgdiff in pkgdiff_tree.findall('.//' + tag):
                            results_dict[tag].extend([x.strip() for x in pkgdiff.text.strip().split('\n')])
            except IOError:
                continue

        return results_dict

    @classmethod
    def _update_added_removed(cls, results_dict, key):
        update = []
        for items in results_dict[key]:
            # We find whether file exists in 'moved' section
            # If yes then do not include in key set
            found = [x for x in results_dict['moved'] if items in x]
            if not found:
                update.append(items)
        return update

    @classmethod
    def _update_changed_moved(cls, results_dict, key):
        updated_list = []
        for item in results_dict[key]:
            fields = item.split(';')
            found = [x for x in results_dict['changed'] if os.path.basename(fields[0]) in x]
            if not found:
                updated_list.append(item)
        return updated_list

    @classmethod
    def _remove_not_checked_files(cls, results_dict):
        update_list = []
        removed_things = ['.build-id', '.dwz']
        for item in results_dict:
            removed = [x for x in removed_things if x in item]
            if removed:
                continue
            update_list.append(item)
        return update_list

    @classmethod
    def process_xml_results(cls, result_dir):
        """
        Function for filling dictionary with keys like 'added', 'removed'
        :return: dict = {'added': [list_of_added],
                         'removed': [list of removed],
                         'changed': [list of changed],
                         'moved': [list of moved]
                        }
        """
        results_dict = cls.fill_dictionary(result_dir)

        # TODO for now we are skipping the some files/directories
        for items in ['added', 'removed']:
            results_dict[items] = cls._update_added_removed(results_dict, items)
        # remove unchanged files and remove things which are not checked
        for tag in settings.CHECKER_TAGS:
            results_dict[tag] = cls._remove_not_changed_files(results_dict[tag])
            results_dict[tag] = cls._remove_not_checked_files(results_dict[tag])
        # remove files from 'moved' if they are in 'changed' section
        results_dict['moved'] = cls._update_changed_moved(results_dict, 'moved')

        return results_dict

    @classmethod
    def run_check(cls, results_dir):
        """ Compares old and new RPMs using pkgdiff """
        cls.results_dir = results_dir
        cls.pkgdiff_results_full_path = os.path.join(cls.results_dir, cls.pkgdiff_results_filename)

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
            raise RebaseHelperError('Execution of %s failed.\nCommand line is: %s', cls.CMD, cmd)
        OutputLogger.set_info_text('Result HTML page from pkgdiff is store in: ', cls.pkgdiff_results_full_path)
        return cls.process_xml_results(cls.results_dir)


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

    def run_check(self, results_dir):
        """ Run the check """
        logger.debug("Running tests on packages using '%s'", self._tool_name)
        return self._tool.run_check(results_dir)

    @classmethod
    def get_supported_tools(cls):
        """ Return list of supported tools """
        return check_tools.keys()
