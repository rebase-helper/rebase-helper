from rebasehelper.output_tool import BaseOutputTool
from rebasehelper.results_store import results_store
import json


class JSONOutputTool(BaseOutputTool):
    """ JSON output tool """

    NAME = "json"
    EXTENSION = "json"

    @classmethod
    def match(cls, cmd=None):
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
    def print_summary(cls, path, results_store):
        """
        Print JSON summary

        :param path: to the report file
        :param results_store: dictionary containing info about rebase
        """
        with open(path, 'w') as outputfile:
            json.dump(results_store.get_all(), outputfile, indent=4, sort_keys=True)

    @classmethod
    def run(cls, logs, app):
        """
        Function is used for storing output dictionary into JSON structure
        JSON output is stored into report.json
        """
        path = cls.get_report_path(app)

        cls.print_summary(path, results_store)
