try:
    from functools import reduce
except ImportError:
    pass # we're on Python 2 => ok
import re

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
    def __init__(self, specfile):
        self.spec = []
        with open(specfile,"r") as f:
            self.spec = f.readlines()
        self.specfile = ''.join(self.spec)
        self.sections = self.split_sections()

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
        flags = []
        next_line = False
        for b in build_section:
            b.strip()
            if next_line:
                flags.append(b)
                if not b.endswith('\\'):
                    next_line = False
            elif flag in b:
                if b.endswith('\\'):
                    next_line = True
                flags.append(b.replace('\\',''))
        print flags
        return flags
        
    def get_config_options(self):
        build_section = self._filter_section('%build')
        config_values = []
        config_values.append(self._get_build_flags(build_section,'CFLAGS'))
        config_values.append(self._get_build_flags(build_section,'%configure'))
        return config_values
