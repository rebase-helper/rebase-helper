try:
    from functools import reduce
except ImportError:
    pass # we're on Python 2 => ok
import re
import rpm

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
        #self.spec = []
        #with open(specfile,"r") as f:
        #    self.spec = f.readlines()
        self.specfile = ''.join(specfile)
        #self.sections = self.split_sections()
        self.spc = rpm.spec(self.specfile)        

    def split_sections(self):
        headers_re = [re.compile('^' + x, re.M) for x in SPECFILE_SECTIONS]
        section_starts = []
        for header in headers_re:
            for match in header.finditer(self.specfile):
                section_starts.append(match.start())

        section_starts.sort()
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
        
