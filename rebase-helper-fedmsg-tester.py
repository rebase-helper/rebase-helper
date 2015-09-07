#!/usr/bin/python -tt
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

# message example
# It requires fedmsg package
from __future__ import print_function
import fedmsg

msg = {u'project': {u'regex': None,
                    u'name': u'dropbox',
                    u'versions': [u'3.23', u'3.22', u'3.21', u'3.14', u'3.13', u'3.12', u'2.2.0'],
                    u'created_on': 1412175079.0,
                    u'version': u'3.23',
                    u'version_url': None,
                    u'updated_on': 1441023040.0,
                    u'homepage': u'https://pypi.python.org/pypi/dropbox',
                    u'id': 3853,
                    u'backend': u'pypi'},
       u'message': {u'versions': [u'3.23', u'3.22', u'3.21', u'3.14', u'3.13', u'3.12', u'2.2.0'],
                    u'old_version': u'3.22',
                    u'agent': u'anitya',
                    u'project': {u'regex': None,
                                 u'name': u'dropbox',
                                 u'versions': [u'3.23', u'3.22', u'3.21', u'3.14', u'3.13', u'3.12', u'2.2.0'],
                                 u'created_on': 1412175079.0,
                                 u'version': u'3.23',
                                 u'version_url': None,
                                 u'updated_on': 1440763839.0,
                                 u'homepage': u'https://pypi.python.org/pypi/dropbox',
                                 u'id': 3853, u'backend': u'pypi'},
                    u'upstream_version': u'3.23',
                    u'packages': [{u'package_name': u'python-dropbox',
                                   u'distro': u'Fedora'}],
                    u'odd_change': False},
       u'distro': None}
topic = "org.fedoraproject.prod.anitya.project.version.update"
endpoint = 'tcp://hub.fedoraproject.org:9940'
name = ""
fedmsg = {'msg': msg}
fedmsg.init()
fedmsg.publish(topic=topic,
               endpoint="",
               msg=fedmsg)

# Testing UpstreamMonitoring
if __name__ == "__main__":
    up = UpstreamMonitoring(name, endpoint, topic, fedmsg)
    up.process_messsage()
