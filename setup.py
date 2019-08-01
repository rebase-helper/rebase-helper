#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This tool helps you rebase your package to the latest version
# Copyright (C) 2013-2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
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
# Authors: Petr Hráček <phracek@redhat.com>
#          Tomáš Hozza <thozza@redhat.com>
#          Nikola Forró <nforro@redhat.com>
#          František Nečas <fifinecas@seznam.cz>

import os

import pkg_resources

from setuptools import setup, find_packages

from rebasehelper.version import VERSION


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
        'ansicolors',
        # need stable marshmallow for copr
        'marshmallow<3.0.0',
        'copr',
        'pyquery',
        'python-pam',
        'requests',
        'GitPython',
    ]
    # there is no rpm nor gssapi inside RTD build environment
    if not os.getenv('READTHEDOCS'):
        result.append(get_rpm_distribution())
        result.append('requests-gssapi')
    return result


def get_readme():
    with open('README.md') as f:
        return f.read()


setup(
    name='rebasehelper',
    version=VERSION,
    description='This tool helps you rebase your package to the latest version',
    long_description=get_readme(),
    long_description_content_type='text/markdown',
    keywords=['rebase', 'packages', 'rpm'],
    author='Petr Hracek',
    author_email='phracek@redhat.com',
    url='https://github.com/rebase-helper/rebase-helper',
    license='GPLv2+',
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'rebase-helper = rebasehelper.cli:CliHelper.run',
        ],
        'rebasehelper.build_tools': [
            'rpmbuild = rebasehelper.plugins.build_tools.rpm.rpmbuild:Rpmbuild',
            'mock = rebasehelper.plugins.build_tools.rpm.mock:Mock',
            'koji = rebasehelper.plugins.build_tools.rpm.koji_:Koji',
            'copr = rebasehelper.plugins.build_tools.rpm.copr_:Copr',
        ],
        'rebasehelper.srpm_build_tools': [
            'rpmbuild = rebasehelper.plugins.build_tools.srpm.rpmbuild:Rpmbuild',
            'mock = rebasehelper.plugins.build_tools.srpm.mock:Mock',
        ],
        'rebasehelper.checkers': [
            'rpmdiff = rebasehelper.plugins.checkers.rpmdiff:RpmDiff',
            'pkgdiff = rebasehelper.plugins.checkers.pkgdiff:PkgDiff',
            'abipkgdiff = rebasehelper.plugins.checkers.abipkgdiff:AbiPkgDiff',
            'csmock = rebasehelper.plugins.checkers.csmock:CsMock',
            'licensecheck = rebasehelper.plugins.checkers.licensecheck:LicenseCheck',
        ],
        'rebasehelper.spec_hooks': [
            'typo-fix = rebasehelper.plugins.spec_hooks.typo_fix:TypoFix',
            'pypi-url-fix = rebasehelper.plugins.spec_hooks.pypi_url_fix:PyPIURLFix',
            'ruby-helper = rebasehelper.plugins.spec_hooks.ruby_helper:RubyHelper',
            'commit-hash-updater = rebasehelper.plugins.spec_hooks.commit_hash_updater:CommitHashUpdater',
            'paths-to-rpm-macros = rebasehelper.plugins.spec_hooks.paths_to_rpm_macros:PathsToRPMMacros',
            'escape-macros = rebasehelper.plugins.spec_hooks.escape_macros:EscapeMacros',
            'replace-old-version = rebasehelper.plugins.spec_hooks.replace_old_version:ReplaceOldVersion',
        ],
        'rebasehelper.build_log_hooks': [
            'files = rebasehelper.plugins.build_log_hooks.files:Files',
        ],
        'rebasehelper.versioneers': [
            'anitya = rebasehelper.plugins.versioneers.anitya:Anitya',
            'pypi = rebasehelper.plugins.versioneers.pypi:PyPI',
            'rubygems = rebasehelper.plugins.versioneers.rubygems:RubyGems',
            'npmjs = rebasehelper.plugins.versioneers.npmjs:NPMJS',
            'cpan = rebasehelper.plugins.versioneers.cpan:CPAN',
            'hackage = rebasehelper.plugins.versioneers.hackage:Hackage',
        ],
        'rebasehelper.output_tools': [
            'json = rebasehelper.plugins.output_tools.json_:JSON',
            'text = rebasehelper.plugins.output_tools.text:Text',
        ]
    },
    install_requires=get_requirements(),
    setup_requires=[],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development',
        'Topic :: System :: Operating System',
        'Topic :: System :: Software Distribution',
        'Topic :: Utilities',
    ],
    project_urls={
        'Source Code': 'https://github.com/rebase-helper/rebase-helper',
        'Documentation': 'https://rebase-helper.readthedocs.io',
        'Bug Tracker': 'https://github.com/rebase-helper/rebase-helper/issues',
    }
)
