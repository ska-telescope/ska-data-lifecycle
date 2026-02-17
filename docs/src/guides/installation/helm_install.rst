Helm Install
=============

**WIP**

For help on installing ska-dlm *client*, please refer to the `dlm-client documentation <https://developer.skatelescope.org/projects/ska-dlm-client/en/latest/>`_.

To install the DLM server services on a Kubernetes cluster, e.g., the DP cluster, start by cloning the repository (if not already present):

.. code-block:: bash

    git clone --recurse-submodules https://gitlab.com/ska-telescope/ska-data-lifecycle.git

Retrieve the available release tags and check out the desired release:

.. code-block:: bash

    cd ska-data-lifecycle
    git fetch --tags
    git tag --list
    git checkout <release-tag>

Configure the ``values.yaml`` file to match your environment and deployment requirements.

.. note::

   A detailed guide is coming soon! For now, please see the
   `Charts README <https://gitlab.com/ska-telescope/ska-data-lifecycle/-/tree/main/charts/ska-dlm#ska-data-lifecycle-management-chart.html>`_
   (note that it is not fully up-to-date).

Then install/upgrade the chart:

.. code-block:: bash

    helm upgrade --install ska-dlm charts/ska-dlm

To uninstall:

.. code-block:: bash

    helm uninstall ska-dlm


