import time
import warnings
from abc import ABC, abstractmethod
from typing import List, Union, Optional, Set, Dict, final

import numpy as np
import pandas as pd
import scipy.stats as stat

import Config.constants as cnst
import Config.experiment_config as cnfg
import Analysis.helpers as hlp
from DataSetLoaders.DataSetFactory import DataSetFactory
from GazeDetectors.BaseDetector import BaseDetector
from GazeEvents.BaseEvent import BaseEvent


class BaseAnalyzer(ABC):

    EVENT_FEATURES = {
        "Count", "Micro-Saccade Ratio", "Amplitude", "Duration", "Azimuth", "Peak Velocity"
    }
    EVENT_FEATURES_STR = "Event Features"

    @staticmethod
    def preprocess_dataset(dataset_name: str,
                           detectors: List[BaseDetector] = None,
                           verbose=False,
                           **kwargs) -> (pd.DataFrame, pd.DataFrame, pd.DataFrame):
        """
        Preprocess the dataset by:
            1. Loading the dataset
            2. Detecting events using the given detectors
            3. Renaming the columns of the samples, events, and detector results DataFrames.

        :param dataset_name: The name of the dataset to load and preprocess.
        :param detectors: A list of detectors to use for detecting events. If None, the default detectors will be used.
        :param verbose: Whether to print the progress of the preprocessing.
        :keyword column_mapper: A function to map the column names of the samples, events, and detector results DataFrames.

        :return: the preprocessed samples, events and raw detector results DataFrames.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if verbose:
                print(f"Preprocessing dataset `{dataset_name}`...")
            start = time.time()
            detectors = BaseAnalyzer._get_default_detectors() if detectors is None else detectors
            samples_df, events_df, detector_results_df = DataSetFactory.load_and_detect(dataset_name, detectors)

            # rename columns
            column_mapper = kwargs.pop("column_mapper", lambda col: col)
            samples_df.rename(columns=column_mapper, inplace=True)
            events_df.rename(columns=column_mapper, inplace=True)
            detector_results_df.rename(columns=column_mapper, inplace=True)

            end = time.time()
            if verbose:
                print(f"\tPreprocessing:\t{end - start:.2f}s")
        return samples_df, events_df, detector_results_df

    @classmethod
    @final
    def analyze(cls,
                events_df: pd.DataFrame,
                test_name: str,
                ignore_events: Set[cnfg.EVENT_LABELS] = None,
                verbose: bool = False,
                **kwargs) -> (Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            start = time.time()
            ignore_events = ignore_events or set()

            # extract observations
            if verbose:
                print("Calculating Observations...")
            observations_start = time.time()
            obs_dict = cls.calculate_observed_data(events_df, ignore_events=ignore_events, **kwargs)
            observations_end = time.time()
            if verbose:
                print(f"Observations Time:\t{observations_end - observations_start:.2f}s")

            # perform statistical analysis
            if verbose:
                print("Performing Statistical Analysis...")
            stat_start = time.time()
            stats_dict = {k: cls.statistical_analysis(v, test_name, **kwargs) for k, v in obs_dict.items()}
            stat_end = time.time()
            if verbose:
                print(f"Statistical Analysis Time:\t{stat_end - stat_start:.2f}s")

            # conclude analysis
            end = time.time()
            if verbose:
                print(f"Total Analysis Time:\t{end - start:.2f}s")
        return obs_dict, stats_dict

    @classmethod
    @abstractmethod
    def calculate_observed_data(cls,
                                data: pd.DataFrame,
                                ignore_events: Set[cnfg.EVENT_LABELS] = None,
                                verbose: bool = False,
                                **kwargs) -> Dict[str, pd.DataFrame]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def statistical_analysis(cls,
                             data: pd.DataFrame,
                             test_name: str,
                             **kwargs) -> pd.DataFrame:
        raise NotImplementedError

    @classmethod
    def analyze_impl(cls,
                     events_df: pd.DataFrame,
                     ignore_events: Set[cnfg.EVENT_LABELS] = None,
                     verbose: bool = False,
                     **kwargs):
        """
        Analyze the given events DataFrame and extract the features of the detected events.

        :param events_df: A DataFrame containing the detected events of each rater/detector.
        :param ignore_events: A set of event labels to ignore when extracting the features.
        :param verbose: Whether to print the progress of the analysis.
        :param kwargs: placeholder for additional parameters used by inherited classes.

        :return: A dictionary mapping a feature name to a DataFrame containing the extracted features.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            start = time.time()
            ignore_events = ignore_events or set()
            results = {BaseAnalyzer.EVENT_FEATURES_STR: BaseAnalyzer._extract_event_features(events_df,
                                                                                             ignore_events=ignore_events,
                                                                                             verbose=verbose)}
            end = time.time()
            if verbose:
                print(f"Total Analysis Time:\t{end - start:.2f}s")
        return results

    @staticmethod
    def group_and_aggregate(data: pd.DataFrame,
                            group_by: Optional[Union[str, List[str]]] = cnst.STIMULUS) -> pd.DataFrame:
        """ Group the data by the given criteria and aggregate the values in each group. """
        if group_by is None:
            return data
        grouped_vals = data.groupby(level=group_by).agg(list).map(lambda group: pd.Series(group).explode().to_list())
        if len(grouped_vals.index) == 1:
            return grouped_vals
        # there is more than one group, so add a row for "all" groups
        group_all = pd.Series([data[col].explode().to_list() for col in data.columns], index=data.columns, name="all")
        grouped_vals = pd.concat([grouped_vals.T, group_all], axis=1).T  # add "all" row
        return grouped_vals

    @staticmethod
    def event_feature_statistical_comparison(feature_df: pd.DataFrame, test_name: str):
        """
        Performs a two-sample statistical test on the set of measured event-features between two raters/detectors.
        :param feature_df: A DataFrame containing the extracted features of the events detected by each rater/detector.
            Each column represents a different rater/detector, and each cell contains a list of the measured values.
        :param test_name: The name of the statistical test to perform.
        :return: A DataFrame containing the results of the statistical test between each pair of raters/detectors.
        """
        test_name = test_name.lower().replace("_", " ").replace("-", " ").strip()
        if test_name in {"u", "u test", "mann whitney", "mann whitney u", "mannwhitneyu"}:
            test_func = stat.mannwhitneyu
        elif test_name in {"rank sum", "ranksum", "ranksums", "wilcoxon rank sum"}:
            test_func = stat.ranksums
        else:
            raise ValueError(f"Unknown test name: {test_name}")

        # calculate the statistical test for each pair of columns
        feature_df = feature_df.map(lambda cell: [v for v in cell if not np.isnan(v)])
        results = hlp.apply_on_column_pairs(feature_df, test_func, is_symmetric=True)

        # remap the results to a DataFrame
        statistics = {(col1, col2, cnst.STATISTIC): {vk: vv[0] for vk, vv in vals.items()}
                      for (col1, col2), vals in results.items()}
        p_values = {(col1, col2, cnst.P_VALUE): {vk: vv[1] for vk, vv in vals.items()}
                    for (col1, col2), vals in results.items()}
        results = {**statistics, **p_values}
        results = pd.DataFrame(results)

        # reorder columns to group by the first column, then the second column, and finally by the statistic type
        column_order = {triplet: (
            len([trp for trp in results.keys() if trp[0] == triplet[0]]),
            len([trp for trp in results.keys() if trp[0] == triplet[1]]),
            1 if triplet[2] == cnst.STATISTIC else 0
        ) for triplet in results.keys()}
        ordered_columns = sorted(results.columns, key=lambda col: column_order[col], reverse=True)
        results = results[ordered_columns]
        return results

    @staticmethod
    def _get_default_detectors() -> Union[BaseDetector, List[BaseDetector]]:
        from GazeDetectors.IVTDetector import IVTDetector
        from GazeDetectors.IDTDetector import IDTDetector
        from GazeDetectors.EngbertDetector import EngbertDetector
        from GazeDetectors.NHDetector import NHDetector
        from GazeDetectors.REMoDNaVDetector import REMoDNaVDetector
        return [IVTDetector(), IDTDetector(), EngbertDetector(), NHDetector(), REMoDNaVDetector()]

    @staticmethod
    def _extract_event_features(events_df: pd.DataFrame,
                                ignore_events: Set[cnfg.EVENT_LABELS] = None,
                                verbose=False) -> Dict[str, pd.DataFrame]:
        global_start = time.time()
        if verbose:
            print("Extracting Event Features...")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ignore_events = ignore_events or set()
            results = {}
            for feature in BaseAnalyzer.EVENT_FEATURES:
                start = time.time()
                if feature == "Count":
                    grouped = BaseAnalyzer.__event_counts_impl(events_df, ignore_events=ignore_events)
                elif feature == "Micro-Saccade Ratio":
                    grouped = BaseAnalyzer.__microsaccade_ratio_impl(events_df)
                else:
                    attr = feature.lower().replace(" ", "_")
                    feature_df = events_df.map(lambda cell: [getattr(e, attr) for e in cell if
                                                             e.event_label not in ignore_events and hasattr(e, attr)])
                    grouped = BaseAnalyzer.group_and_aggregate(feature_df)
                results[feature] = grouped
                end = time.time()
                if verbose:
                    print(f"\tExtracting {feature}s:\t{end - start:.2f}s")
        global_end = time.time()
        if verbose:
            print(f"Total time:\t{global_end - global_start:.2f}s\n")
        return results

    @staticmethod
    def __event_counts_impl(events: pd.DataFrame, ignore_events: Set[cnfg.EVENT_LABELS] = None, ) -> pd.DataFrame:
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
        return BaseAnalyzer.group_and_aggregate(ratios)