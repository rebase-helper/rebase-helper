# -*- coding: utf-8 -*-
import os
from rebasehelper.logger import logger


class BaseChecker(object):
    """ Class used for testing and other future stuff, ...
        Each method should overwrite method like run_check
    """

    def run_check(self, **kwargs):
        """ Return list of files which has been changed against old version
        This will be used by checkers
        """
        raise NotImplementedError()
