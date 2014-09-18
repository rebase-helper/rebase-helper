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

try:
    from functools import reduce
except ImportError:
    pass  # we're on Python 2 => ok
import os
try:
    import rpm
except ImportError:
    pass
import re
from StringIO import StringIO
from rebasehelper.utils import DownloadHelper, ProcessHelper
from rebasehelper.logger import logger
from rebasehelper import settings
from rebasehelper.utils import check_empty_patch
from rebasehelper.archive import Archive
from rebasehelper.exceptions import RebaseHelperError


PATCH_PREFIX = '%patch'


def get_source_name(name):
    """
    Function returns a source name from full URL address
    :param name:
    :return:
    """
    new_name = name.split('/')[-1]
    return new_name


def get_rebase_name(name):
    """
    Function returns a name in results directory
    :param name:
    :return: full path to results dir with name
    """
    dir_name = os.path.dirname(name)
    file_name = os.path.basename(name)
    return os.path.join(dir_name, settings.REBASE_HELPER_RESULTS_DIR, file_name)


class SpecFile(object):
    """
    Class representing a SPEC file
    """
    path = ''
    download = False
    spec_content = []
    spec_filtered_content = []
    spc = None
    hdr = None
    sources = None
    source_files = None
    patches = None
    parsed_spec_file = ""
    rpm_sections = {}

    defined_sections = ['%headers',
                        '%files',
                        '%changelog',
                        '%build',
                        '%check',
                        '%install',
                        '%description',
                        '%package',
                        '%prep']

    def __init__(self, path, sources=None, download=True):
        self.path = path
        self.download = download
        #  Read the content of the whole SPEC file
        self._read_spec_content()
        #  SPEC file content filtered from commented lines
        self._update_filtered_spec_content()

        self._update_data()
        if sources:
            self.new_sources = sources
            self.set_spec_version()

    def _update_data(self):
        """
        Function updates data from given SPEC file
        :return:
        """
        # Load rpm information
        self.spc = rpm.spec(self.path)
        # HEADER of SPEC file
        self.hdr = self.spc.sourceHeader
        # ALL sources mentioned in SPEC file
        self.sources = self.spc.sources
        # All patches mentioned in SPEC file
        self.patches = [x for x in self.sources if x[2] == 2]
        # All source file mentioned in SPEC file Source[0-9]*
        self.source_files = [x for x in self.sources if x[2] == 0 or x[2] == 1]
        self.rpm_sections = self._split_sections()

    def get_patch_option(self, line):
        """
        Function returns a patch options
        :param line:
        :return: patch options like -p1
        """
        spl = line.strip().split()
        if len(spl) == 1:
            return spl[0], ''
        else:
            return spl[0], spl[1]

    def _create_spec_from_sections(self):
        # Spec file has defined order
        # First we write a header
        new_spec_file = ""

        try:
            for key, value in sorted(self.rpm_sections.iteritems()):
                sec_name, section = value
                if '%header' in sec_name:
                    new_spec_file = section
                else:
                    new_spec_file += sec_name + '\n' + section
        except KeyError:
            raise RebaseHelperError("Unable to find a specific section in SPEC file")

        try:
            with open(self.path, 'w') as f:
                f.write(new_spec_file)
        except IOError:
            raise RebaseHelperError("Unable to open and write new SPEC file '{0}'".format(self.path))

    def _split_sections(self):
        """
        Function split spec file to defined sections
        :return: position and content of section in format like
            [0, (%files, <all rows within %files section>,
             1, (%files debug, <all rows within %files debug section>]
        """
        # rpm-python does not provide any directive for getting %files section
        # Therefore we should do that workaround
        self.parsed_spec_file = ''.join(self.spec_content)
        headers_re = [re.compile('^' + x, re.M) for x in self.defined_sections]

        section_starts = []
        # First of all we need to find a specific sections
        for header in headers_re:
            for match in header.finditer(self.parsed_spec_file):
                section_starts.append(match.start())

        section_starts.sort()
        header_end = section_starts[0] if section_starts else len(self.parsed_spec_file)
        sections = {}
        sections[0] = ('%header', self.parsed_spec_file[:header_end])

        for i in range(len(section_starts)):
            # We cut a relevant section to field
            if len(section_starts) > i + 1:
                curr_section = self.parsed_spec_file[section_starts[i]:section_starts[i+1]]
            else:
                curr_section = self.parsed_spec_file[section_starts[i]:]
            for header in headers_re:
                if header.match(curr_section):
                    fields = curr_section.split('\n')
                    sections[i+1] = (fields[0], '\n'.join(fields[1:]))
        return sections

    def get_files_sections(self):
        pkg_files = []
        for key, section in self.rpm_sections.iteritems():
            tag, sec = section
            if '%files' in tag:
                pkg_files.extend([f for f in sec.split('\n') if f.startswith('/')])
        return pkg_files

    def _get_patch_number(self, fields):
        """
        Function returns patch number
        :param line:
        :return: patch_num
        """
        patch_num = fields[0].replace('Patch', '')[:-1]
        return patch_num

    def _read_spec_content(self):
        """
        Method reads the content SPEC file and updates internal variables.
        """
        try:
            with open(self.path) as f:
                lines = f.readlines()
        except IOError:
            raise RebaseHelperError("Unable to open and read SPEC file '{0}'".format(self.path))
        #  Complete SPEC file content
        self.spec_content = lines

    def _get_patches_flags(self):
        """
        For all patches: get flags passed to %patch macro and index of application
        """
        patch_flags = {}
        patches = [x for x in self.spec_content if x.startswith(PATCH_PREFIX)]
        for index, line in enumerate(patches):
            num, option = self.get_patch_option(line)
            num = num.replace(PATCH_PREFIX, '')
            patch_flags[int(num)] = (option, index)
        # {num: (flags, index of application)}
        return patch_flags

    def get_information(self):
        """
        Function creates a dictionary and returns them
        with all information from SPEC file
        :return:
        """
        #  TODO: we should get rid of kwargs, also we should not create it in SPEC file object
        kwargs = {}
        kwargs[settings.FULL_PATCHES] = self.get_patches()
        kwargs['sources'] = self.get_sources()
        kwargs['name'] = self.get_package_name()
        kwargs['version'] = self.get_version()
        kwargs['tarball'] = self.get_archive()
        return kwargs

    def get_version(self):
        """
        Method returns the version
        :return:
        """
        return self.hdr[rpm.RPMTAG_VERSION]

    def get_package_name(self):
        """
        Function returns a package name
        :return:
        """
        return self.hdr[rpm.RPMTAG_NAME]

    def get_requires(self):
        """
        Function returns a package reuirements
        :return:
        """
        return self.hdr[rpm.RPMTAG_REQUIRES]

    def is_patch_git_generated(self, full_patch_name):
        """
        Return:
          True if patch is generated by git ('git diff' or 'git format-patch')
          False means patch is generated by gendiff or somehow else.
        """
        #  TODO: move this method to patch_helper?
        with open(full_patch_name) as inputfile:
            for line in inputfile:
                if line.startswith("diff "):
                    if line.startswith("diff --git"):
                        return True
                    else:
                        return False
        return False

    def get_patches(self):
        """
        Function returns a list of patches from a spec file
        """
        patches = {}
        patch_flags = self._get_patches_flags()
        cwd = os.getcwd()
        for source in self.patches:
            filename, num, patch_type = source
            full_patch_name = os.path.join(cwd, filename)
            if not os.path.exists(full_patch_name):
                logger.error('Patch {0} does not exist'.format(filename))
                continue
            if num in patch_flags:
                #  TODO: Why do we need to know here if patch is git generated??
                patches[num] = [full_patch_name, patch_flags[num][0],
                                patch_flags[num][1], self.is_patch_git_generated(full_patch_name)]
        # list of [name, flags, index, git_generated]
        return patches

    def _update_spec_path(self, files):
        type_mapping = {'/usr/lib': '%{_libdir}',
                        '/usr/bin': '%{_bindir}',
                        '/usr/sbin': '%{_sbindir}',
                        '/usr/include': '%{_includedir}'}
        for index, filename in enumerate(files):
            for key, value in type_mapping.iteritems():
                if filename.startswith(key):
                    fields = filename.split('/')[3:]
                    files[index] = value + '/' + '/'.join(fields)
        return files

    def correct_spec(self, files):
        """
        Function repairs spec file according to new sources.
        :param files:
        :return:
        """
        begin_comment = '#BEGIN THIS MODIFIED BY REBASE-HELPER'
        end_comment = '#END THIS MODIFIED BY REBASE-HELPER'
        sep = '\n'
        # Files which are missing in SPEC file.
        if 'missing' in files:
            files = self._update_spec_path(files['missing'])
            for key, value in self.rpm_sections.iteritems():
                sec_name, sec_content = value
                match = re.search(r'^%files\s*$', sec_name)
                if match:
                    if begin_comment in sec_content:
                        regex = re.compile('(^' + begin_comment + '\s*)')
                        sec_content = regex.sub('\\1' + '\n'.join(files) + sep,
                                                sec_content)
                    else:
                        sec_content = begin_comment + sep
                        sec_content += '\n'.join(files) + sep
                        sec_content += end_comment + sep
                    self.rpm_sections[key] = (sec_name, sec_content)
                    break

        # Files which does not exist in SOURCES.
        # Should be removed from SPEC file.
        if 'sources' in files:
            files = self._update_spec_path(files['sources'])
            print files
            for key, value in self.rpm_sections.iteritems():
                sec_name, sec_content = value
                match = re.search(r'^%files', sec_name)
                if match:
                    pass
        self._create_spec_from_sections()

    def _download_source(self, source_name, destination):
        """
        Function downloads a source name defined in SPEC file
        """
        if not self.download:
            return
        if not os.path.exists(destination):
            ret_code = DownloadHelper.download_source(source_name, destination)

    def _write_spec_file_to_disc(self):
        """
        Write the current SPEC file to the disc
        """
        logger.debug("SpecFile: Writing SPEC file '{0}' to the disc".format(self.path))
        try:
            with open(self.path, "w") as f:
                f.writelines(self.spec_content)
        except IOError:
            raise RebaseHelperError("Unable to write updated data to SPEC file '{0}'".format(self.path))

    def _update_filtered_spec_content(self):
        """
        Update the internal variable for SPEC content without commented lines
        """
        self.spec_filtered_content = [l for l in self.spec_content if not l.strip().startswith('#')]

    def get_sources(self):
        """
        Function returns all sources mentioned in specfile
        """
        #  TODO: this might not be a good idea - should we use EXECUTION DIR?
        cwd = os.getcwd()
        sources = []
        remote_files = ['http:', 'https:', 'ftp:']
        for index, src in enumerate(self.source_files):
            new_name = get_source_name(src[0])
            if int(src[1]) == 0:
                sources.append(os.path.join(cwd, new_name))
            else:
                remote = [x for x in remote_files if src[0].startswith(x)]
                if remote:
                    self._download_source(src[0], new_name)
                sources.append(os.path.join(cwd, new_name))
        return sources

    def get_archive(self):
        """
        Function returns a old sources from specfile
        """
        full_source_name = self._get_full_source_name()
        source_name = get_source_name(full_source_name)
        self._download_source(full_source_name, source_name)
        return source_name

    def _get_full_source_name(self):
        """
        Function returns a source name provided by Source [0]
        List has format [(<name>, <type, 1), (other source)]
        <type> has values:
        - 0 means Source 0
        - 1 means Source > 0
        - 2 means Patches
        """
        source = [src[0] for src in self.source_files if src[1] == 0]
        # We need just a name
        return source[0]

    def _comment_out_patches(self, patch_num):
        """
        Comment out patches from SPEC file

        :var patch_num: list with patch numbers to comment out
        """
        for index, line in enumerate(self.spec_content):
            #  if patch is applied on the line, try to check if it should be commented out
            if line.startswith('%patch'):
                #  check patch numbers
                for num in patch_num:
                    #  if the line should be commented out
                    if line.startswith('%patch{0}'.format(num)):
                        self.spec_content[index] = '#%' + line
                        #  remove the patch number from list
                        patch_num.remove(num)
                        break

    def set_version(self, version):
        """
        Function updates a version in SPEC file
        based on self.new_sources variable
        """
        for index, line in enumerate(self.spec_content):
            if not line.startswith('Version'):
                continue
            logger.debug("SpecFile: Updating version in SPEC from '{0}' with '{1}'".format(self.get_version(),
                                                                                           version))
            self.spec_content[index] = line.replace(self.get_version(), version)

    def set_spec_version(self):
        """
        Function updates a version in spec file based on input argument
        """
        #  TODO: This logic should go to application. SPEC should get only new version!
        archive_ext = None
        for ext in Archive.get_supported_archives():
            if self.new_sources.endswith(ext):
                archive_ext = ext
                break

        if not archive_ext:
            # CLI argument is probably just a version without name and extension
            self.set_version(self.new_sources)
            self.save()
            # We need to reload the spec file
            old_source_name = self._get_full_source_name()
            self.new_sources = get_source_name(old_source_name)
            return self.new_sources
        # TODO: We should move the version extraction code to a separate method and add extensive tests!
        tarball_name = self.new_sources.replace(archive_ext, '')
        regex = re.compile(r'^\w+-?_?v?(.*)')
        match = re.search(regex, tarball_name)
        if match:
            new_version = match.group(1)
            logger.debug("SpecFile: Version extracted from archive '{0}'".format(new_version))
            self.set_version(new_version)
            self.save()
        return None

    def write_updated_patches(self, **kwargs):
        """
        Function writes the patches to -rebase.spec file
        """
        #  TODO: this method should not take whole kwargs as argument, take only what it needs.
        new_files = kwargs.get('new', None)
        if not new_files:
            return None
        patches = new_files.get('patches', None)
        if not patches:
            return None

        updated_patches = {}
        updated_patches['deleted'] = []
        updated_patches['modified'] = []

        removed_patches = []
        for index, line in enumerate(self.spec_content):
            if line.startswith('Patch'):
                fields = line.strip().split()
                patch_num = self._get_patch_number(fields)
                #  TODO: Add explanation comment
                if int(patch_num) not in patches:
                    continue
                patch_name = patches[int(patch_num)][0]
                comment = ""
                #  TODO: this method should not check this, but rather get final list of removed/empty patches (probably from Patch tool)
                #  TODO: This while logic should go to Patch tool, not into SPEC file!
                if settings.REBASE_HELPER_RESULTS_DIR in patch_name:
                    if check_empty_patch(patch_name):
                        comment = '#'
                        removed_patches.append(patch_num)
                        del patches[int(patch_num)]
                        updated_patches['deleted'].append(patch_name)
                    else:
                        updated_patches['modified'].append(patch_name)
                #  TODO: this commenting should be done in _comment_out_patches() method
                self.spec_content[index] = comment + ' '.join(fields[:-1]) + ' ' + os.path.basename(patch_name) + '\n'

        self._comment_out_patches(removed_patches)
        #  save changes
        self.save()
        return updated_patches

    def save(self):
        """
        Save changes made to the spec_content to the disc and update internal variables
        """
        #  Update filtered SPEC content
        self._update_filtered_spec_content()
        #  Write changes to the disc
        self._write_spec_file_to_disc()
        #  Update internal variables
        self._update_data()
