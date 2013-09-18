# -*- coding: utf-8 -*-

class Application(object):
    result_file = ""
    temp_dir = ""

    def __init__(self, conf):
        """ conf is CLI object """
        self.conf = conf

    def build_command(self,binary):
        """
        create command from CLI options
        """
        command = [binary]
        command.extend(self.command_eval)
        if self.conf.devel:
            command.append("--devel")
        if self.conf.verbose:
            command.append("--verbose")
        return command

    def run(self):
        cmd = self.build_command()
        print "running command:\n%s" % ' '.join(cmd)
        """ This section can be used for testing """
        """if self.conf.devel:
            old_arch = archive.Archive("emacs-24.2.tar.xz")
            old_arch.extract()
            tar_arch = archive.Archive(self.conf.source)
            tar_arch.extract()
            zip_arch = archive.Archive("taglist_46.zip")
            zip_arch.extract()
        """



if __name__ == '__main__':
    a = Application(None)
    a.run()
