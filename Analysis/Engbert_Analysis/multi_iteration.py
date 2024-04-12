import time
import copy
import warnings
from typing import Callable

import numpy as np
import pandas as pd
import plotly.io as pio

import Config.constants as cnst
from GazeDetectors.BaseDetector import BaseDetector
from GazeDetectors.EngbertDetector import EngbertDetector
from DataSetLoaders.DataSetFactory import DataSetFactory

import Analysis.figures as figs

pio.renderers.default = "browser"

DATASET_NAME = "Lund2013"
LAMBDA_STR = "λ"
ITERATION_STR = "Iteration"
NUM_ITERATIONS = 5


# %%
def detect_multiple_times(data: pd.DataFrame, detector: BaseDetector, num_iterations: int):
    data = data.copy()  # copy the data to avoid modifying the original data
    results = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for i in range(num_iterations):
            iter_results = {}
            for tr in data[cnst.TRIAL].unique():
                trial_data = data[data[cnst.TRIAL] == tr]
                res = detector.detect(
                    trial_data[cnst.T].values,
                    trial_data[cnst.X].values,
                    trial_data[cnst.Y].values
                )
                iter_results[tr] = copy.deepcopy(res)  # deep copy to avoid overwriting the res object

                # nullify detected saccades
                detected_event_labels = res[cnst.GAZE][cnst.EVENT]
                saccade_idxs = trial_data.index[detected_event_labels == cnst.EVENT_LABELS.SACCADE]
                data.loc[saccade_idxs, cnst.X] = np.nan
                data.loc[saccade_idxs, cnst.Y] = np.nan

            results[i+1] = pd.Series(iter_results, name=i+1)
    return pd.DataFrame(results)


# TODO: extract only events from the multi-detect DF
# TODO: apply "group and agg" on the extracted-events DF

# %%
engbert = EngbertDetector()
dataset = DataSetFactory.load(DATASET_NAME)
multi_detect = detect_multiple_times(dataset, engbert, NUM_ITERATIONS)
