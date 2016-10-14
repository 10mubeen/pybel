Logging Messages
================

General Parser Failure
----------------------

This message is displayed when a problem was caused due to an unforseen error. The line number and original statement
are printed for the user to debug.

Error Codes
-----------

When errors in the statement leave the term or relation as nonsense, these errors are thrown and the statement is
excluded. These are debugged with code :code:`PyBEL1XX`.

.. automodule:: pybel.parser.parse_exceptions
    :members:

Debugging Codes
---------------

There are certain statements that aren't correct, but PyBEL can understand and fix. These will be handled automatically,
and a nice message with :code:`PyBEL0XX` number will be output to debug.

+------+---------------------------+------------------------------------------------------------------------------------+
| Code | Problem                   | Explanation                                                                        |
+------+---------------------------+------------------------------------------------------------------------------------+
| 001  | Legacy molecular activity | This means that an old style activity, like kin(p(HGNC:YFG)) was used.             |
|      |                           |                                                                                    |
|      |                           | PyBEL converts this automatically to activity(HGNC:YFG, ma(KinaseActivity))        |
+------+---------------------------+------------------------------------------------------------------------------------+
| 016  | Legacy pmod()             | Old protein substitutions are converted automatically to the new HGVS style.       |
+------+---------------------------+------------------------------------------------------------------------------------+
| 006  | Legacy sub()              | Attribute sub() in p() has been deprecated in favor of variant() and HGVS style.   |
+------+---------------------------+------------------------------------------------------------------------------------+
| 009  | Legacy sub()              | Old gene substitutions are convert automatically to the new HGVS style.            |
+------+---------------------------+------------------------------------------------------------------------------------+
| 024  | Missing Key               | Tried to UNSET annotation that is not set                                          |
+------+---------------------------+------------------------------------------------------------------------------------+
| 025  | Legacy trunc()            | Attribute trunc() in p() has been deprecated in favor of variant() and HGVS style. |
+------+---------------------------+------------------------------------------------------------------------------------+
