# -*- coding: utf-8 -*-

import os
from rebasehelper.logger import logger

class RebaseBase(object):
    """ Class used for testing and other future stuff, ...
        Each method should overwrite method like run_check
    """

    def run_check(self, **kwargs):
        """ abstract method for checking
        like PathChecker and DevelChecker
        """
        return []

    def prepare_source(self):
        """ This method is used for prepare sources
        before running any checker
        """
        pass