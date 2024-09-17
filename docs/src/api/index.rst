SKA_DLM Interfaces
==================
This is the Python package level documentation of the SKA Data Lifecycle Management system. Using this package requires it to be installed inside a python environment. The ska_dlm is using the poetry package manager and thus installation is pretty straight foward:

.. code:: bash

   $ cd ska_data_lifecycle
   $ poetry install
   $ poetry shell

Then the package can be imported into python:

.. code:: python

   >>> import ska_dlm
   >>> print(ska_dlm.__doc__)

.. toctree::
   :maxdepth: 1
   :caption: APIs:

   cli
   rest

.. _api:

- Python API (auto generated):

.. autosummary::
   :caption: Package API:
   :toctree: _autosummary
   :recursive:

   ska_dlm
