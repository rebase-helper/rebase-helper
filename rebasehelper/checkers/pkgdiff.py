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

from rebasehelper.utils import ProcessHelper, RpmHelper
from rebasehelper.logger import logger
from rebasehelper.exceptions import RebaseHelperError, CheckerNotFoundError
from rebasehelper.results_store import results_store
from rebasehelper import settings
from rebasehelper.checker import BaseChecker
from xml.etree import ElementTree


class PkgDiffTool(BaseChecker):
    """ Pkgdiff compare tool. """
    CMD = "pkgdiff"
    DEFAULT = True
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
    def get_checker_name(cls):
        return cls.CMD

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
            old_version = results_store.get_old_build().get('version')
            if old_version is '':
                old_version = cls._get_rpm_info('version', results_store.get_old_build()['rpm'])
        if new_version is None:
            new_version = results_store.get_new_build().get('version')
            if new_version is '':
                new_version = cls._get_rpm_info('version', results_store.get_new_build()['rpm'])

        for tag in settings.CHECKER_TAGS:
            cls.results_dict[tag] = []
        for file_name in [os.path.join(result_dir, x) for x in XML_FILES]:
            logger.debug('Processing %s file.', file_name)
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
            old = results_store.get_build(version)
            if old:
                file_name = cls._create_xml(version, input_structure=old)
                cmd.append(file_name)
        cmd.append('-extra-info')
        cmd.append(cls.results_dir)
        cmd.append('-report-path')
        cmd.append(cls.pkgdiff_results_full_path)
        try:
            ret_code = ProcessHelper.run_subprocess(cmd, output=ProcessHelper.DEV_NULL)
        except OSError:
            raise CheckerNotFoundError("Checker '%s' was not found or installed." % cls.CMD)

        """
         From pkgdiff source code:
         ret_code 0 means unchanged
         ret_code 1 means Changed
         other return codes means error
        """
        if int(ret_code) != 0 and int(ret_code) != 1:
            raise RebaseHelperError('Execution of %s failed.\nCommand line is: %s' % (cls.CMD, cmd))
        results_dict = cls.process_xml_results(cls.results_dir)
        lines = []

        for key, val in six.iteritems(results_dict):
            if val:
                if lines:
                    lines.append('')
                lines.append('Following files were %s:' % key)
                lines.extend(val)

        pkgdiff_report = os.path.join(cls.results_dir, 'report-' + cls.pkgdiff_results_filename + '.log')
        try:
            with open(pkgdiff_report, "w") as f:
                f.write('\n'.join(lines))
        except IOError:
            raise RebaseHelperError("Unable to write result from %s to '%s'" % (cls.CMD, pkgdiff_report))

        return {pkgdiff_report: None}
