# -*- coding: utf-8 -*-

patch_tools = {}
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
    def run_patch(self, **kwargs):
        """
            Method will check all patches in relevant package
        """
        return NotImplementedError()

@register_patch_tool
class FedoraPatchTool(PatchTool):
    shortname = 'fedora_patch'
    c_patch = 'patch'

    @classmethod
    def run_patch(self, **kwargs):
        """
        The function can be used for patching one
        directory against another
        """
        pass