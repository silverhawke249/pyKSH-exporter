pyKSH-exporter
==============

A library and app for converting KSH files into VOX format and export supporting assets.


Requirements
------------

* Python == 3.10
* DearPyGui == 2.0.0
* Tcl/Tk >= 8.6
* construct >= 2.10
* pydub >= 0.25.1
* PIL == 11.0.0

A dependency of pydub, audioop, was deprecated in Python 3.11 and removed from the standard library in Python 3.13. As such, this exporter does not run out of the box in Python 3.13.

If documentation is needed:

* sphinx >= 7.2.5
* sphinx-autoapi >= 2.1.1
* sphinx-rtd-theme >= 1.3.0

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
