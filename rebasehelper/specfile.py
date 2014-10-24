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
import re
import shutil
import six
try:
    import rpm
except ImportError:
    pass

from rebasehelper.utils import DownloadHelper
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
    rpm_sections = {}

    defined_sections = ['%package',
                        '%description',
                        '%prep',
                        '%build',
                        '%install',
                        '%check',
                        '%files',
                        '%changelog']

    def __init__(self, path, download=True):
        self.path = path
        self.download = download
        #  Read the content of the whole SPEC file
        self._read_spec_content()
        #  SPEC file content filtered from commented lines
        self._update_filtered_spec_content()
        self._update_data()

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

    def copy(self, new_path=None):
        """
        Create a copy of the current object and copy the SPEC file the new object
        represents to a new location.

        :param new_path: new path to which to copy the SPEC file
        :return: copy of the current object
        """
        if new_path:
            shutil.copy(self.path, new_path)
        new_object = SpecFile(new_path, self.download)
        return new_object

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
        new_spec_file = []

        try:
            for key, value in sorted(six.iteritems(self.rpm_sections)):
                sec_name, section = value
                if '%header' in sec_name:
                    new_spec_file.extend(section)
                else:
                    new_spec_file.append(sec_name + '\n')
                    new_spec_file.extend(section)
        except KeyError:
            raise RebaseHelperError("Unable to find a specific section in SPEC file")

        return new_spec_file

    def _split_sections(self):
        """
        Function split spec file to well known SPEC sections

        :return: position and content of section in format like
            [0, (%files, [list of all rows within %files section],
             1, (%files debug, [list of all rows within %files debug section]]
        """
        # rpm-python does not provide any directive for getting %files section
        # Therefore we should do that workaround
        section_headers_re = [re.compile('^{0}.*'.format(x)) for x in self.defined_sections]

        section_starts = []
        # First of all we need to find beginning of all sections
        for line_num, line in enumerate(self.spec_content):
            # it might be a section
            if line.startswith('%'):
                # check all possible section headers
                for section_header in section_headers_re:
                    if section_header.search(line):
                        section_starts.append(line_num)

        # determine the SPEC header
        # it is everything until the beginning the first section
        header_end = section_starts[0] if section_starts else len(self.spec_content)
        sections = {0: ('%header', self.spec_content[:header_end])}

        # now determine all previously found sections
        for i in range(len(section_starts)):
            # We cut a relevant section to field
            if i + 1 < len(section_starts):
                curr_section = self.spec_content[section_starts[i]:section_starts[i+1]]
            else:
                curr_section = self.spec_content[section_starts[i]:]
            sections[i+1] = (curr_section[0].strip(), curr_section[1:])

        return sections

    def get_spec_section(self, section_name):
        """
        Returns the section of selected name

        :param section_name: section name to get
        :return: list of lines contained in the selected section
        """
        for sec_name, section in six.itervalues(self.rpm_sections):
            if sec_name == section_name:
                return section

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
        return self.hdr[rpm.RPMTAG_VERSION].decode()

    def get_package_name(self):
        """
        Function returns a package name
        :return:
        """
        return self.hdr[rpm.RPMTAG_NAME].decode()

    def get_requires(self):
        """
        Function returns a package reuirements
        :return:
        """
        return [r.decode() for r in self.hdr[rpm.RPMTAG_REQUIRES]]

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

    def _get_raw_source_string(self, source_num):
        """
        Method returns raw string, possibly with RPM macros, of a Source with passed number.

        :param source_num: number of the source of which to get the raw string
        :return: string of the source or None if there is no such source
        """
        source_rexex_str = '^Source{0}:[ \t]*(.*?)$'.format(source_num)
        source_rexex = re.compile(source_rexex_str)

        for line in self.spec_content:
            match = source_rexex.search(line)
            if match:
                return match.group(1)

    @staticmethod
    def get_header_from_rpm(rpm_name):
        """
        Function returns a rpm header from given rpm package
        for later on analysis
        :param pkg_name:
        :return:
        """
        ts = rpm.TransactionSet()
        h = None
        with open(rpm_name, "r") as f:
            h = ts.hdrFromFdno(f)
        return h

    @staticmethod
    def get_info_from_rpm(rpm_name, info):
        """
        Method returns a name of the package from RPM file format
        :param pkg_name:
        :return:
        """
        h = SpecFile.get_header_from_rpm(rpm_name)
        name = h[info]
        return name

    @staticmethod
    def get_paths_with_rpm_macros(files):
        """
        Method modifies paths in passed list to use RPM macros

        :param files: list of absolute paths
        :return: modified list of paths with RPM macros
        """
        macro_mapping = {'/usr/lib64': '%{_libdir}',
                         '/usr/libexec': '%{_libexecdir}',
                         '/usr/lib/systemd/system': '%{_unitdir}',
                         '/usr/lib': '%{_libdir}',
                         '/usr/bin': '%{_bindir}',
                         '/usr/sbin': '%{_sbindir}',
                         '/usr/include': '%{_includedir}',
                         '/usr/share/man': '%{_mandir}',
                         '/usr/share/info': '%{_infodir}',
                         '/usr/share/doc': '%{_docdir}',
                         '/usr/share': '%{_datarootdir}',
                         '/var/lib': '%{_sharedstatedir}',
                         '/var/tmp': '%{_tmppath}',
                         '/var': '%{_localstatedir}',
                         }
        for index, filename in enumerate(files):
            for abs_path, macro in sorted(six.iteritems(macro_mapping), reverse=True):
                if filename.startswith(abs_path):
                    files[index] = filename.replace(abs_path, macro)
                    break
        return files

    @staticmethod
    def construct_string_with_comment(lines):
        """
        Wraps the line in a rebase-helper specific comments

        :param lines: line (or list of lines) to be wrapped
        :return: list with lines
        """
        comm_lines = [settings.BEGIN_COMMENT]
        for l in lines if not isinstance(lines, six.string_types) else [lines]:
            comm_lines.append(l)
        comm_lines.append(settings.END_COMMENT)
        return comm_lines

    def _correct_missing_files(self, missing):
        sep = '\n'
        for key, value in six.iteritems(self.rpm_sections):
            sec_name, sec_content = value
            match = re.search(r'^%files\s*$', sec_name)
            if match:
                if settings.BEGIN_COMMENT in sec_content:
                    # We need only files which are not included yet.
                    upd_files = [f for f in missing if f not in sec_content]
                    regex = re.compile('(' + settings.BEGIN_COMMENT + '\s*)')
                    sec_content = regex.sub('\\1' + '\n'.join(upd_files) + sep,
                                            sec_content)
                else:
                    # This code adds begin_comment, files and end_comment
                    # with separator
                    sec_content = SpecFile.construct_string_with_comment(missing) + sec_content
                self.rpm_sections[key] = (sec_name, sec_content)
                break

    def _correct_removed_files(self, sources):
        for key, value in six.iteritems(self.rpm_sections):
            sec_name, sec_content = value
            # Only sections %files are interesting
            match = re.search(r'^%files', sec_name)
            if match:
                # Check what files are in section
                # and comment only relevant
                f_exists = [f for f in sources if os.path.basename(f) in sec_content]
                if not f_exists:
                    continue
                for f in f_exists:
                    sec_content = sec_content.split('\n')
                    for index, row in enumerate(sec_content):
                        if f in row:
                            sec_content[index] = SpecFile.construct_string_with_comment('#' + row)
                self.rpm_sections[key] = (sec_name, '\n'.join(sec_content))

    def modify_spec_files_section(self, files):
        """
        Function repairs spec file according to new sources.
        :param files:
        :return:
        """
        # Files which are missing in SPEC file.
        try:
            if files['missing']:
                upd_files = SpecFile.get_paths_with_rpm_macros(files['missing'])
                self._correct_missing_files(upd_files)
        except KeyError:
            pass

        # Files which does not exist in SOURCES.
        # Should be removed from SPEC file.
        try:
            if files['sources']:
                upd_files = SpecFile.get_paths_with_rpm_macros(files['sources'])
                self._correct_removed_files(upd_files)
        except KeyError:
            pass

        self.spec_content = self._create_spec_from_sections()
        self.save()

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
        Method to update the version in the SPEC file

        :param version: string with new version
        :return:
        """
        for index, line in enumerate(self.spec_content):
            if not line.startswith('Version'):
                continue
            logger.debug("SpecFile: Updating version in SPEC from '{0}' with '{1}'".format(self.get_version(),
                                                                                           version))
            self.spec_content[index] = line.replace(self.get_version(), version)
            break
        #  save changes to the disc
        self.save()

    def set_version_using_archive(self, archive_path):
        """
        Method to update the version in the SPEC file using a archive path. The version
        is extracted from the archive name.

        :param archive_path:
        :return:
        """
        version, extra_version = SpecFile.extract_version_from_archive_name(archive_path,
                                                                            self._get_raw_source_string(0))
        # TODO: Handle the extra version to change the release number
        self.set_version(version)

    def write_updated_patches(self, patches):
        """
        Function writes the patches to -rebase.spec file
        """
        #  TODO: this method should not take whole kwargs as argument, take only what it needs.
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
                        #del patches[int(patch_num)]
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

    @staticmethod
    def split_version_string(version_string=''):
        """
        Method splits version string into version and possibly extra string as 'rc1' or 'b1', ...

        :param version_string: version string such as '1.1.1' or '1.2.3b1', ...
        :return: tuple of strings with (extracted version, extra version) or (None, None) if extraction failed
        """
        version_split_regex_str = '([.0-9]+)(\w*)'
        version_split_regex = re.compile(version_split_regex_str)
        logger.debug("split_version_string: Splitting string '{0}'".format(version_string))
        match = version_split_regex.search(version_string)
        if match:
            version = match.group(1)
            extra_version = match.group(2)
            logger.debug("split_version_string: Divided version '{0}' and extra string {1}".format(version,
                                                                                                   extra_version))
            return version, extra_version
        else:
            return None, None

    @staticmethod
    def extract_version_from_archive_name(archive_path, source_string=''):
        """
        Method extracts the version from archive name based on the source string from SPEC file.
        It extracts also an extra version such as 'b1', 'rc1', ...

        :param archive_path: archive name or path with archive name from which to extract the version
        :param source_string: Source string from SPEC file used to construct version extraction regex
        :return: tuple of strings with (extracted version, extra version) or (None, None) if extraction failed
        """
        version_regex_str = '([.0-9]+\w*)'
        fallback_regex_str = '^\w+-?_?v?{0}({1})'.format(version_regex_str,
                                                         '|'.join(Archive.get_supported_archives()))
        # match = re.search(regex, tarball_name)
        name = os.path.basename(archive_path)
        url_base = get_source_name(source_string)

        logger.debug("Extracting version from '{0}' using '{1}'".format(name, url_base))
        regex_str = re.sub(r'%{version}', version_regex_str, url_base, flags=re.IGNORECASE)

        # if no substitution was made, use the fallback regex
        if regex_str == url_base:
            logger.debug('Using fallback regex to extract version from archive name.')
            regex_str = fallback_regex_str

        logger.debug("Extracting version using regex '{0}'".format(regex_str))
        regex = re.compile(regex_str)
        match = regex.search(name)
        if match:
            version = match.group(1)
            logger.debug("Extracted version '{0}'".format(version))
            return SpecFile.split_version_string(version)
        else:
            logger.debug('Failed to extract version from archive name!')
            #  TODO: look at this if it could be rewritten in a better way!
            #  try fallback regex if not used this time
            if regex_str != fallback_regex_str:
                logger.debug("Trying to extracting version using fallback regex '{0}'".format(fallback_regex_str))
                regex = re.compile(fallback_regex_str)
                match = regex.search(name)
                if match:
                    version = match.group(1)
                    logger.debug("Extracted version '{0}'".format(version))
                    return SpecFile.split_version_string(version)
                else:
                    logger.debug('Failed to extract version from archive name using fallback regex!')
            return SpecFile.split_version_string('')
