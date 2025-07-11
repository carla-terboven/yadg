"""
Handles the reading and processing of volumetric flow meter data exported from the
MesaLabs DryCal software as a txt file.

.. note::

    The date information is missing in the timestamps of the exported files and has to
    be supplied externally.

Usage
`````
Available since ``yadg-4.0``.

.. autopydantic_model:: dgbowl_schemas.yadg.dataschema_6_0.filetype.Drycal_txt

Schema
``````
.. code-block:: yaml

    xarray.DataTree:
      coords:
        uts:            !!float               # Unix timestamp, without date
      data_vars:
        DryCal:         (uts)                 # Standardised flow rate
        DryCal Avg.:    (uts)                 # Running average of the flow rate
        Temp.:          (uts)                 # Measured flow temperature
        Pressure:       (uts)                 # Measured flow pressure

Metadata
````````
The following metadata is extracted:

    - ``product``: Model name of the MesaLabs device.
    - ``serial number``: Serial number of the MesaLabs device.

Uncertainties
`````````````
All uncertainties are derived from the string representation of the floats.

.. codeauthor::
    Peter Kraus

"""

from xarray import DataTree
from yadg.extractors.drycal import common
from pathlib import Path
from yadg.extractors import get_extract_dispatch

extract = get_extract_dispatch()


@extract.register(Path)
def extract_from_path(
    source: Path,
    *,
    encoding: str,
    timezone: str,
    **kwargs: dict,
) -> DataTree:
    vals = common.sep(str(source), "\t", encoding, timezone)
    return DataTree(common.check_timestamps(vals))
