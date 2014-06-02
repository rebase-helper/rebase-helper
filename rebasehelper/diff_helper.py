
from rebasehelper import base_checker

diff_tools = {}
def register_diff_tool(diff_tool):
    diff_tools.setdefault(diff_tool.shortcut, [])
    diff_tools[diff_tool.shortcut].append(diff_tool)
    return diff_tool


class DiffHelper(object):
    """ Class used for testing and other future stuff, ...
        Each method should overwrite method like run_check
    """

    @classmethod
    def run_diff(self, **kwargs):
        """
            Method will check all patches in relevant package
        """
        return NotImplementedError()

@register_diff_tool
class MeldDiffHelper(DiffHelper):
    """
    The class is used for diff between two directory sources
    """
    @classmethod
    def run_diff(self, **kwargs):
        pass
