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
        """Perform the check itself and return results."""
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
        """Compares old and new RPMs using pkgdiff"""
        results_dict = {}

        for tag in settings.CHECKER_TAGS:
            results_dict[tag] = []
        cls.results_dir = results_dir

        # Only S (size), M(mode) and 5 (checksum) are now important
        not_catched_flags = ['T', 'F', 'G', 'U', 'V', 'L', 'D', 'N']
        old_pkgs = cls._get_rpms(OutputLogger.get_old_build().get('rpm', None))
        new_pkgs = cls._get_rpms(OutputLogger.get_new_build().get('rpm', None))
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
        results_dict = dict((k, v) for k, v in six.iteritems(results_dict) if v)
        text = []
        for key, val in six.iteritems(results_dict):
            text.append('Following files were %s:\n%s' % (key, '\n'.join(val)))

        pkgdiff_report = os.path.join(cls.results_dir, 'report-' + cls.CMD + '.log')
        try:
            with open(pkgdiff_report, "w") as f:
                f.writelines(text)
        except IOError:
            raise RebaseHelperError("Unable to write result from %s to '%s'" % (cls.CMD, pkgdiff_report))

        return {pkgdiff_report: None}


@register_check_tool
class PkgDiffTool(BaseChecker):
    """ Pkgdiff compare tool. """
    CMD = "pkgdiff"
    pkgdiff_results_filename = 'pkgdiff_reports.html'
    files_xml = "files.xml"
    results_dir = ''
    results_dict = {}

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def _get_rpm_info(cls, name, packages):
        if packages is None:
            return None
        basic_package = sorted(packages)[0]
        return RpmHelper.get_info_from_rpm(basic_package, name)

    @classmethod
    def _create_xml(cls, name, input_structure):
        """
        Function creates a XML format for pkgdiff command
        :param name: package name
        :param input_structure: structure provided by OutputLogger.get_build('new' or 'old')
        :return:
        """
        file_name = os.path.join(cls.results_dir, name + ".xml")
        if input_structure.get('version', '') == '':
            input_structure['version'] = cls._get_rpm_info('version', input_structure['rpm'])

        if input_structure.get('name', '') == '':
            input_structure['name'] = cls._get_rpm_info('name', input_structure['rpm'])

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
            raise RebaseHelperError("Unable to create XML file for pkgdiff tool '%s'" % file_name)

        return file_name

    @classmethod
    def _remove_not_changed_files(cls):
        """
        Function removes all rows which were not changed
        """
        for tag in settings.CHECKER_TAGS:
            cls.results_dict[tag] = [x for x in cls.results_dict[tag] if not x.endswith('(0%)')]

    @classmethod
    def fill_dictionary(cls, result_dir, old_version=None, new_version=None):
        """
        Parsed files.xml and symbols.xml and fill dictionary
        :param result_dir: where should be stored file for pkgdiff
        :param old_version: old version of package
        :param new_version: new version of package
        :return:
        """
        XML_FILES = ['files.xml', 'symbols.xml']
        if old_version is None:
            old_version = OutputLogger.get_old_build().get('version')
            if old_version is '':
                old_version = cls._get_rpm_info('version', OutputLogger.get_old_build()['rpm'])
        if new_version is None:
            new_version = OutputLogger.get_new_build().get('version')
            if new_version is '':
                new_version = cls._get_rpm_info('version', OutputLogger.get_new_build()['rpm'])

        for tag in settings.CHECKER_TAGS:
            cls.results_dict[tag] = []
        for file_name in [os.path.join(result_dir, x) for x in XML_FILES]:
            logger.info('Processing %s file.', file_name)
            try:
                with open(file_name, "r") as f:
                    lines = ['<pkgdiff>']
                    lines.extend(f.readlines())
                    lines.append('</pkgdiff>')
                    pkgdiff_tree = ElementTree.fromstringlist(lines)
                    for tag in settings.CHECKER_TAGS:
                        for pkgdiff in pkgdiff_tree.findall('.//' + tag):
                            files = [x.strip() for x in pkgdiff.text.strip().split('\n')]
                            files = [x.replace(old_version, '*') for x in files]
                            files = [x.replace(new_version, '*') for x in files]
                            cls.results_dict[tag].extend(files)
            except IOError:
                continue

    @classmethod
    def _update_changed_moved(cls, key):
        updated_list = []
        for item in cls.results_dict[key]:
            fields = item.split(';')
            found = [x for x in cls.results_dict['changed'] if os.path.basename(fields[0]) in x]
            if not found:
                updated_list.append(item)
        return updated_list

    @classmethod
    def _remove_not_checked_files(cls, results_dict):
        """
        Function removes things which we don't care like
        ['.build-id', '.dwz']
        :return:
        """
        update_list = []
        removed_things = ['.build-id', '.dwz']
        for item in results_dict:
            removed = [x for x in removed_things if x in item]
            if removed:
                continue
            if item.endswith('.debug'):
                continue
            update_list.append(item)
        return update_list

    @classmethod
    def process_xml_results(cls, result_dir, old_version=None, new_version=None):
        """
        Function for filling dictionary with keys like 'added', 'removed'

        :return: dict = {'added': [list_of_added],
                         'removed': [list of removed],
                         'changed': [list of changed],
                         'moved': [list of moved]
                        }
        """
        cls.fill_dictionary(result_dir, old_version=old_version, new_version=new_version)

        # Remove all files which were not changed
        cls._remove_not_changed_files()
        for tag in settings.CHECKER_TAGS:
            cls.results_dict[tag] = cls._remove_not_checked_files(cls.results_dict[tag])

        added = [x for x in cls.results_dict['added'] if x not in cls.results_dict['removed']]
        removed = [x for x in cls.results_dict['removed'] if x not in cls.results_dict['added']]
        cls.results_dict['added'] = added
        cls.results_dict['removed'] = removed

        # remove unchanged files and remove things which are not checked
        # remove files from 'moved' if they are in 'changed' section
        cls.results_dict['moved'] = cls._update_changed_moved('moved')

        # Remove empty items
        return dict((k, v) for k, v in six.iteritems(cls.results_dict) if v)

    @classmethod
    def run_check(cls, results_dir):
        """
        Compares old and new RPMs using pkgdiff
        :param results_dir result dir where are stored results
        """
        cls.results_dir = results_dir
        cls.pkgdiff_results_full_path = os.path.join(cls.results_dir, cls.pkgdiff_results_filename)


        cmd = [cls.CMD]
        cmd.append('-hide-unchanged')
        for version in ['old', 'new']:
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
            raise RebaseHelperError('Execution of %s failed.\nCommand line is: %s' % (cls.CMD, cmd))
        OutputLogger.set_info_text('HTML report from pkgdiff is stored in: ', cls.pkgdiff_results_full_path)
        results_dict = cls.process_xml_results(cls.results_dir)
        text = []

        for key, val in six.iteritems(results_dict):
            if val:
                text.append('Following files were %s:\n%s' % (key, '\n'.join(val)))

        pkgdiff_report = os.path.join(cls.results_dir, 'report-' + cls.pkgdiff_results_filename + '.log')
        try:
            with open(pkgdiff_report, "w") as f:
                f.writelines(text)
        except IOError:
            raise RebaseHelperError("Unable to write result from %s to '%s'" % (cls.CMD, pkgdiff_report))

        return {pkgdiff_report: None}


@register_check_tool
class AbiCheckerTool(BaseChecker):
    """ Pkgdiff compare tool. """
    CMD = "abipkgdiff"
    results_dir = ''
    log_name = 'abipkgdiff.log'

    # Example
    # abipkgdiff --d1 dbus-glib-debuginfo-0.80-3.fc12.x86_64.rpm \
    # --d2 dbus-glib-debuginfo-0.104-3.fc23.x86_64.rpm \
    # dbus-glib-0.80-3.fc12.x86_64.rpm dbus-glib-0.104-3.fc23.x86_64.rpm
    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def _get_packages_for_abipkgdiff(cls, input_structure=None):
        debug_package = None
        rest_packages = None
        packages = input_structure.get('rpm', [])
        if packages:
            debug_package = [x for x in packages if 'debuginfo' in os.path.basename(x)]
            rest_packages = [x for x in packages if 'debuginfo' not in os.path.basename(x)]

        return debug_package, rest_packages

    @classmethod
    def run_check(cls, result_dir):
        """Compares old and new RPMs using pkgdiff"""
        debug_old, rest_pkgs_old = cls._get_packages_for_abipkgdiff(OutputLogger.get_build('old'))
        debug_new, rest_pkgs_new = cls._get_packages_for_abipkgdiff(OutputLogger.get_build('new'))
        cmd = [cls.CMD]
        if debug_old is None:
            logger.warning("Package doesn't contain any debug package")
            return None
        try:
            cmd.append('--d1')
            cmd.append(debug_old[0])
        except IndexError:
            logger.error('Debuginfo package not found for old package.')
            return None
        try:
            cmd.append('--d2')
            cmd.append(debug_new[0])
        except IndexError:
            logger.error('Debuginfo package not found for new package.')
            return None
        reports = {}
        for pkg in rest_pkgs_old:
            command = list(cmd)
            # Package can be <letters><numbers>-<letters>-<and_whatever>
            regexp = r'^(\w*)(-\D+)?.*$'
            reg = re.compile(regexp)
            matched = reg.search(os.path.basename(pkg))
            if matched:
                file_name = matched.group(1)
                command.append(pkg)
                find = [x for x in rest_pkgs_new if os.path.basename(x).startswith(file_name)]
                command.append(find[0])
                package_name = os.path.basename(os.path.basename(pkg))
                logger.debug('Package name for ABI comparision %s', package_name)
                regexp_name = r'(\w-)*(\D+)*'
                reg_name = re.compile(regexp_name)
                matched = reg_name.search(os.path.basename(pkg))
                logger.debug('Found matches %s', matched.groups())
                if matched:
                    package_name = matched.group(0) + cls.log_name
                else:
                    package_name = package_name + '-' + cls.log_name
                output = os.path.join(cls.results_dir, result_dir, package_name)
                ret_code = ProcessHelper.run_subprocess(command, output=output)
                if int(ret_code) & settings.ABIDIFF_ERROR and int(ret_code) & settings.ABIDIFF_USAGE_ERROR:
                    raise RebaseHelperError('Execution of %s failed.\nCommand line is: %s' % (cls.CMD, cmd))
                if int(ret_code) == 0:
                    text = 'ABI of the compared binaries in package %s are equal.' % package_name
                else:
                    text = 'ABI of the compared binaries in package %s are not equal.' % package_name
                reports[output] = text
            else:
                logger.debug("Rebase-helper did not find a package name in '%s'", package_name)
        return reports


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
        """Run the check"""
        logger.debug("Running tests on packages using '%s'", self._tool_name)
        return self._tool.run_check(results_dir)

    @classmethod
    def get_supported_tools(cls):
        """Return list of supported tools"""
        return check_tools.keys()
