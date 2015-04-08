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

import re
import os
from rebasehelper.logger import logger


class BuildLogAnalyzerMissingError(RuntimeError):

    """Error indicating build.log is missing"""

    pass


class BuildLogAnalyzerMakeError(RuntimeError):

    """Error indicating failure problem with building"""

    pass


class BuildLogAnalyzerPatchError(RuntimeError):

    """Error indicating failure problem with building"""

    pass


class BuildLogAnalyzer(object):

    """Class analyze the log provided by build programs"""

    log_dirname = ""

    @classmethod
    def parse_log(cls, dir_name, log_name):
        """
        Function analyze the logs for specific section

        :param log_name: Logfile name which is analyzed
        :param start_string: Start string
        :return: list of files
        """
        log_dictionary = {'build.log': cls._parse_build_log,
                          'mock.log': cls._parse_mock_log}
        return log_dictionary[log_name](os.path.join(dir_name, log_name))

    @classmethod
    def _parse_build_log(cls, log_name):
        """
        Function analyzes log files in our case build.log

        :param log_name:
        :return: list of files which are either missing or not exists
        """
        files = {}
        files['missing'] = []
        files['deleted'] = []

        with open(log_name, 'r') as f:
            lines = f.read()
        if not lines:
            logger.debug('Problem with openning log %s', log_name)
            raise BuildLogAnalyzerMissingError

        # Test for finding files which exists in sources
        # but are not mentioned in spec file
        missing_reg = 'error:\s+Installed\s+'
        missing_source_reg = 'RPM build errors:'
        e_reg = 'EXCEPTION:'
        section = cls._find_section(lines, missing_reg, e_reg)
        if section:
            section = section.replace('File not found by glob:', '').replace('File not found:', '')
            logger.debug('Found missing files which are not in SPEC file: %s', section)
            files['missing'] = cls._get_files_from_string(section)
        else:
            section = cls._find_section(lines, missing_source_reg, e_reg)
            if section:
                if cls._find_make_error(lines):
                    raise BuildLogAnalyzerMakeError('Look at the build log %s', log_name)
                else:
                    if cls._find_patch_error(lines):
                        raise BuildLogAnalyzerPatchError('Patching failed during building. '
                                                         'Look at the build log %s', log_name)
                    else:
                        files_from_section = cls._get_files_from_string(section)
                        if files_from_section:
                            logger.debug('Found files which does not exist in source: %s', section)
                            files['deleted'] = files_from_section
                        else:
                            logger.info('Not known issue')
                            raise RuntimeError
            else:
                logger.info('We did not find a reason why build failed.')
                logger.info('Look at the build log %s', log_name)

        return files

    @classmethod
    def _find_make_error(cls, section):
        for x in map(str.strip, section.split('\n')):
            if 'make' in x and 'Error' in x:
                logger.info('Package build failed')
                return True
        return False

    @classmethod
    def _find_patch_error(cls, section):
        section_lst = section.split('\n')
        for index, x in enumerate(map(str.strip, section_lst)):
            if 'FAILED' in x and 'RPM build errors' in section_lst[index+1]:
                return True
        return False

    @classmethod
    def _get_files_from_string(cls, section):
        """
        Function returns files from string
        If row begins with / then it appends the rest of row to field
        """
        files = []
        for x in map(str.strip, section.split('\n')):
            for dirs in ['usr', 'etc', 'opt', 'bin', 'var', 'sbin']:
                pos = x.find(dirs)
                if pos != -1:
                    x = x[pos-1:]
                    break
            if x.startswith('/') and x not in files:
                files.append(x)
        return files

    @classmethod
    def _parse_mock_log(cls, log_name):
        return None

    @classmethod
    def _find_section(cls, lines, s_reg, e_reg=None):
        """
        get string from substring

        :param log_name: file_name to analyze
        :param s_reg: Start regular expression
        :param e_reg: End regular expression
        """
        sub_lines = None
        s_search = re.search(s_reg, lines)
        s_pos = e_pos = 0
        if s_search:
            s_pos = s_search.start()
        if e_reg:
            e_search = re.search(e_reg, lines)
            if e_search:
                e_pos = e_search.start()
        if int(s_pos) == 0 or int(e_pos) == 0:
            return None
        if not e_reg:
            sub_lines = lines[s_pos:]
        else:
            sub_lines = lines[s_pos:e_pos]

        return sub_lines
