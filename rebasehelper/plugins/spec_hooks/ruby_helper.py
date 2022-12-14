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

import logging
import os
import re
from typing import cast

from rebasehelper.constants import ENCODING
from rebasehelper.logger import CustomLogger
from rebasehelper.plugins.spec_hooks import BaseSpecHook
from rebasehelper.temporary_environment import TemporaryEnvironment
from rebasehelper.types import PackageCategories
from rebasehelper.specfile import PackageCategory
from rebasehelper.helpers.process_helper import ProcessHelper


logger: CustomLogger = cast(CustomLogger, logging.getLogger(__name__))


class RubyHelper(BaseSpecHook):

    CATEGORIES: PackageCategories = [PackageCategory.ruby]

    @classmethod
    def _get_instructions(cls, spec, comments, old_version, new_version):
        """Extract instructions from comments, update version if necessary"""
        instructions = []
        for comment in comments:
            comment = spec.expand(comment, comment)
            comment = re.sub(r'^#\s*', '', comment)
            comment = comment.replace(old_version, new_version)
            instructions.append(comment)
        return instructions

    @classmethod
    def _build_source_from_instructions(cls, instructions, source, logfile):
        """Run instructions to create source archive"""
        logger.info("Attempting to create source '%s' using instructions in comments", source)
        with TemporaryEnvironment() as tmp:
            script = os.path.join(tmp.path(), 'script.sh')
            with open(script, 'w', encoding=ENCODING) as f:
                f.write('#!/bin/sh -x\n')
                f.write('{}\n'.format('\n'.join(instructions)))
                f.write('cp "{}" "{}"\n'.format(source, os.getcwd()))
            os.chmod(script, 0o755)
            result = ProcessHelper.run_subprocess_cwd(script, tmp.path(), output_file=logfile, shell=True)
        if result == 0 and os.path.isfile(source):
            logger.info('Source creation succeeded.')
        else:
            logger.info('Source creation failed.')

    @classmethod
    def run(cls, spec_file, rebase_spec_file, **kwargs):
        # find non-existent local sources
        sources = [
            s
            for s in rebase_spec_file.all_sources
            if not s.remote
            and not (rebase_spec_file.spec.sourcedir / s.expanded_filename).is_file()
        ]
        for source in sources:
            if next(s for s in spec_file.all_sources if s.number == source.number).location == source.location:
                # skip sources that stayed unchanged
                continue
            logger.info("Found non-existent source '%s'", source.expanded_filename)
            if not source.comments:
                # nothing to do
                continue
            instructions = cls._get_instructions(
                rebase_spec_file,
                source.comments,
                spec_file.spec.expanded_version,
                rebase_spec_file.spec.expanded_version,
            )
            logfile = os.path.join(kwargs['workspace_dir'], '{}.log'.format(source.expanded_filename))
            cls._build_source_from_instructions(
                instructions,
                rebase_spec_file.spec.sourcedir / source.expanded_filename,
                logfile,
            )
