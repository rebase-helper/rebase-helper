# -*- coding: utf-8 -*-

import shutil
import random
import string

from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger
from rebasehelper.diff_helper import *
from rebasehelper import settings
from rebasehelper.utils import get_temporary_name, remove_temporary_name, get_content_file
from rebasehelper.specfile import get_rebase_name

patch_tools = {}


def get_patch_name(name):
    """
    Function returns a patch name with suffix
    :param name:
    :return: patch name with suffix
    """
    name, extension = os.path.splitext(name)
    return name + settings.REBASE_HELPER_SUFFIX + extension


def get_path_to_patch(patch):
    return os.path.join('..', '..', patch)


def register_patch_tool(patch_tool):
    patch_tools[patch_tool.c_patch] = patch_tool
    return patch_tool


class PatchBase(object):
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
class PatchTool(PatchBase):
    shortcut = 'patch'
    c_patch = 'patch'
    suffix = None
    fuzz = 0
    source_dir = ""
    old_sources = ""
    new_sources = ""

    @classmethod
    def match(cls, c_patch):
        if c_patch == cls.c_patch:
            return True
        else:
            return False

    @classmethod
    def patch_command(cls, patch_name, patch_flags, output=None):
        """
        Patch command whom patches as the
        """
        cmd = ['/usr/bin/patch']
        cmd.append(patch_flags)
        if cls.suffix:
            cmd.append('-b ')
            cmd.append('--suffix .' + cls.suffix)
        cmd.append(' --fuzz={0}'.format(cls.fuzz))
        cmd.append(' --force') # don't ask questions
        cmd.append(' < ')
        cmd.append(patch_name)
        temp_name = get_temporary_name()
        logger.debug('patch_command(): ' + ' '.join(cmd))
        ret_code = ProcessHelper.run_subprocess_cwd(' '.join(cmd),
                                                    output=temp_name,
                                                    shell=True)
        cls.output_data = get_content_file(temp_name, 'r', method=True)
        remove_temporary_name(temp_name)
        return ret_code

    @classmethod
    def get_failed_patched_files(cls, patch_name):
        cmd = 'lsdiff {0}'.format(patch_name)
        temp_name = get_temporary_name()
        ret_code = ProcessHelper.run_subprocess_cwd(cmd,
                                                    output=temp_name,
                                                    shell=True)
        if ret_code != 0:
            return None
        cls.patched_files = get_content_file(temp_name, 'r', method=True)
        remove_temporary_name(temp_name)
        failed_files = []
        applied_rules = ['succeeded']
        source_file = ""
        for data in cls.output_data:
            if data.startswith('patching file'):
                patch, file_text, source_file = data.strip().split()
                continue
            result = [x for x in applied_rules if x in data ]
            if result:
                continue
            file_list = [x for x in cls.patched_files if source_file in x ]
            if source_file in failed_files:
                continue
            failed_files.append(source_file)
        return failed_files

    @classmethod
    def generate_diff(cls, patch, source_dir):
        # gendiff new_source + self.suffix > patch[0]
        logger.info("Generating patch by gendiff")
        cmd = ['/usr/bin/gendiff']
        cmd.append(os.path.basename(cls.new_sources))
        cmd.append('.'+cls.suffix)
        cmd.append('>')
        cmd.append(patch)
        temp_name = get_temporary_name()
        os.chdir(os.pardir) # goto parent dir
        logger.debug('apply_patch(): ' + ' '.join(cmd))
        ret_code = ProcessHelper.run_subprocess_cwd(' '.join(cmd),
                                                    output=temp_name,
                                                    shell=True)
        # sometimes returns 1 even the patch was generated. why ???
        logger.debug("ret_code: {0}".format(ret_code))
        os.chdir(source_dir)
        gendiff_output = get_content_file(temp_name, 'r', method=True)
        remove_temporary_name(temp_name)
        if gendiff_output:
            logger.info("gendiff_output: {0}".format(gendiff_output))


    @classmethod
    def apply_patch(cls, patch):
        """
        Function applies a patch to a old/new sources
        """
        os.chdir(cls.source_dir)
        if cls.source_dir == cls.old_sources:
            # for new_sources we want the same suffix as for old_sources
            cls.suffix = ''.join(random.choice(string.ascii_letters) for _ in range(6))
        logger.debug('Applying patch {0} to {1}...'.format(patch[0], cls.source_dir))
        ret_code = cls.patch_command(get_path_to_patch(patch[0]), patch[1])
        if ret_code != 0:
            # unexpected
            if cls.source_dir == cls.old_sources:
                logger.critical('Failed to patch old sources.{0}'.format(ret_code))
                raise RuntimeError
            get_message("Patch {0} failed on new source. merge-tool will start.".
                        format(os.path.basename(patch[0])),
                        keyboard=True)
            logger.warning('Patch failed with return code {0}. '
                           'Will start merge-tool to fix conflicts manually.'.format(ret_code))
            patched_files = cls.get_failed_patched_files(patch[0])
            if not patched_files:
                logger.error('We are not able to get a list of failed files.')
                raise RuntimeError
            orig_patch = patch[0]
            patch[0] = get_rebase_name(patch[0])
            cls.kwargs['suffix'] = cls.suffix
            cls.kwargs['failed_files'] = patched_files
            logger.debug('Input to MergeTool:', cls.kwargs)
            diff = Diff(cls.kwargs.get('diff_tool', None))
            ret_code = diff.mergetool(**cls.kwargs)
            cls.generate_diff(patch[0], cls.source_dir)
            diff.diff(orig_patch, patch[0])
            accept = ['y', 'yes']
            var = get_message(message="Do you want to continue with another patch? (y/n)")
            if var not in accept:
                sys.exit(0)

        return patch

    @classmethod
    def run_patch(cls, **kwargs):
        """
        The function can be used for patching one
        directory against another
        """
        cls.kwargs = kwargs
        cls.patches = kwargs['new'].get('patches', '')
        cls.old_sources = kwargs.get('old_dir', None)
        cls.new_sources = kwargs.get('new_dir', None)
        cls.output_data = []
        cls.patched_files = []
        cwd = os.getcwd()
        # apply patches in the same order as in spec file, not according to their numbers
        for order in sorted(cls.patches.items(), key=lambda x: x[1][2]):
            try:
                cls.source_dir = cls.old_sources
                cls.apply_patch(cls.patches[order[0]])
                cls.source_dir = cls.new_sources
                patch = cls.apply_patch(cls.patches[order[0]])
            except Exception:
                raise Exception
            cls.patches[order[0]] = patch
        os.chdir(cwd)

        return cls.patches


class PatchTool(object):
    def __init__(self, patch=None):
        if patch is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._path_tool_name = patch
        self._tool = None

        for patch_tool in patch_tools.values():
            if patch_tool.match(self._path_tool_name):
                self._tool = patch_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported build tool")



    def patch(self, **kwargs):
        logger.debug("Patch: Patching source by patch tool {0}...".format(self._path_tool_name))
        return self._tool.run_patch(**kwargs)




