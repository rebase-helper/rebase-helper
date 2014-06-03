try:
    from functools import reduce
except ImportError:
    pass # we're on Python 2 => ok
import re
import os
import rpm
from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger

SPECFILE_SECTIONS=['%header', # special "section" for the start of specfile
                   '%description',
                   '%package',
                   '%prep',
                   '%build',
                   '%install',
                   '%clean',
                   '%check',
                   '%files',
                   '%changelog']
RUNTIME_SECTIONS=['%prep', '%build', '%install', '%clean', '%check']
METAINFO_SECTIONS=['%header', '%package']

class Specfile(object):
    
    values = []
    def __init__(self, specfile):
        self.specfile = specfile
        self.spc = rpm.spec(self.specfile)

    def split_sections(self):
        headers_re = [re.compile('^' + x, re.M) for x in SPECFILE_SECTIONS]
        section_starts = []
        for header in headers_re:
            for match in header.finditer(self.specfile):
                section_starts.append(match.start())

        section_starts.sort()
        print section_starts
        # this is mainly for tests - if the header is the only section
        header_end = section_starts[0] if section_starts else len(self.specfile)
        sections = [('%header', self.specfile[:header_end])]
        for i in range(len(section_starts)):
            if len(section_starts) > i + 1:
                curr_section = self.specfile[section_starts[i]:section_starts[i+1]]
            else:
                curr_section = self.specfile[section_starts[i]:]
            #print 'Curr_section',curr_section
            for header in headers_re:
                if header.match(curr_section):
                    #print 'append',(header.pattern[1:], curr_section)
                    sections.append((header.pattern[1:], curr_section))

        return sections

    def __contains__(self, what):
        return reduce(lambda x, y: x or (what in y[1]), self.sections, False)

    def __str__(self):
        # in tests (maybe in reality, too), we may have an empty header, which will result in
        # putting unnecessary newlines on top => leave out empty sections from joining
        return '\n\n'.join([section for section in list(zip(*self.sections))[1] if section])

    def _filter_section(self, section):
        section = filter(lambda x: x[0] == section, self.sections)[0]
        section = section[1].split('\n')
        return section[1:]
        
    def _get_build_flags(self, build_section, flag):
        next_line = False
        for b in build_section:
            b = b.strip()
            if next_line:
                if not b.endswith('\\'):
                    self.values.append(b)
                    break
                b = b.replace('\\','').strip()
                self.values.append(b)
            elif flag in b:
                if b.endswith('\\'):
                    next_line = True
                b = b.replace('\\','').replace(flag,'').strip()
                b = b.split(' ')
                self.values.extend(b)
    
    def _get_sections(self, section, parameters=[]):
        requested_section = self.spc.build
        self.values = []
        for param in parameters:
            self._get_build_flags(requested_section,param)
        return self.values
            
        
    def get_config_options(self):
        requested_section = self.spc.build
        self.values = []
        for param in ['./configure']:
            self._get_build_flags(requested_section.split('\n'),param)
        return self.values
        
    def get_make_options(self):
        requested_section = self.spc.build
        self.values = []
        for param in ['make']:
            self._get_build_flags(requested_section.split('\n'),param)
        return self.values
    
    def _correct_install_prefix(self):
        for value in self.values:
            print 'PREFIX:',value
        
    def get_make_install_options(self):
        requested_section = self.spc.install
        self.values = []
        for param in ['make']:
            self._get_build_flags(requested_section.split('\n'),param)
        self._correct_install_prefix()
            
        return self.values

    def get_patch_option(self, line):
        spl = line.strip().split()
        if len(spl) == 1:
            return spl[0], " "
        elif len(spl) == 2:
            return spl[0], spl[1]
        else:
            return spl[0], spl[1]

    def get_patch_flags(self):
        patch_flags = {}
        with open(self.specfile, "r") as spc_file:
            lines = spc_file.readlines()
            lines = [x for x in lines if x.startswith('%patch')]
            for line in lines:
                num, option = self.get_patch_option(line)
                num = num.replace('%patch','')
                patch_flags[int(num)] = option
        return patch_flags
        
    def get_patches(self):
        patches = {}
        patch_flags = self.get_patch_flags()
        for source in self.spc.sources:
            try:
                patch, num, patch_type = source
            except IndexError:
                print 'Problem with getting patches'
                return None
            # Patch has flag 2
            if int(patch_type) != 2:
                continue
            full_patch_name = patch
            if not os.path.exists(full_patch_name):
                logger.error('Patch {0} does not exist'.format(patch))
                continue
            patches[num] = [full_patch_name, patch_flags[num]]
        return patches

    def get_old_sources(self):
        old_sources = None
        source_name = ""
        for source in self.spc.sources:
            try:
                source, num, source_type = source
            except IndexError:
                logger.error('Problem with getting source')
                return None
            if int(num) == 0:
                old_sources = source
                break

        source_name = old_sources.split('/')[-1]
        if not os.path.exists(source_name):
            ProcessHelper.run_subprocess_cwd('wget {0}'.format(old_sources), shell=True)
        return source_name
