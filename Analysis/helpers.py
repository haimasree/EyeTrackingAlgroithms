import itertools
from typing import Callable

import pandas as pd


def apply_on_column_pairs(data: pd.DataFrame, func: Callable, is_symmetric: bool = True) -> pd.DataFrame:
    """
    Calculates the provided function on data taken from all pairs of columns in the given DataFrame.
    If `is_symmetric` is True, only calculate the measure once for each (unordered-)pair of columns,
    e.g, (A, B) and (B, A) will be the same. If False, calculate the measure for all ordered-pairs of columns.

    :param data: The DataFrame to calculate the function on its columns.
    :param func: The function to calculate the measure between two columns. Should take two arguments as input.
    :param is_symmetric: Determines whether to calculate the measure for ordered or unordered pairs of columns.
    :return: A DataFrame with the same index as the input data, and columns as the pairs of columns of the input data.
    """
    if is_symmetric:
        column_pairs = list(itertools.combinations(data.columns, 2))
    else:
        column_pairs = list(itertools.product(data.columns, repeat=2))
        column_pairs = [pair for pair in column_pairs if pair[0] != pair[1]]
    res = {}
    for idx in data.index:
        res[idx] = {}
        for pair in column_pairs:
            vals1, vals2 = data.loc[idx, pair[0]], data.loc[idx, pair[1]]
            if len(vals1) == 0 or pd.isnull(vals1).all():
                res[idx][pair] = None
            elif len(vals2) == 0 or pd.isnull(vals2).all():
                res[idx][pair] = None
            else:
                res[idx][pair] = func(vals1, vals2)
    res = pd.DataFrame.from_dict(res, orient="index")
    res.index.names = data.index.names
    return res
