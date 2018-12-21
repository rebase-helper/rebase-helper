from rebasehelper.output_tool import BaseOutputTool
from rebasehelper.results_store import results_store
import json


class JSONOutputTool(BaseOutputTool):
    """ JSON output tool """

    EXTENSION = "json"

    @classmethod
    def print_summary(cls, path, results):
        """
        Print JSON summary

        :param path: to the report file
        :param results: dictionary containing info about rebase
        """
        with open(path, 'w') as outputfile:
            json.dump(results.get_all(), outputfile, indent=4, sort_keys=True)

    @classmethod
    def run(cls, logs, app):  # pylint: disable=unused-argument
        """
        Function is used for storing output dictionary into JSON structure
        JSON output is stored into report.json
        """
        path = cls.get_report_path(app)

        cls.print_summary(path, results_store)
