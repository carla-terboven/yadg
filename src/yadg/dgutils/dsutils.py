import numpy as np
import xarray as xr
from xarray import Dataset
from typing import Any


def append_dicts(
    vals: dict[str, Any],
    devs: dict[str, Any],
    data: dict[str, list[Any]],
    meta: dict[str, list[Any]],
    fn: str = None,
    li: int = 0,
) -> None:
    if "_fn" in meta and fn is not None:
        meta["_fn"].append(str(fn))
    for k, v in vals.items():
        if k not in data:
            data[k] = [None if isinstance(v, str) else np.nan] * li
        data[k].append(v)
    for k, v in devs.items():
        if k not in meta:
            meta[k] = [np.nan] * li
        meta[k].append(v)

    for k in set(data) - set(vals):
        data[k].append(np.nan)
    for k in set(meta) - set(devs):
        if k != "_fn":
            meta[k].append(np.nan)


def dicts_to_dataset(
    data: dict[str, list[Any]],
    meta: dict[str, list[Any]],
    units: dict[str, str] = dict(),
    fulldate: bool = True,
) -> Dataset:
    darrs = {}
    for k, v in data.items():
        attrs = {}
        u = units.get(k, None)
        if u is not None:
            attrs["units"] = u
        if k == "uts":
            continue
        darrs[k] = xr.DataArray(data=v, dims=["uts"], attrs=attrs)
        if k in meta and darrs[k].dtype.kind in {"i", "u", "f", "c", "m", "M"}:
            err = f"{k}_std_err"
            darrs[k].attrs["ancillary_variables"] = err
            attrs["standard_name"] = f"{k} standard error"
            darrs[err] = xr.DataArray(data=meta[k], dims=["uts"], attrs=attrs)
    if "uts" in data:
        coords = dict(uts=data.pop("uts"))
    else:
        coords = dict()
    if fulldate:
        attrs = dict()
    else:
        attrs = dict(fulldate=False)
    return xr.Dataset(data_vars=darrs, coords=coords, attrs=attrs)


def merge_dicttrees(vals: dict, fvals: dict, mode: str) -> dict:
    """
    A helper function that merges two ``DataTree.to_dict()`` objects by concatenating
    the new values in ``fvals`` to the existing ones in ``vals``.

    """
    if vals is None:
        return fvals
    for k in fvals.keys():
        try:
            vals[k] = xr.concat([vals[k], fvals[k]], dim="uts", combine_attrs=mode)
        except xr.MergeError:
            raise RuntimeError(
                "Merging metadata from multiple files has failed, as some of the "
                "values differ between files. This might be caused by trying to "
                "parse data obtained using different techniques/protocols in a "
                "single step. If you are certain this is what you want, try using "
                "yadg with the '--ignore-merge-errors' option."
            )
    return vals