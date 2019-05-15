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

import copy


class ResultsStore:
    """Class for storing information about results from rebase-helper actions."""

    RESULTS_INFORMATION: str = 'information'
    RESULTS_CHECKERS: str = 'checkers'
    RESULTS_BUILD_LOG_HOOKS: str = 'build_log_hooks'
    RESULTS_BUILDS: str = 'builds'
    RESULTS_PATCHES: str = 'patches'
    RESULTS_CHANGES_PATCH: str = 'changes_patch'
    RESULTS_SUCCESS: str = 'result'

    def __init__(self):
        self._data_store = dict()

    def clear(self):
        self._data_store.clear()

    def set_results(self, results_type, data_dict):
        if results_type not in (
                self.RESULTS_INFORMATION,
                self.RESULTS_CHECKERS,
                self.RESULTS_BUILD_LOG_HOOKS,
                self.RESULTS_BUILDS,
                self.RESULTS_PATCHES,
                self.RESULTS_CHANGES_PATCH,
                self.RESULTS_SUCCESS
        ):
            raise ValueError('Trying to set unsupported type of results: {}!'.format(results_type))

        try:
            dict_to_update = self._data_store[results_type]
        except KeyError:
            dict_to_update = dict()
            self._data_store[results_type] = dict_to_update
        dict_to_update.update(data_dict)

    def set_info_text(self, text, data):
        self.set_results(self.RESULTS_INFORMATION, {text: data})

    def set_patches_results(self, results_dict):
        self.set_results(self.RESULTS_PATCHES, results_dict)

    def set_checker_output(self, text, data):
        self.set_results(self.RESULTS_CHECKERS, {text: data})

    def set_build_log_hooks_result(self, text, data):
        self.set_results(self.RESULTS_BUILD_LOG_HOOKS, {text: data})

    def set_build_data(self, version, data):
        self.set_results(self.RESULTS_BUILDS, {version: data})

    def set_changes_patch(self, text, data):
        self.set_results(self.RESULTS_CHANGES_PATCH, {text: data})

    def set_result_message(self, text, data):
        self.set_results(self.RESULTS_SUCCESS, {text: data})

    def get_all(self):
        return copy.deepcopy(self._data_store)

    def get_build(self, version):
        builds_results = self._data_store.get(self.RESULTS_BUILDS, None)
        if builds_results is not None:
            return builds_results.get(version, None)
        else:
            return None

    def get_old_build(self):
        return self.get_build('old')

    def get_new_build(self):
        return self.get_build('new')

    def get_patches(self):
        return self._data_store.get(self.RESULTS_PATCHES, None)

    def get_checkers(self):
        return self._data_store.get(self.RESULTS_CHECKERS, {})

    def get_build_log_hooks(self):
        return self._data_store.get(self.RESULTS_BUILD_LOG_HOOKS, {})

    def get_summary_info(self):
        return self._data_store.get(self.RESULTS_INFORMATION, None)

    def get_changes_patch(self):
        return self._data_store.get(self.RESULTS_CHANGES_PATCH, None)

    def get_result_message(self):
        return self._data_store.get(self.RESULTS_SUCCESS, None)


# global results store
results_store: ResultsStore = ResultsStore()
