import six
import os

from rebasehelper.output_tool import BaseOutputTool
from rebasehelper.exceptions import RebaseHelperError
from rebasehelper.logger import LoggerHelper, logger, logger_report
from rebasehelper.results_store import results_store


class TextOutputTool(BaseOutputTool):

    """ Text output tool. """

    NAME = "text"
    EXTENSION = 'txt'
    DEFAULT = True

    @classmethod
    def match(cls, cmd=None):
        """
        Checks if the given string matches the output tool

        :param cmd: output tool name
        :return: True if the name matches
        """
        if cmd == cls.NAME:
            return True
        else:
            return False

    @classmethod
    def get_name(cls):
        return cls.NAME

    @classmethod
    def get_extension(cls):
        """
        Get extension of the output_tool

        :return: output_tool extension
        """
        return cls.EXTENSION

    @classmethod
    def print_success_message(cls):
        """Print result message"""
        results = cls.results_store.get_result_message()
        if 'success' in results:
            logger_report.info(results['success'])
        else:
            logger_report.info(results['fail'])

    @classmethod
    def print_changes_patch(cls):
        """Print info about the location of changes.patch"""
        patch = cls.results_store.get_changes_patch()
        if patch is not None:
            logger_report.info('\nPatch with differences between old and new version source files:')
            logger_report.info(patch['changes_patch'])

    @classmethod
    def print_message_and_separator(cls, message="", separator='='):
        logger_report.info(message)
        logger_report.info(separator * len(message))

    @classmethod
    def print_patches(cls, patches, summary):
        if not patches:
            logger_report.info("Patches were neither modified nor deleted.")
            return
        logger_report.info(summary)
        max_name = 0
        for value in six.itervalues(patches):
            if value:
                new_max = max([len(os.path.basename(x)) for x in value])
                if new_max > max_name:
                    max_name = new_max
        max_key = max([len(x) for x in six.iterkeys(patches)])
        for key, value in six.iteritems(patches):
            if value:
                for patch in value:
                    logger_report.info('Patch %s [%s]', os.path.basename(patch).ljust(max_name), key.ljust(max_key))

    @classmethod
    def print_rpms(cls, rpms, version):
        pkgs = ['srpm', 'rpm']
        if not rpms.get('rpm', None):
            return
        message = '\n{0} (S)RPM packages:'.format(version)
        cls.print_message_and_separator(message=message, separator='-')
        for type_rpm in pkgs:
            srpm = rpms.get(type_rpm, None)
            if not srpm:
                continue
            message = "%s package(s): are in directory %s :"
            if isinstance(srpm, str):
                logger_report.info(message, type_rpm.upper(), os.path.dirname(srpm))
                logger_report.info("- %s", os.path.basename(srpm))
            else:
                logger_report.info(message, type_rpm.upper(), os.path.dirname(srpm[0]))
                for pkg in srpm:
                    logger_report.info("- %s", os.path.basename(pkg))

    @classmethod
    def print_build_logs(cls, rpms, version):
        """Function is used for printing rpm build logs"""
        if rpms.get('logs', None) is None:
            return
        logger_report.info('Available %s logs:', version)
        for logs in rpms.get('logs', None):
            logger_report.info('- %s', logs)

    @classmethod
    def print_summary(cls, path, results):
        """Function is used for printing summary information"""
        if results.get_summary_info():
            for key, value in six.iteritems(results.get_summary_info()):
                logger.info("%s %s\n", key, value)

        try:
            LoggerHelper.add_file_handler(logger_report, path)
        except (OSError, IOError):
            raise RebaseHelperError("Can not create results file '%s'" % path)

        cls.results_store = results

        cls.print_success_message()
        type_pkgs = ['old', 'new']
        if results.get_patches():
            cls.print_changes_patch()
            cls.print_patches(results.get_patches(), '\nSummary information about patches:')
        for pkg in type_pkgs:
            type_pkg = results.get_build(pkg)
            if type_pkg:
                cls.print_rpms(type_pkg, pkg.capitalize())
                cls.print_build_logs(type_pkg, pkg.capitalize())

        cls.print_pkgdiff_tool(results.get_checkers())

    @classmethod
    def print_pkgdiff_tool(cls, checkers_results):
        """Function prints a summary information about pkgcomparetool"""
        if checkers_results:
            for check, data in six.iteritems(checkers_results):
                logger_report.info("=== Checker %s results ===", check)
                if data:
                    for checker, output in six.iteritems(data):
                        if output is None:
                            logger_report.info("Log is available here: %s\n", checker)
                        else:
                            if isinstance(output, list):
                                logger_report.info("%s See for more details %s", ','.join(output), checker)
                            else:
                                logger_report.info("%s See for more details %s", output, checker)

    @classmethod
    def run(cls, log, app):
        path = cls.get_report_path(app)
        cls.print_summary(path, results_store)
