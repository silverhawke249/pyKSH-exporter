pyKSH-exporter
==============

A library and app for converting KSH files into VOX format and export supporting assets.


Requirements
------------

* Python >= 3.10.10
* DearPyGui >= 1.9.0
* Tcl/Tk >= 8.6
* construct >= 2.10
* pydub >= 0.25.1
* PIL >= 9.1.0

If documentation is needed:

* sphinx >= 7.2.5
* sphinx-autoapi >= 2.1.1
* sphinx-rtd-theme >= 1.3.0

Older versions of Python 3.10 is untested, but this certainly does not run on Python 3.9.


Usage
-----

Simply run ``main.pyw``.

Typical usage would only use the first two tabs. Upon loading a KSH file, most of the fields will be automatically populated.
Fill the empty fields, both in the "Song info" tab and the "Chart info" tab.

Available functions:

* **Save VOX** --- Exports the KSH file into a VOX file, containing chart data.
* **Save XML** --- Exports a XML file, containing song and chart metadata.
* **Export 2DX** --- Exports two 2DX files, containing song audio and preview audio.
* **Export jackets** --- Exports three PNG files of the song jacket in different resolutions.


Further reading
---------------

.. toctree::
    :maxdepth: 1

    advanced-tabs
    custom-commands
    version-history


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
