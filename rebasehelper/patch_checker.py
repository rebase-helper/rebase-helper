# -*- coding: utf-8 -*-

import os
import sys
import random
import string

from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger
from rebasehelper.diff_helper import *
from rebasehelper import settings
from rebasehelper.utils import get_rebase_name, get_temporary_name, get_content_temp

patch_tools = {}

def get_path_to_patch(patch):
    return os.path.join('..', '..', patch)

def register_patch_tool(patch_tool):
    patch_tools.setdefault(patch_tool.shortcut, [])
    patch_tools[patch_tool.shortcut].append(patch_tool)
    return patch_tool

class PatchTool(object):
    """ Class used for using several patching command tools, ...
        Each method should overwrite method like run_check
    """

    helpers = {}

    @classmethod
    def match(cls):
        """
            Method checks whether it is usefull patch method
        """
        return NotImplementedError()

    @classmethod
    def run_patch(cls, **kwargs):
        """
            Method will check all patches in relevant package
        """
        return NotImplementedError()

@register_patch_tool
class FedoraPatchTool(PatchTool):
    shortcut = 'fedora_patch'
    c_patch = 'patch'

    @classmethod
    def run_patch(self, **kwargs):
        """
        The function can be used for patching one
        directory against another
        """
        pass


class Patch(object):
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.patches = kwargs.get('patches', '')
        self.old_sources = kwargs.get('old_dir', None)
        self.new_sources = kwargs.get('new_dir', None)
        self.output_data = []
        self.patched_files = []

    def patch_command(self, patch_name, patch_flags, suffix=None, output=None):
        """
        Patch command whom patches as the
        """
        cmd = ['/usr/bin/patch']
        cmd.append(patch_flags)
        if suffix:
            cmd.append('-b ')
            cmd.append('--suffix .'+suffix)
        cmd.append(" < ")
        cmd.append(patch_name)
        temp_name = get_temporary_name()
        logger.debug('patch_command(): ' + ' '.join(cmd))
        ret_code = ProcessHelper.run_subprocess_cwd(' '.join(cmd),
                                                    output=temp_name,
                                                    shell=True)
        self.output_data = get_content_temp(temp_name)
        return ret_code

    def get_failed_patched_files(self, patch_name):
        cmd = 'lsdiff {0}'.format(patch_name)
        temp_name = get_temporary_name()
        ret_code = ProcessHelper.run_subprocess_cwd(cmd,
                                                    output=temp_name,
                                                    shell=True)
        if ret_code != 0:
            return None
        self.patched_files = get_content_temp(temp_name)
        failed_files = []
        applied_rules = ['succeeded']
        source_file = ""
        for data in self.output_data:
            if data.startswith('patching file'):
                patch, file_text, source_file = data.strip().split()
                continue
            result = [x for x in applied_rules if x in data ]
            logger.debug('get_failed_patched_files(): result: ' + str(result))
            if result:
                continue
            file_list = [x for x in self.patched_files if source_file in x ]
            if source_file in failed_files:
                continue
            failed_files.append(source_file)
        logger.debug('get_failed_patched_files(): failed_files: ' + str(failed_files))
        return failed_files

    def apply_patch(self, patch, source_dir):
        """
        Function applies a patch to a new sources
        """
        os.chdir(source_dir)
        suffix = ''.join(random.choice(string.ascii_letters) for _ in range(6))
        if source_dir != self.old_sources:
            logger.error('Applying patch {0} ...'.format(patch[0]))
        ret_code = self.patch_command(get_path_to_patch(patch[0]), patch[1], suffix=suffix)
        if ret_code != 0:
            logger.error('Patch failed with return code {0}. Updating patch with some diff programs continues.'.format(ret_code))
            patched_files = self.get_failed_patched_files(patch[0])
            if not patched_files:
                logger.error('We are not able to get a list of failed files')
                raise Exception
            patch[0] = get_rebase_name(patch[0])
            while ret_code != 0:
                self.kwargs['suffix'] = suffix
                self.kwargs['failed_files'] = patched_files
                diff = Diff(self.kwargs.get('diff_tool', None))
                ret_code = diff.diff(**self.kwargs)
                if ret_code is None:
                    logger.warning("Diff output is empty. Rebase-helper is finished")
                #TODO This row should be deleted when Diff is finished
                ret_code = 0
            #TODO
            # gendiff new_source + suffix
        return patch

    def run_patch(self):
        cwd = os.getcwd()
        for order in sorted(self.patches):
            self.apply_patch(self.patches[order], self.old_sources)
            try:
                patch = self.apply_patch(self.patches[order], self.new_sources)
            except Exception:
                raise Exception
            self.patches[order] = patch
        os.chdir(cwd)
        return self.patches



