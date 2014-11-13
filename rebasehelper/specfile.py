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
from difflib import SequenceMatcher
try:
    import rpm
except ImportError:
    pass

from rebasehelper.utils import DownloadHelper
from rebasehelper.logger import logger
from rebasehelper import settings
from rebasehelper.archive import Archive
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.diff_helper import GenericDiff


PATCH_PREFIX = '%patch'


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
    spc = None
    hdr = None
    extra_version = None
    sources = None
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

    def __init__(self, path, sources_location='', download=True):
        self.path = path
        self.download = download
        self.sources_location = sources_location
        #  Read the content of the whole SPEC file
        self._read_spec_content()
        # Load rpm information
        self.spc = rpm.spec(self.path)
        self.patches = self._get_initial_patches_list()
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
        # All source file mentioned in SPEC file Source[0-9]*
        self.rpm_sections = self._split_sections()
        # determine the extra_version
        logger.debug("SpecFile: _update_data(): Updating the extra version")
        self.sources = self._get_initial_sources_list()
        self.extra_version = SpecFile.extract_version_from_archive_name(self.get_archive(),
                                                                        self._get_raw_source_string(0))[1]

    def _get_initial_sources_list(self):
        """
        Function returns all sources mentioned in SPEC file
        """
        # get all regular sources
        sources = []
        sources_list = [x for x in self.spc.sources if x[2] == 1]
        remote_files_re = re.compile(r'(http:|https:|ftp:)//.*')

        for index, src in enumerate(sources_list):
            abs_path = os.path.join(self.sources_location, os.path.basename(src[0]).strip())
            # if the source is a remote file, download it
            if remote_files_re.search(src[0]):
                self._download_source(src[0], abs_path)
            # the Source0 has to be at the beginning!
            if src[1] == 0:
                sources.insert(0, abs_path)
            else:
                sources.append(abs_path)
        return sources

    def _get_initial_patches_list(self):
        """
        Method returns a list of patches from a spec file
        """
        patches = {}
        patches_list = [p for p in self.spc.sources if p[2] == 2]
        patch_flags = self._get_patches_flags()

        for filename, num, patch_type in patches_list:
            patch_path = os.path.join(self.sources_location, filename)
            if not os.path.exists(patch_path):
                logger.error('Patch {0} does not exist'.format(filename))
                continue
            if num in patch_flags:
                #  TODO: Why do we need to know here if patch is git generated??
                patches[num] = [patch_path, patch_flags[num][0],
                                patch_flags[num][1], self.is_patch_git_generated(patch_path)]
        # dict with <num>: [name, flags, index, git_generated]
        return patches

    def copy(self, new_path=None):
        """
        Create a copy of the current object and copy the SPEC file the new object
        represents to a new location.

        :param new_path: new path to which to copy the SPEC file
        :return: copy of the current object
        """
        if new_path:
            shutil.copy(self.path, new_path)
        new_object = SpecFile(new_path, self.sources_location, self.download)
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

    def get_path(self):
        """
        Return only spec file path
        :return:
        """
        return self.path

    def is_test_suite_enabled(self):
        """
        Returns whether test suite is enabled during the build time
        :return: True if enabled or False if not
        """
        check_section = self.get_spec_section('%check')
        if not check_section:
            return False
        # Remove commented lines
        check_section = [x.strip() for x in check_section if not x.strip().startswith('#')]
        # If there is at least one line with some command in %check we assume test suite is run
        if check_section:
            return True
        else:
            return False

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

    def get_release(self):
        """
        Method for getting full release string of the package
        :return:
        """
        return self.hdr[rpm.RPMTAG_RELEASE].decode()

    def get_release_number(self):
        """
        Method for getting the release of the package
        :return:
        """
        for line in self.spec_content:
            match = re.search(r'Release:\s*([0-9.]+).*%{\?dist}\s*', line)
            if match:
                return match.group(1)

    def get_version(self):
        """
        Method returns the version
        :return:
        """
        return self.hdr[rpm.RPMTAG_VERSION].decode()

    def get_extra_version(self):
        """
        Returns an extra version of the package - like b1, rc2, ...
        :return: String
        """
        return self.extra_version

    def get_package_name(self):
        """
        Function returns a package name
        :return:
        """
        return self.hdr[rpm.RPMTAG_NAME].decode()

    def get_requires(self):
        """
        Function returns a package requirements
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
        Method returns dictionary with patches list.

        :return: dict with <num>: [path, flags, index, git_generated]
        """
        return self.patches

    def get_sources(self):
        """
        Method returns dictionary with sources list.

        :return:
        """
        return self.sources

    def get_archive(self):
        """
        Function returns the archive name from SPEC file
        """
        return os.path.basename(self.get_sources()[0]).strip()

    def _get_raw_source_string(self, source_num):
        """
        Method returns raw string, possibly with RPM macros, of a Source with passed number.

        :param source_num: number of the source of which to get the raw string
        :return: string of the source or None if there is no such source
        """
        source_re_str = '^Source0?:[ \t]*(.*?)$' if source_num == 0 else '^Source{0}:[ \t]*(.*?)$'.format(source_num)
        source_re = re.compile(source_re_str)

        for line in self.spec_content:
            match = source_re.search(line)
            if match:
                return match.group(1)

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
            if files['deleted']:
                upd_files = SpecFile.get_paths_with_rpm_macros(files['deleted'])
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

    def set_release_number(self, release):
        """
        Method to set release number
        :param release:
        :return:
        """
        for index, line in enumerate(self.spec_content):
            if line.startswith('Release:'):
                new_release_line = re.sub(r'(Release:\s*)[0-9.]+(.*%{\?dist}\s*)', r'\g<1>{0}\2'.format(release),
                                          line)
                logger.debug("SpecFile: Changing release line to '{0}'".format(new_release_line.strip()))
                self.spec_content[index] = new_release_line
                self.save()
                break

    def redefine_release_with_macro(self, macro):
        """
        Method redefines the Release: line to include passed macro and comments out the old line
        :param macro:
        :return:
        """
        for index, line in enumerate(self.spec_content):
            if line.startswith('Release:'):
                new_release_line = re.sub(r'(Release:\s*[0-9.]*[0-9]+).*(%{\?dist}\s*)', r'\g<1>{0}\2'.format(macro),
                                          line)
                logger.debug("SpecFile: Commenting out original Release line '{0}'".format(line.strip()))
                self.spec_content[index] = '#{0}'.format(line)
                logger.debug("SpecFile: Inserting new Release line '{0}'".format(new_release_line.strip()))
                self.spec_content.insert(index + 1, new_release_line)
                self.save()
                break

    def revert_redefine_release_with_macro(self, macro):
        """
        Method removes the redefined the Release: line with given macro and uncomments the old Release line.
        :param macro:
        :return:
        """
        search_re = re.compile('Release:\s*[0-9.]*[0-9]+{0}%{{\?dist}}\s*'.format(macro))

        for index, line in enumerate(self.spec_content):
            match = search_re.search(line)
            if match:
                # We will uncomment old line, so sanity check first
                if not self.spec_content[index - 1].startswith('#Release:'):
                    raise RebaseHelperError("Redefined Release line in SPEC is not 'commented out' "
                                            "old line: '{0}'".format(self.spec_content[index - 1].strip()))
                logger.debug("SpecFile: Uncommenting original Release line "
                             "'{0}'".format(self.spec_content[index - 1].strip()))
                self.spec_content[index - 1] = self.spec_content[index - 1].lstrip('#')
                logger.debug("SpecFile: Removing redefined Release line '{0}'".format(line.strip()))
                self.spec_content.pop(index)
                self.save()
                break

    def set_version(self, version):
        """
        Method to update the version in the SPEC file

        :param version: string with new version
        :return: None
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

    def set_extra_version(self, extra_version):
        """
        Method to update the extra version in the SPEC file. Redefined Source0 if needed and also changes
        Release accordingly.

        :param extra_version: the extra version string, if any (e.g. 'b1', 'rc2', ...)
        :return: None
        """
        extra_version_def = '%define REBASE_EXTRA_VER'
        extra_version_macro = '%{?REBASE_EXTRA_VER}'
        extra_version_re = re.compile('^{0}.*$'.format(extra_version_def))
        extra_version_line_index = None
        rebase_extra_version_def = '%define REBASE_VER %{version}%{REBASE_EXTRA_VER}\n'
        new_extra_version_line = '%define REBASE_EXTRA_VER {0}\n'.format(extra_version)

        logger.debug("SpecFile: Updating extra version in SPEC to '{0}'".format(extra_version))

        #  try to find existing extra version definition
        for index, line in enumerate(self.spec_content):
            match = extra_version_re.search(line)
            if match:
                extra_version_line_index = index
                break

        if extra_version:
            #  just update the existing extra version
            if extra_version_line_index is not None:
                self.spec_content[extra_version_line_index] = new_extra_version_line
            #  we need to create the extra version definition
            else:
                # insert the REBASE_VER and REBASE_EXTRA_VER definitions
                self.spec_content.insert(0, rebase_extra_version_def)
                self.spec_content.insert(0, new_extra_version_line)
                # change Release to 0.1 and append the extra version macro
                self.set_release_number('0.1')
                self.redefine_release_with_macro(extra_version_macro)
                # change the Source0 definition
                source0_re = re.compile(r'Source0?:.*')
                for index, line in enumerate(self.spec_content):
                    if source0_re.search(line):
                        # comment out the original Source0 line
                        logger.debug("SpecFile: Commenting out original Source0 line '{0}'".format(line.strip()))
                        self.spec_content[index] = '#{0}'.format(line)

                        # construct new archive name with %{REBASE_VER}
                        # replacing the version that will be used in Source0
                        basename_raw = os.path.basename(line.strip())
                        basename_expanded = self.get_archive()
                        match_blocks = list(SequenceMatcher(None, basename_raw, basename_expanded).get_matching_blocks())
                        new_basename_with_macro = '{0}{1}{2}'.format(basename_raw[:match_blocks[0][2]],
                                                                     '%{REBASE_VER}',
                                                                     basename_raw[match_blocks[1][0]:])
                        logger.debug("SpecFile: New Source0 basename with macro '{0}'".format(new_basename_with_macro))
                        # replace the archive name in old Source0 with new one
                        new_source0_line = str.replace(line, basename_raw, new_basename_with_macro)
                        logger.debug("SpecFile: Inserting new Source0 line '{0}'".format(new_source0_line.strip()))
                        self.spec_content.insert(index + 1, new_source0_line)
                        break
        else:
            # set the Release to 1 and revert the redefined Release with macro if needed
            self.set_release_number('1')
            self.revert_redefine_release_with_macro(extra_version_macro)
            # TODO: handle empty extra_version as removal of the definitions!

        #  save changes
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
        self.set_version(version)
        self.set_extra_version(extra_version)

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
                    if GenericDiff.check_empty_patch(patch_name):
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
        url_base = os.path.basename(source_string).strip()

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
