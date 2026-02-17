Python Install
==============


Clone the DLM server repository:

.. code-block:: bash

    git clone --recurse-submodules https://gitlab.com/ska-telescope/ska-data-lifecycle.git


Then install the project dependencies and enter a Poetry shell:

.. code-block:: bash

    cd ska-data-lifecycle
    poetry install
    poetry shell


See the :doc:`/guides/usage/index` for examples on how to interact with the DLM server directly.