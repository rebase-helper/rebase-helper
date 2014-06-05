try:
    from functools import reduce
except ImportError:
    pass # we're on Python 2 => ok
import os
import rpm
import shutil
from rebasehelper.utils import ProcessHelper
from rebasehelper.logger import logger
from rebasehelper import settings
from rebasehelper.utils import get_content_file,  get_rebase_name, write_to_file


class Specfile(object):
    """
    Class who manipulates with SPEC file
    """
    
    values = []
    def __init__(self, specfile):
        self.specfile = specfile
        self.rebased_spec = get_rebase_name(specfile)
        if os.path.exists(self.rebased_spec):
            os.unlink(self.rebased_spec)
        shutil.copy(self.specfile, self.rebased_spec)
        self.spc = rpm.spec(self.rebased_spec)

    def get_patch_option(self, line):
        spl = line.strip().split()
        if len(spl) == 1:
            return spl[0], " "
        elif len(spl) == 2:
            return spl[0], spl[1]
        else:
            return spl[0], spl[1]

    def get_rebased_spec(self):
        """
        Function returns rebase.spec file
        """
        return self.rebased_spec

    def get_patch_number(self, line):
        fields = line.strip().split()
        patch_num = fields[0].replace('Patch','')[:-1]
        return patch_num

    def get_content_rebase(self):
        """
        Function reads a content rebase.spec file
        """
        lines = get_content_file(self.get_rebased_spec(), "r", method=True)
        return lines

    def get_patch_flags(self):
        """
        Function gets all patches
        """
        patch_flags = {}
        lines = self.get_content_rebase()
        lines = [x for x in lines if x.startswith(settings.PATCH_PREFIX)]
        for line in lines:
            num, option = self.get_patch_option(line)
            num = num.replace(settings.PATCH_PREFIX,'')
            patch_flags[int(num)] = option
        return patch_flags
        
    def get_patches(self):
        """
        Function returns a list of patches from a spec file
        """
        patches = {}
        patch_flags = self.get_patch_flags()
        cwd = os.getcwd()
        sources = [ x for x in self.spc.sources if x[2] == 2]
        for source in sources:
            filename, num, patch_type = source
            full_patch_name = os.path.join(cwd, filename)
            if not os.path.exists(full_patch_name):
                logger.error('Patch {0} does not exist'.format(filename))
                continue
            if num in patch_flags:
                patches[num] = [full_patch_name, patch_flags[num]]
        return patches

    def get_sources(self):
        """
        Function returns a all sources
        """
        sources = [ x for x in self.spc.sources if x[2] == 0 or x[2] == 1 ]
        return sources

    def get_all_sources(self):
        """
        Function returns all sources mentioned in specfile
        """
        cwd = os.getcwd()
        sources = self.get_sources()
        for index, src in enumerate(sources):
            if int(src[1]) == 0:
                sources[index] = os.path.join(cwd, src[0].split('/')[-1])
            else:
                sources[index] = os.path.join(cwd, src[0])
        return sources

    def get_old_sources(self):
        """
        Function returns a old sources from specfile
        """
        sources = self.get_sources()
        old_source_name = [ x for x in sources if x[1] == 0 ]
        source_name = old_source_name[0][0].split('/')[-1]
        if not os.path.exists(source_name):
            ProcessHelper.run_subprocess_cwd('wget {0}'.format(old_source_name), shell=True)
        return source_name

    def write_updated_patches(self, patches):
        """
        Function writes a patches to -rebase.spec file
        """
        lines = self.get_content_rebase()
        for index, line in enumerate(lines):
            # We take care about patches.
            if not line.startswith('Patch'):
                continue
            fields = line.strip().split()
            patch_num = self.get_patch_number(line)
            lines[index] = ' '.join(fields[:-1]) + ' ' + os.path.basename(patches[int(patch_num)][0]) +'\n'

        write_to_file(self.get_rebased_spec(), "w", lines)