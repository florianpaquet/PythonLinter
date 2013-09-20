# -*- coding:utf-8 -*-
import sublime
import sublime_plugin
from collections import namedtuple
from .contrib import pep8
from .contrib.pyflakes.api import check

Error = namedtuple('Error', ['code', 'line', 'offset', 'text'])


# ---- REPORTERS

class Pep8Report(pep8.BaseReport):
    def __init__(self, options):
        super(Pep8Report, self).__init__(options)
        self.error_list = []

    def error(self, line_number, offset, text, check):
        code = super(Pep8Report, self).error(line_number, offset, text, check)
        if code:
            # Extract error description part from "EXXX error description" and capitalize the first word
            raw_text = text.split(' ', 1)[1].strip().capitalize()
            self.error_list.append(Error(code, self.line_offset + line_number, offset, raw_text))


class PyFlakesReporter(object):
    def __init__(self):
        self.error_list = []

    def unexpectedError(self, filename, msg):
        self.error_list.append(Error('ERROR', 0, 0, msg))

    def syntaxError(self, filename, msg, lineno, offset, text):
        self.error_list.append(Error('ERROR', lineno, offset, msg))

    def flake(self, error):
        code = error.flake8_msg.split(' ', 1)[0]
        self.error_list.append(Error(code, error.lineno, error.col, error.message % error.message_args))


# ---- COMMANDS


class PythonLinter(sublime_plugin.EventListener):

    def __init__(self, *args, **kwargs):
        super(PythonLinter, self).__init__(*args, **kwargs)
        self.view = None
        self.settings = None
        self.error_list = []
        self.pep8_error_list = []
        self.pyflakes_error_list = []

    def _on_select(self, index):
        """
        Sets cursor and view at selected error
        """
        if 0 <= index < len(self.error_list):
            error = self.error_list[index]
            point = self.view.text_point(error.line - 1, error.offset)
            self.view.sel().clear()
            self.view.sel().add(point)
            self.view.show_at_center(point)

    def _format_error(self, error):
        """
        Returns formatted error
        """
        assert isinstance(error, Error)
        base_error = '%s : %s' % (error.code, error.text)

        if self.settings.get('multiline_errors', False):
            return [base_error, 'Line %d at character %d' % (error.line, error.offset)]
        else:
            return base_error

    def _merge_errors(self):
        """
        Merges PEP8 and PyFlakes errors to a single list
        """
        self.error_list = []

        ignore_list = self.settings.get('ignore', [])
        error_lists = [self.pyflakes_error_list, self.pep8_error_list]

        for error_list in error_lists:
            for error in error_list:
                if not any(error.code.startswith(ignore) for ignore in ignore_list):
                    self.error_list.append(error)

    def _display_errors(self):
        """
        Displays errors on Sublime Text
        """
        self.view.window().show_quick_panel(
            items=[self._format_error(error) for error in self.error_list],
            on_select=self._on_select
        )

    def _run_pep8(self, filename):
        """
        Runs PEP8 checker on the file
        """
        pep8_checker = pep8.Checker(
            filename=filename,
            select=['E', 'W'],
            max_line_length=self.settings.get('max_line_length', 79),
            reporter=Pep8Report
        )
        pep8_checker.check_all()

        # Store errors and display them
        self.pep8_error_list = pep8_checker.report.error_list

    def _run_pyflakes(self, code, filename):
        """
        Runs PyFlakes checker on the code
        """
        reporter = PyFlakesReporter()
        check(
            codeString=code,
            filename=filename,
            reporter=reporter
        )
        self.pyflakes_error_list = reporter.error_list

    def on_post_save_async(self, view):
        """
        Runs checkers on post save
        """
        self.settings = sublime.load_settings('PythonLinter.sublime-settings')

        if self.settings.get('active', True):
            filename = view.file_name()
            code = view.substr(sublime.Region(0, view.size()))

            if filename is not None and view.match_selector(0, 'source.python'):
                self.view = view
                if self.settings.get('pep8', True):
                    self._run_pep8(filename)
                if self.settings.get('pyflakes', True):
                    self._run_pyflakes(code, filename)
                self._merge_errors()
                self._display_errors()
