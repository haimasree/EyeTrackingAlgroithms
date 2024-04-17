import time
import warnings
from typing import Set, Dict, List, Union

import numpy as np
import pandas as pd

import Config.constants as cnst
import Config.experiment_config as cnfg
import Analysis.helpers as hlp
from Analysis.Analyzers.BaseAnalyzer import BaseAnalyzer
from GazeDetectors.BaseDetector import BaseDetector
from GazeEvents.BaseEvent import BaseEvent


class EventFeaturesAnalyzer(BaseAnalyzer):
    EVENT_FEATURES = {
        "Count", "Micro-Saccade Ratio", "Amplitude", "Duration", "Azimuth", "Peak Velocity"
    }

    _DEFAULT_STATISTICAL_TEST = "Mann-Whitney"

    @staticmethod
    def preprocess_dataset(dataset_name: str,
                           detectors: List[BaseDetector] = None,
                           verbose=False,
                           **kwargs) -> pd.DataFrame:
        """ Loads the dataset and preprocesses it to extract the detected events by each rater/detector. """
        if verbose:
            print(f"Preprocessing dataset `{dataset_name}`...")
        start = time.time()
        _, events_df, _ = super(EventFeaturesAnalyzer, EventFeaturesAnalyzer).preprocess_dataset(
            dataset_name, detectors, False, **kwargs
        )
        end = time.time()
        if verbose:
            print(f"\tPreprocessing:\t{end - start:.2f}s")
        return events_df

    @classmethod
    def calculate_observed_data(cls,
                                events_df: pd.DataFrame,
                                ignore_events: Set[cnfg.EVENT_LABELS] = None,
                                verbose: bool = False,
                                **kwargs) -> Dict[str, pd.DataFrame]:
        """
        Extract the features of the detected events.

        :param events_df: A DataFrame containing the detected events of each rater/detector.
        :param ignore_events: A set of event labels to ignore when extracting the features.
        :param verbose: Whether to print the progress of the analysis.
        :param kwargs: placeholder for additional parameters used by inherited classes.

        :return: A dictionary mapping a feature name to a DataFrame containing the extracted features.
        """
        with warnings.catch_warnings():
            if verbose:
                print("Extracting event features...")
            warnings.simplefilter("ignore")
            ignore_events = ignore_events or set()
            results = {}
            for feature in cls.EVENT_FEATURES:
                start = time.time()
                if feature == "Count":
                    grouped = cls.__event_counts_impl(events_df, ignore_events=ignore_events)
                elif feature == "Micro-Saccade Ratio":
                    grouped = cls.__microsaccade_ratio_impl(events_df)
                else:
                    attr = feature.lower().replace(" ", "_")
                    feature_df = events_df.map(lambda cell: [getattr(e, attr) for e in cell if
                                                             e.event_label not in ignore_events and hasattr(e, attr)])
                    grouped = cls.group_and_aggregate(feature_df)
                results[feature] = grouped
                end = time.time()
                if verbose:
                    print(f"\t{feature}:\t{end - start:.2f}s")
        return results

    @classmethod
    def statistical_analysis(cls,
                             features_dict: Dict[str, pd.DataFrame],
                             test_name: str = _DEFAULT_STATISTICAL_TEST) -> Dict[str, pd.DataFrame]:
        return {k: cls._statistical_analysis_impl(v, test_name) for k, v in features_dict.items()}

    @classmethod
    def _statistical_analysis_impl(cls,
                                   feature_df: pd.DataFrame,
                                   test_name: str) -> pd.DataFrame:
        """
        Performs a two-sample statistical test on the set of measured event-features between two raters/detectors.
        :param feature_df: A DataFrame containing the extracted features of the events detected by each rater/detector.
            Each column represents a different rater/detector, and each cell contains a list of the measured values.
        :param test_name: The name of the statistical test to perform.
        :return: A DataFrame containing the results of the statistical test between each pair of raters/detectors.
        """
        # calculate the statistical test for each pair of columns
        feature_df = feature_df.map(lambda cell: [v for v in cell if not np.isnan(v)])
        stat_test = cls._get_statistical_test_func(test_name)
        results = hlp.apply_on_column_pairs(feature_df, stat_test, is_symmetric=True)
        return cls._rearrange_statistical_results(results)

    @staticmethod
    def __event_counts_impl(events: pd.DataFrame, ignore_events: Set[cnfg.EVENT_LABELS] = None) -> pd.DataFrame:
        """
        Counts the number of detected events for each detector by type of event, and groups the results by the stimulus.
        :param events: A DataFrame containing the detected events of each rater/detector.
        :return: A DataFrame containing the count of events detected by each rater/detector (cols), grouped by the given
            criteria (rows).
        """

        def count_event_labels(data: List[Union[BaseEvent, cnfg.EVENT_LABELS]]) -> pd.Series:
            labels = pd.Series([e.event_label if isinstance(e, BaseEvent) else e for e in data])
            counts = labels.value_counts()
            if counts.empty:
                return pd.Series({l: 0 for l in cnfg.EVENT_LABELS})
            if len(counts) == len(cnfg.EVENT_LABELS):
                return counts
            missing_labels = pd.Series({l: 0 for l in cnfg.EVENT_LABELS if l not in counts.index})
            return pd.concat([counts, missing_labels]).sort_index()

        ignore_events = ignore_events or set()
        events = events.map(lambda cell: [e for e in cell if e.event_label not in ignore_events])
        event_counts = events.map(count_event_labels)
        grouped_vals = event_counts.groupby(level=cnst.STIMULUS).agg(list).map(sum)
        if len(grouped_vals.index) == 1:
            return grouped_vals
        # there is more than one group, so add a row for "all" groups
        group_all = pd.Series(event_counts.sum(axis=0), index=event_counts.columns, name="all")
        grouped_vals = pd.concat([grouped_vals.T, group_all], axis=1).T  # add "all" row
        return grouped_vals

    @staticmethod
    def __microsaccade_ratio_impl(events: pd.DataFrame,
                                  threshold_amplitude: float = cnfg.MICROSACCADE_AMPLITUDE_THRESHOLD) -> pd.DataFrame:
        saccades = events.map(lambda cell: [e for e in cell if e.event_label == cnfg.EVENT_LABELS.SACCADE])
        saccades_count = saccades.map(len).to_numpy()
        microsaccades = saccades.map(lambda cell: [e for e in cell if e.amplitude < threshold_amplitude])
        microsaccades_count = microsaccades.map(len).to_numpy()

        ratios = np.divide(microsaccades_count, saccades_count,
                           out=np.full_like(saccades_count, fill_value=np.nan, dtype=float),  # fill NaN if denom is 0
                           where=saccades_count != 0)
        ratios = pd.DataFrame(ratios, index=events.index, columns=events.columns)
        return EventFeaturesAnalyzer.group_and_aggregate(ratios)
