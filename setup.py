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

import os

import pkg_resources

from rebasehelper.version import VERSION


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def get_rpm_distribution():
    for distribution in ['rpm', 'rpm-python']:
        try:
            pkg_resources.get_distribution(distribution)
        except pkg_resources.DistributionNotFound:
            continue
        else:
            return distribution
    return 'rpm-py-installer'


def get_requirements():
    result = [
        'backports.lzma;python_version<"3.3"',
        'copr',
        'pyquery',
        'requests',
        'six',
        'GitPython',
        'ansicolors',
    ]
    # there is no rpm inside RTD build environment
    if not os.getenv('READTHEDOCS'):
        result.append(get_rpm_distribution())
    return result


setup(
    name='rebasehelper',
    version=VERSION,
    description='rebase-helper helps you to rebase your packages',
    keywords='packages, easy, quick',
    author='Petr Hracek',
    author_email='phracek@redhat.com',
    url='https://github.com/rebase-helper/rebase-helper',
    license='GPLv2+',
    packages=[
        'rebasehelper',
        'rebasehelper.build_tools',
        'rebasehelper.srpm_build_tools',
        'rebasehelper.checkers',
        'rebasehelper.spec_hooks',
        'rebasehelper.output_tools',
        'rebasehelper.versioneers',
        'rebasehelper.tests',
        'rebasehelper.tests.functional',
    ],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'rebase-helper = rebasehelper.cli:CliHelper.run',
        ],
        'rebasehelper.build_tools': [
            'rpmbuild = rebasehelper.build_tools.rpmbuild_tool:RpmbuildBuildTool',
            'mock = rebasehelper.build_tools.mock_tool:MockBuildTool',
            'koji = rebasehelper.build_tools.koji_tool:KojiBuildTool',
            'copr = rebasehelper.build_tools.copr_tool:CoprBuildTool',
        ],
        'rebasehelper.srpm_build_tools': [
            'rpmbuild = rebasehelper.srpm_build_tools.rpmbuild_tool:RpmbuildSRPMBuildTool',
            'mock = rebasehelper.srpm_build_tools.mock_tool:MockSRPMBuildTool',
        ],
        'rebasehelper.checkers': [
            'rpmdiff = rebasehelper.checkers.rpmdiff_tool:RpmDiffTool',
            'pkgdiff = rebasehelper.checkers.pkgdiff_tool:PkgDiffTool',
            'abipkgdiff = rebasehelper.checkers.abipkgdiff_tool:AbiCheckerTool',
            'csmock = rebasehelper.checkers.csmock_tool:CsmockTool',
        ],
        'rebasehelper.spec_hooks': [
            'typo_fix = rebasehelper.spec_hooks.typo_fix:TypoFixHook',
            'pypi_url_fix = rebasehelper.spec_hooks.pypi_url_fix:PyPIURLFixHook',
            'ruby_helper = rebasehelper.spec_hooks.ruby_helper:RubyHelperHook',
            'commit_hash_updater = rebasehelper.spec_hooks.commit_hash_updater:CommitHashUpdaterHook',
        ],
        'rebasehelper.versioneers': [
            'anitya = rebasehelper.versioneers.anitya_versioneer:AnityaVersioneer',
            'pypi = rebasehelper.versioneers.pypi_versioneer:PyPIVersioneer',
            'rubygems = rebasehelper.versioneers.rubygems_versioneer:RubyGemsVersioneer',
            'npmjs = rebasehelper.versioneers.npmjs_versioneer:NPMJSVersioneer',
            'cpan = rebasehelper.versioneers.cpan_versioneer:CPANVersioneer',
            'haskell = rebasehelper.versioneers.haskell_versioneer:HaskellVersioneer',
        ],
        'rebasehelper.output_tools': [
            'json_output_tool = rebasehelper.output_tools.json_output_tool:JSONOutputTool',
            'text_output_tool = rebasehelper.output_tools.text_output_tool:TextOutputTool',
        ]
    },
    install_requires=get_requirements(),
    setup_requires=[],
    # this is only a temporary change until the PR adding bright colors support isn't merged to upstream
    # link to the PR: https://github.com/jonathaneunice/colors/pull/1
    dependency_links=[
        'git+https://github.com/FrNecas/colors.git@#egg=ansicolors'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Topic :: Software Development',
    ]
)
