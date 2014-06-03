# -*- coding: utf-8 -*-

import os
import sys

from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger

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
    def __init__(self, patches, old_sources, new_sources):
        self.patches = patches
        self.old_sources = old_sources
        self.new_sources = new_sources

    def patch_command(self, patch_name, patch_flags):
        """
        Patch command whom patches as the
        """
        cmd = ['/usr/bin/patch']
        cmd.append(patch_flags)
        cmd.append(" < ")
        cmd.append(patch_name)

        ret_code = ProcessHelper.run_subprocess_cwd(' '.join(cmd), shell=True)
        return ret_code

    def apply_patch(self, patch, source_dir):
        """
        Function applies a patch to a new sources
        """
        os.chdir(source_dir)
        ret_code = self.patch_command(get_path_to_patch(patch[0]), patch[1])
        if ret_code != 0:
            logger.error('Applying patch {0} failed with return code {1}'.format(patch[0], ret_code))
            logger.error('Patch failed. Updating patch with some diff programs continues.')
            sys.exit(0)
            #TODO Run any diff tool

    def run_patch(self):
        for order in sorted(self.patches):
            self.apply_patch(self.patches[order], self.old_sources)
            self.apply_patch(self.patches[order], self.new_sources)



