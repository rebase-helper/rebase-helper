try:
    from functools import reduce
except ImportError:
    pass # we're on Python 2 => ok
import re

import os
from rebasehelper import settings

class Specfile(object):
    def __init__(self, file):
        f = open(file,"r")
        self.specfile = ''.join(f.readlines())
        f.close()
        self.sections = self.split_sections()

    def split_sections(self):
        headers_re = [re.compile('^' + x, re.M) for x in settings.SPECFILE_SECTIONS]
        section_starts = []
        for header in headers_re:
            for match in header.findall(self.specfile):
                print match, type(match)
                section_starts.append(match)

        section_starts.sort()
        print section_starts
        # this is mainly for tests - if the header is the only section
        header_end = section_starts[0] if section_starts else len(self.specfile)
        sections = [('%header', self.specfile[:header_end])]
        for i in range(len(section_starts)):
            print i
            if len(section_starts) > i + 1:
                curr_section = self.specfile[section_starts[i]:section_starts[i+1]]
            else:
                curr_section = self.specfile[section_starts[i]:]
            for header in headers_re:
                if header.match(curr_section):
                    sections.append((header.pattern[1:], curr_section))

        return sections

    def __contains__(self, what):
        return reduce(lambda x, y: x or (what in y[1]), self.sections, False)

    def __str__(self):
        # in tests (maybe in reality, too), we may have an empty header, which will result in
        # putting unnecessary newlines on top => leave out empty sections from joining
        return '\n\n'.join([section for section in list(zip(*self.sections))[1] if section])
