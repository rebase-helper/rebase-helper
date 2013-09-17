# -*- coding: utf-8 -*-

from rebasehelper import rebase_base

class DevelChecker(rebase_base.RebaseBase):
    """ Class used for testing and other future stuff, ...
        Each method should overwrite method like run_check
    """

    def run_check(self, **kwargs):
        """
            Method will check whether all header, binaries and libraries are ok
            with previous version
        """
        return []