# -*- coding:utf-8 -*-
import os
import sys
import sublime
import sublime_plugin
from collections import namedtuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'contrib'))

from .contrib import pep8
from .contrib.autopep8 import fix_code
from .contrib.pyflakes.api import check


Error = namedtuple('Error', ['code', 'line', 'offset', 'text'])


def upper_first(s):
    return s[:1].upper() + s[1:]


# ---- REPORTERS

class Pep8Reporter(pep8.BaseReport):
    def __init__(self, options):
        super(Pep8Reporter, self).__init__(options)
        self.error_list = []

    def error(self, line_number, offset, text, check):
        code = super(Pep8Reporter, self).error(
            line_number, offset, text, check)
        if code:
            # Extract error description part from "EXXX error description"
            # and capitalize the first word
            raw_text = upper_first(text.split(' ', 1)[1].strip())
            self.error_list.append(
                Error(
                    code,
                    self.line_offset + line_number,
                    offset,
                    raw_text
                )
            )


class PyFlakesReporter(object):
    def __init__(self):
        self.error_list = []

    def unexpectedError(self, filename, msg):
        self.error_list.append(Error(None, 0, 0, upper_first(msg)))

    def syntaxError(self, filename, msg, lineno, offset, text):
        self.error_list.append(Error(None, lineno, offset, upper_first(msg)))

    def flake(self, error):
        self.error_list.append(
            Error(
                None,
                error.lineno,
                error.col,
                upper_first(
                    error.message % error.message_args
                )
            )
        )

# ---- COMMANDS


class PythonLintCommand(sublime_plugin.TextCommand):
    """
    Shows PEP8 and PyFlakes errors on the current file
    """
    def __init__(self, *args, **kwargs):
        super(PythonLintCommand, self).__init__(*args, **kwargs)
        self.settings = None
        self.error_list = []
        self.error_format = ''
        self.description_format = ''
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

    def _get_description(self, error, text):
        """
        Returns text offset and formatted description
        """
        located_description = self.description_format.format(
            line=error.line,
            column=error.offset,
            text='{text}'
        )
        text_offset = located_description.find('{text}')
        description = located_description.format(
            text=text.strip()
        )

        return text_offset, description

    def _format_error(self, error):
        """
        Returns formatted error
        """
        assert isinstance(error, Error)

        if error.code is not None:
            base_error = self.error_format.format(
                code=error.code,
                text=error.text
            )
        else:
            base_error = error.text

        if self.settings.get('show_error_description', True):
            text = self.view.substr(
                self.view.line(
                    self.view.text_point(error.line - 1, error.offset)
                )
            )
            text_offset, description = self._get_description(error, text)

            error_block = [
                base_error,
                description
            ]

            # Add cursor if activated
            # Cursor, even if empty, is required to avoid Sublime Text errors
            if self.settings.get('show_error_offset_cursor', True):
                if text.strip() and text_offset != -1:
                    leading_spaces = len(text) - len(text.lstrip())
                    cursor = '^'.rjust(
                        error.offset - leading_spaces + text_offset + 1)
                else:
                    cursor = ''

                error_block.append(cursor)

            return error_block
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
                ignored = any(
                    error.code.startswith(ignore) for ignore in ignore_list)
                if error.code is None or not ignored:
                    self.error_list.append(error)

    def _underline_errors(self):
        """
        Shows an underline on errors
        """
        regions = [
            self.view.line(
                self.view.text_point(error.line - 1, error.offset)
            ) for error in self.error_list]
        flags = sublime.DRAW_NO_FILL | \
            sublime.DRAW_NO_OUTLINE | sublime.DRAW_STIPPLED_UNDERLINE
        self.view.add_regions(
            key='python_linter_errors',
            scope='comment',
            regions=regions,
            flags=flags
        )

    def _display_errors(self):
        """
        Displays errors on Sublime Text
        """
        if self.settings.get('underline_errors', True):
            self._underline_errors()

        self.view.window().show_quick_panel(
            items=[self._format_error(error) for error in self.error_list],
            on_select=self._on_select,
            flags=sublime.MONOSPACE_FONT
        )

    def _run_pep8(self, filename):
        """
        Runs PEP8 checker on the file
        """
        pep8_checker = pep8.Checker(
            filename=filename,
            select=['E', 'W'],
            max_line_length=self.settings.get('max_line_length', 79),
            reporter=Pep8Reporter
        )
        pep8_checker.check_all()

        # Store errors and display them
        self.pep8_error_list = pep8_checker.report.error_list

    def _run_pyflakes(self, code):
        """
        Runs PyFlakes checker on the code
        """
        reporter = PyFlakesReporter()
        check(
            codeString=code,
            filename='',
            reporter=reporter
        )
        self.pyflakes_error_list = reporter.error_list

    def run(self, edit):
        """
        Check code
        """
        self.settings = sublime.load_settings('PythonLinter.sublime-settings')
        filename = self.view.file_name()
        code = self.view.substr(sublime.Region(0, self.view.size()))

        if filename is not None and \
           self.view.match_selector(0, 'source.python'):
            self.error_format = self.settings.get(
                'error_format', '{code} : {text}')
            self.description_format = self.settings.get(
                'description_format', 'L{line}:C{column} {text}')

            if self.settings.get('pep8', True):
                self._run_pep8(filename)
            if self.settings.get('pyflakes', True):
                self._run_pyflakes(code)

            self._merge_errors()
            self._display_errors()


class AutoPep8Command(sublime_plugin.TextCommand):
    def run(self, edit):
        """
        Auto PEP8 the current file
        """
        if self.view.match_selector(0, 'source.python'):
            full_region = sublime.Region(0, self.view.size())
            input_code = self.view.substr(full_region)
            fixed_code = fix_code(input_code)
            self.view.replace(edit, full_region, fixed_code)

# ---- LISTENERS


class PythonFileSaveListener(sublime_plugin.EventListener):

    def __init__(self, *args, **kwargs):
        super(PythonFileSaveListener, self).__init__(*args, **kwargs)
        self.view = None
        self.settings = None
        self.error_list = []
        self.error_format = ''
        self.description_format = ''
        self.pep8_error_list = []
        self.pyflakes_error_list = []

    def on_post_save_async(self, view):
        """
        Runs checkers on post save
        """
        settings = sublime.load_settings('PythonLinter.sublime-settings')

        if settings.get('active', True):
            view.run_command('python_lint')
