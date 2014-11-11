#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This tool helps you to rebase package to the latest version
# Copyright (C) 2013-2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Authors: Petr Hracek <phracek@redhat.com>
#          Tomas Hozza <thozza@redhat.com>


from __future__ import print_function
import subprocess
import os
from rebasehelper.version import VERSION
from rebasehelper.cli import CliHelper
try:
    from setuptools import setup, Command
except:
    from distutils.core import setup, Command


class PyTest(Command):
    user_options = [('test-runner=',
                     't',
                     'test runner to use; by default, multiple py.test runners are tried')]
    command_consumes_arguments = True

    def initialize_options(self):
        self.test_runner = None
        self.args = []

    def finalize_options(self):
        pass

    def runner_exists(self, runner):
        syspaths = os.getenv('PATH').split(os.pathsep)
        for p in syspaths:
            if os.path.exists(os.path.join(p, runner)):
                return True

        return False

    def run(self):
        # only one test runner => just run the tests
        supported = ['2.7', '3.3']
        potential_runners = ['py.test-' + s for s in supported]
        if self.test_runner:
            potential_runners = [self.test_runner]
        runners = [pr for pr in potential_runners if self.runner_exists(pr)]

        for runner in runners:
            if len(runners) > 1:
                print('\n' * 2)
                print('Running tests using "{0}":'.format(runner))

            retcode = 0
            cmd = [runner]
            for a in self.args:
                cmd.append(a)
            cmd.append('-v')
            cmd.append('test')
            t = subprocess.Popen(cmd)
            rc = t.wait()
            retcode = t.returncode or retcode

        raise SystemExit(retcode)

install_requires = ['pkgdiff >= 1.6.3']

setup(
    name='rebasehelper',
    version=VERSION,
    description='RebaseHelper helps you to rebase your packages.',
    keywords='packages,easy,quick',
    author='Petr Hracek',
    author_email='phracek@redhat.com',
    url='https://github.com/phracek/rebase-helper',
    license='GPLv2+',
    packages=['rebasehelper'],
    include_package_data=True,
    entry_points={'console_scripts': ['rebase-helper=rebasehelper.cli:CliHelper.run']},
    install_requires=install_requires,
    setup_requires=[],
    classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
                   'Operating System :: POSIX :: Linux',
                   'Programming Language :: Python',
                   'Topic :: Software Development',
                  ],
    cmdclass={'test': PyTest}
)
