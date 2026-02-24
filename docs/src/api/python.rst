.. _python api:

Python
------

This is the Python package level documentation of the SKA Data Lifecycle Management system. Using this package requires it to be installed inside a python environment. The ska_dlm is using the poetry package manager and thus installation is pretty straight foward:
.. This is duplication of docs/src/guides/installation/python_install.rst. Refactor.

.. code:: bash

   $ cd ska_data_lifecycle
   $ poetry install
   $ poetry shell

Then the package can be imported into python:

.. code:: python

   >>> import ska_dlm
   >>> print(ska_dlm.__doc__)

See :ref:`our Python guide <local-development-python-script>` for a full example.

.. autosummary::
   :caption: Package API:
   :toctree: _autosummary
   :recursive:

   ska_dlm
