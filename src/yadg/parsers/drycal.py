import logging
import json
from striprtf.striprtf import rtf_to_text

from yadg.parsers.basiccsv import process_row, tols_from
import yadg.dgutils

version = "1.0.dev1"


def drycal_rtf(
    fn: str,
    date: float,
    encoding: str = "utf-8",
    atol: float = 0.0,
    rtol: float = 0.0,
    sigma: dict = {},
    timezone: str = "localtime",
    calib: dict = {},
) -> tuple[list, dict, None]:
    """
    RTF version of the drycal parser.

    This is intended to parse legacy drycal DOC files, which have been converted to RTF
    using other means.

    Parameters
    ----------
    fn
        Filename to parse.

    date
        A unix timestamp float corresponding to the day (or other offset) to be added to
        each line in the measurement table.

    encoding
        Encoding to use for parsing ``fn``.

    atol
        Absolute error accross all fields in the data. By default 0.0.

    rtol
        Relative error accross all fields in the data. By default 0.0.

    sigma
        A dictionary specifying per-column ``atol`` and ``rtol``.

    calib
        A calibration spec.

    Returns
    -------
    (timesteps, metadata, None): tuple[list, dict, None]
        A standard data - metadata - common data output tuple.
    """
    with open(fn, "r", encoding=encoding) as infile:
        rtf = infile.read()
    lines = rtf_to_text(rtf).split("\n")
    for li in range(len(lines)):
        if lines[li].startswith("Sample"):
            si = li
        elif lines[li].startswith("1|"):
            di = li
            break
    # Metadata processing for rtf files is in columns, not rows.
    ml = []
    metadata = dict()
    for line in lines[:si]:
        if line.strip() != "":
            items = [i.strip() for i in line.split("|")]
            if len(items) > 1:
                ml.append(items)
    assert len(ml) == 2 and len(ml[0]) == len(ml[1])
    for i in range(len(ml[0])):
        if ml[0][i] != "":
            metadata[ml[0][i]] = ml[1][i]

    # Process data table
    dl = []
    dl.append(" ".join(lines[si:di]))
    for line in lines[di:]:
        if line.strip() != "":
            dl.append(line)
    headers, units, data = drycal_table(dl, sep="|")
    datecolumns, datefunc = yadg.dgutils.infer_timestamp_from(
        spec={"time": {"index": 4, "format": "%I:%M:%S %p"}}, timezone=timezone
    )

    tols = tols_from(headers[1:], sigma, atol, rtol)

    # Correct each ts by provided date
    timesteps = []
    for row in data:
        ts = process_row(
            headers[1:], row[1:], units, tols, datefunc, datecolumns, calib=calib
        )
        ts["uts"] += date
        ts["fn"] = fn
        timesteps.append(ts)

    return timesteps, metadata, None


def drycal_sep(
    fn: str,
    date: float,
    sep: str,
    encoding: str = "utf-8",
    atol: float = 0.0,
    rtol: float = 0.0,
    sigma: dict = {},
    timezone: str = "localtime",
    calib: dict = {},
) -> tuple[list, dict, None]:
    """
    Generic drycal parser, using ``sep`` as separator string.

    This is intended to parse other export formats from DryCal, such as txt and csv files.

    Parameters
    ----------
    fn
        Filename to parse.

    date
        A unix timestamp float corresponding to the day (or other offset) to be added to
        each line in the measurement table.

    sep
        The separator character used to split lines in ``fn``.

    encoding
        Encoding to use for parsing ``fn``.

    atol
        Absolute error accross all fields in the data. By default 0.0.

    rtol
        Relative error accross all fields in the data. By default 0.0.

    sigma
        A dictionary specifying per-column ``atol`` and ``rtol``.

    calib
        A calibration spec.

    Returns
    -------
    (timesteps, metadata, None): tuple[list, dict, None]
        A standard data - metadata - common data output tuple.
    """
    with open(fn, "r", encoding=encoding) as infile:
        lines = infile.readlines()
    for li in range(len(lines)):
        if lines[li].startswith("Sample"):
            si = li
        elif lines[li].startswith(f"1{sep}"):
            di = li
            break
    # Metadata processing for csv files is standard.
    metadata = dict()
    for line in lines[:si]:
        if line.strip() != "":
            items = [i.strip() for i in line.split(sep)]
            if len(items) == 2:
                metadata[items[0]] = items[1]

    # Process data table
    dl = list()
    dl.append(" ".join(lines[si:di]))
    for line in lines[di:]:
        if line.strip() != "":
            dl.append(line)
    headers, units, data = drycal_table(dl, sep=sep)
    datecolumns, datefunc = yadg.dgutils.infer_timestamp_from(
        spec={"time": {"index": 4, "format": "%H:%M:%S"}}, timezone=timezone
    )

    # fill in
    tols = tols_from(headers[1:], sigma, atol, rtol)

    # Correct each ts by provided date
    timesteps = list()
    for row in data:
        ts = process_row(
            headers[1:], row[1:], units, tols, datefunc, datecolumns, calib=calib
        )
        ts["uts"] += date
        ts["fn"] = str(fn)
        timesteps.append(ts)

    return timesteps, metadata, None


def drycal_table(lines: list, sep: str = ",") -> tuple[list, dict, list]:
    """
    DryCal table-processing function.

    Given a table with headers and units in the first line, and data in the following
    lines, this function returns the headers, units, and data extracted from the table.
    The returned values are always of :class:`(str)` type, any post-processing is done
    in the calling routine.

    Parameters
    ----------
    lines
        A list containing the lines to be parsed

    sep
        The separator string used to split each line into individual items

    Returns
    -------
    (headers, units, data): tuple[list, dict, list]
        A tuple of a list of the stripped headers, dictionary of header-unit key-value
        pairs, and a list of lists containing the rows of the table.
    """
    items = [i.strip() for i in lines[0].split(sep)]
    headers = []
    units = {}
    data = []
    for item in items:
        for rs in [". ", " "]:
            parts = item.split(rs)
            if len(parts) == 2:
                break
        headers.append(parts[0])
        if len(parts) == 2:
            units[parts[0]] = parts[1]
        else:
            units[parts[0]] = "-"
    if items[-1] == "":
        trim = True
        headers = headers[:-1]
    for line in lines[1:]:
        cols = line.split(sep)
        assert len(cols) == len(items)
        if trim:
            data.append(cols[:-1])
        else:
            data.append(cols)
    return headers, units, data


def process(
    fn: str,
    encoding: str = "utf-8",
    timezone: str = "localtime",
    filetype: str = None,
    atol: float = 0.0,
    rtol: float = 0.0,
    sigma: dict = {},
    convert: dict = None,
    calfile: str = None,
    date: str = None,
    **kwargs,
) -> tuple[list, dict, dict]:
    """
    DryCal log file processor.

    This parser is currently able to process DryCal formatted rtf, txt, and csv files.
    It reuses a lot of its functionality from the :mod:`yadg.parsers.basiccsv` module.

    Parameters
    ----------
    fn
        File to process

    encoding
        Encoding of ``fn``, by default "utf-8".

    timezone
        A string description of the timezone. Default is "localtime".

    filetype
        Whether a rtf, csv, or txt file is to be expected. When `None`, the suffix of
        the file is used to determine the file type.

    sep
        Separator to use. Default is "," for csv.

    atol
        The default absolute uncertainty accross all float values in csv columns.
        By default set to 0.0.

    rtol
        The default relative uncertainty accross all float values in csv columns.
        By default set to 0.0.

    sigma
        Column-specific ``atol`` and ``rtol`` values can be supplied here.

    units
        Column-specific unit specification. If present, even if empty, 2nd line is
        treated as data. If omitted, 2nd line is treated as units.

    timestamp
        Specification for timestamping. Allowed keys are ``"date"``, ``"time"``,
        ``"timestamp"``, ``"uts"``. The entries can be ``"index"`` :class:`(list[int])`,
        containing the column indices, and ``"format"`` :class:`(str)` with the format
        string to be used to parse the date. See :func:`yadg.dgutils.dateutils.infer_timestamp_from`
        for more info.

    convert
        Specification for column conversion. The `key` of each entry will form a new
        datapoint in the ``"derived"`` :class:`(dict)` of a timestep. The elements within
        each entry must either be one of the ``"header"`` fields, or ``"unit"`` :class:`(str)`
        specification. See :func:`yadg.parsers.basiccsv.process_row` for more info.

    calfile
        ``convert``-like functionality specified in a json file.

    Returns
    -------
    (data, metadata, common) : tuple[list, None, None]
        Tuple containing the timesteps, metadata, and common data.

    """
    if calfile is not None:
        with open(calfile, "r") as infile:
            calib = json.load(infile)
    else:
        calib = {}
    if convert is not None:
        calib.update(convert)

    if date is None:
        date = fn
    date = yadg.dgutils.date_from_str(date)
    assert date is not None, "Log starting date must be specified."

    metadata = {}
    kwargs = {
        "atol": atol,
        "rtol": rtol,
        "sigma": sigma,
        "calib": calib,
        "encoding": encoding,
        "timezone": timezone,
    }

    if filetype == "rtf" or (filetype is None and fn.endswith("rtf")):
        ts, meta, comm = drycal_rtf(fn, date, **kwargs)
    elif filetype == "csv" or (filetype is None and fn.endswith("csv")):
        ts, meta, comm = drycal_sep(fn, date, ",", **kwargs)
    elif filetype == "txt" or (filetype is None and fn.endswith("txt")):
        ts, meta, comm = drycal_sep(fn, date, "\t", **kwargs)

    metadata.update(meta)

    return ts, metadata, comm