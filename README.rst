PythonLinter
============

SublimeText 3 python lint plugin (pyflakes + pep8)


Installation
------------

Clone this repo in your sublime text ``Packages`` folder.


Commands
--------

* ``PythonLinter: Check code``
* ``PythonLinter: Auto PEP8``


Configuration
-------------

Override these settings using ``Package Settings > PythonLinter > Settings - User``

.. code-block:: json

  {
    "active": true,
    "pep8": true,
    "pyflakes": true,
    "error_format": "{code} : {text}",
    "description_format": "L{line}:C{column} {text}",
    "underline_errors": true,
    "max_line_length": 79,
    "show_error_description": true,
    "show_error_offset_cursor": true,
    "ignore": []
  }
