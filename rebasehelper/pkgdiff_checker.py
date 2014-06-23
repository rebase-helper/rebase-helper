# -*- coding: utf-8 -*-

from rebasehelper.base_checker import BaseChecker, register_check_tool
from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger
from rebasehelper.utils import write_to_file


@register_check_tool
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
        cmd = [cls.CMD]
        for version in versions:
            old = kwargs.get(version, None)
            if old:
                file_name = cls._create_xml(version, old)
                cmd.append(file_name)
        # TODO Should we return a value??
        ProcessHelper.run_subprocess(cmd)

