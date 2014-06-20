# -*- coding: utf-8 -*-

from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger
from rebasehelper.base_checker import BaseChecker
from rebasehelper.utils import write_to_file

pkgdiff_tools = {}


def register_build_tool(pkgdiff_tool):
    pkgdiff_tools[pkgdiff_tool.CMD] = pkgdiff_tool
    return pkgdiff_tool


def check_pkgdiff_argument(pkgcomparetool):
    """
    Function checks whether pkgdifftool argument is allowed
    """
    if pkgcomparetool not in pkgdiff_tools.keys():
        logger.error('You have to specify one of these package diff tool {0}'.format(pkgdiff_tools.keys()))
        return False
    return True


@register_build_tool
class PkgDiffTool(BaseChecker):
    """ Mock build tool. """
    CMD = "pkgdiff"

    @classmethod
    def match(cls, cmd=None):
        if cmd == cls.CMD:
            return True
        else:
            return False

    @classmethod
    def _create_xml(cls, name, kwargs):
        file_name = name + ".xml"
        tags = {'version': kwargs.get('version', ""),
                'group': kwargs.get('name', ''),
                'packages': kwargs.get('rpm', [])}
        lines = []
        for key, value in tags.items():
            new_value = value if isinstance(value, str) else '\n'.join(value)
            lines.append('<{0}>\n{1}\n</{0}>\n'.format(key, new_value))
        write_to_file(file_name, "w", lines)
        return file_name

    @classmethod
    def run_check(cls, **kwargs):
        """ Compares  old and new RPMs using pkgdiff """
        versions = ['old', 'new']
        cmd = ['pkgdiff']
        for version in versions:
            old = kwargs.get(version, None)
            if old:
                file_name = cls._create_xml(version, old)
                cmd.append(file_name)
        # TODO Should we return a value??
        ProcessHelper.run_subprocess(cmd)


class PkgCompare(object):
    """
    Class representing a process of building binaries from sources.
    """

    def __init__(self, tool=None):
        if tool is None:
            raise TypeError("Expected argument 'tool' (pos 1) is missing")
        self._tool_name = tool
        self._tool = None

        for pkg_tool in pkgdiff_tools.values():
            if pkg_tool.match(self._tool_name):
                self._tool = pkg_tool

        if self._tool is None:
            raise NotImplementedError("Unsupported pkg compare tool")

    def __str__(self):
        return "<PkgCompare tool_name='{_tool_name}' tool={_tool}>".format(**vars(self))

    def compare_pkgs(self, **kwargs):
        """ Build sources. """
        logger.debug("PkgCompare: Comparing packages using '%s'" % self._tool_name)
        return self._tool.run_check(**kwargs)