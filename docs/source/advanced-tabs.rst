Advanced tabs
=============

During typical usage, these tabs are generally not used. However, these tabs are made available for ease of use, if the
user would like to tweak their charts further.


Effects
-------

This tab allows the user to change the effects defined in the chart. While adding and deleting effects is possible, it
is not recommended, since this does not update the note objects in the charts.

.. important::
    Updating an effect definition will reset the autotab parameter values for that effect.

..
    TODO: Explain the parameters for each effect


Filter mapping
--------------

This tab allows the user to change which effect definition is used for each custom filter. This is due to how the VOX
format works -- every effect applied to a laser as a custom filter requires an effect definition.


Autotab params
--------------

This tab allows the user to tweak an additional layer over the custom filter's effect. The VOX format allows the filter
to change a single parameter. Which parameter is changed, and the range of said parameter, can be changed in this tab.
