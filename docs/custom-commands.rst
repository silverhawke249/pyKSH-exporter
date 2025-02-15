Custom chart commands
=====================

The following chart comments are treated as commands:

* ``curveBeginL``, ``curveBeginR``, ``curveBeginLR``
* ``curveBeginSpL``, ``curveBeginSpR``
* ``curveEndL``, ``curveEndR``, ``curveEndLR``
* ``lightFXL``, ``lightFXR``, ``lightFXLR``
* ``applyFilter``
* ``hideBars``, ``addBars``
* ``scriptBegin``, ``scriptEnd``

Multiple commands may be issued at the same time point, separated by a semicolon (``;``) -- e.g. ``curveBeginL=4;curveEndR``.


Curves
------

Curve commands must be placed on a volume track point. Failure to adhere to this will result in an improper conversion.

For the ``curveBegin`` commands, it must be followed by ``=`` and a number ``2``, ``4``, or ``5``:

* ``curveBeginL=4`` indicates that the left volume track will have an ease-out curve.
* ``curveBeginLR=2,5`` indicates that the left volume track will have a linear "curve", while the right volume track will have an ease-in curve.
* ``curveBeginLR=4`` indicates that both volume tracks will have an ease-out curve.

For the ``curveBeginSp`` commands, it must be followed by ``=`` and three numbers, separated by commas.

* The first number indicates the curve type, as described above.
* The second number indicates the start point of the curve as a decimal number, between ``0.0`` and ``1.0``.
* The third number indicates the end point of the curve as a decimal number, between ``0.0`` and ``1.0``.

To illustrate the purpose of this command, suppose we are converting a chart with this segment:

.. image:: https://silverhawke.s-ul.eu/tMOxmR43
    :alt: Chart example

We have a single continuous curve, but it changes colors mid-way. Applying ``curveBeginL=4`` and ``curveBeginR=4`` to these will not produce the intended effect!
However, we can still do it using ``curveBeginSp`` -- annotate the first half of the curve as ``curveBeginSpL=4,0,0.5`` and the second half as ``curveBeginSpR=4,0.5,1``... (without forgetting about ``curveEnd`` commands)

.. image:: https://silverhawke.s-ul.eu/MwNl482C
    :alt: Curve annotation

And this will produce the intended effect.

The curves are calculated using a sine curve. Currently, no other curves are implemented.

For the ``curveEnd`` commands, nothing else is needed. Simply write ``curveEndL``/``curveEndR``/``curveEndLR`` as appropriate.

A curved segment may be closed with either a ``curveEnd`` command or more ``curveBegin`` commands.


FX chip sound effect
--------------------

FX chip sound sample can be autodetected by using the appropriate file name (``1.wav``, etc.) or by specifying it using the ``lightFX`` command -- e.g. ``lightFXLR=7``.


Filter overriding
-----------------

In the VOX format, effects on lasers are implemented as an additional layer above FX effects.
As a result, effects on lasers can be overlaid on top of regular laser effects -- e.g. putting a Re16 effect on a laser while the laser applies a LPF effect on the song.
The only effect that cannot be overlaid on is the ``PEAK`` effect.

To use this command, simply write ``applyFilter=[filter]`` as a chart comment where the active filter changes to the custom filter activates.
Valid ``filter`` values are: ``lpf``, ``hpf``, ``bitc``, ``1``, ``2``, ``3``, ``4``, ``5``.


Bar lines
---------

By writing ``hideBars=on``, bar lines from this point onwards will be hidden. If this command is issued on the start of a measure, that measure's bar line **WILL** be hidden.
Write ``hideBars=off`` to make bar lines appear again. This is subject to the same quirk as ``hideBars=on``.

While ``hideBars`` is active, the command ``addBars`` can be issued to manually draw a bar line at that point.


Scripts
-------

This command is intended to make writing charts with scripted sections easier. Write ``scriptBegin=`` followed by at least two comma separated numbers.
The first number is the track specifier, which indicates which tracks will have scripts applied to. The following numbers indicates the script ID that will be applied to the specified tracks.

The way the track specifier encodes which track gets scripts applied to is via binary flags::

      Flag for VOL-L
      | Flag for BT-A
      | | Flag for BT-C
      | | | Flag for FX-R
      | | | |
    0b10100010 = 0xA2 = 162
       | | | |
       | | | Flag for VOL-R
       | | Flag for BT-D
       | Flag for BT-B
       Flag for FX-L

This number can be provided in hexadecimal (with the ``0x`` prefix), binary (with the ``0b`` prefix), or decimal.

In the generated VOX file, sections to define the script will be provided for each script ID specified in the commands.
