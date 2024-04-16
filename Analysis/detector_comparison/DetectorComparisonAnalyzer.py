import time
import warnings
import itertools
from abc import ABC
from typing import Set, Dict, Union, List

import numpy as np
import pandas as pd

import Config.constants as cnst
import Utils.metrics as metrics

from Analysis.BaseAnalyzer import BaseAnalyzer
from DataSetLoaders.DataSetFactory import DataSetFactory
from GazeDetectors.BaseDetector import BaseDetector
from Analysis.EventMatcher import EventMatcher as Matcher


class DetectorComparisonAnalyzer(BaseAnalyzer, ABC):
    DEFAULT_EVENT_MATCHING_PARAMS = {
        "match_by": "onset",
        "max_onset_latency": 15,
        "allow_cross_matching": False,
        "ignore_events": None,
    }

    SAMPLE_METRICS = {
        "Accuracy": "acc",
        "Levenshtein Distance": "lev",
        "Cohen's Kappa": "kappa",
        "Mathew's Correlation": "mcc",
        "Transition Matrix l2-norm": "frobenius",
        "Transition Matrix KL-Divergence": "kl"
    }

    MATCHED_EVENT_FEATURES = {
        "Onset Jitter", "Offset Jitter", "L2 Timing Difference", "IoU", "Overlap Time", "Amplitude Difference",
        "Duration Difference", "Azimuth Difference", "Peak Velocity Difference"
    }

    MATCH_RATIO_STR = "Match Ratio"
    MATCH_FEATURES_STR = "Matched Event Features"
    SAMPLE_METRICS_STR = "Sample Metrics"

    @staticmethod
    def preprocess_dataset(dataset_name: str,
                           detectors: List[BaseDetector] = None,
                           verbose=False,
                           **kwargs):
        """
        Preprocess the dataset by:
            1. Loading the dataset
            2. Detecting events using the given detectors
            3. Match events detected by each pair of detectors
            4. Extract pairs of (human-rater, detector) for future analysis

        :param dataset_name: The name of the dataset to load and preprocess.
        :param detectors: A list of detectors to use for detecting events. If None, the default detectors will be used.
        :param verbose: Whether to print the progress of the preprocessing.
        :keyword column_mapper: A function to map the column names of the samples, events, and detector results DataFrames.
        :additional keyword arguments: Additional parameters to pass to the event matching algorithm (see EventMatcher).

        :return: the preprocessed samples, events, raw detector results, event matches, and comparison columns.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if verbose:
                print(f"Preprocessing dataset `{dataset_name}`...")
            start = time.time()
            detectors = DetectorComparisonAnalyzer._get_default_detectors() if detectors is None else detectors
            samples_df, events_df, detector_results_df = DataSetFactory.load_and_detect(dataset_name, detectors)

            # rename columns
            column_mapper = kwargs.pop("column_mapper", lambda col: col)
            samples_df.rename(columns=column_mapper, inplace=True)
            events_df.rename(columns=column_mapper, inplace=True)
            detector_results_df.rename(columns=column_mapper, inplace=True)

            # match events
            kwargs = {**DetectorComparisonAnalyzer.DEFAULT_EVENT_MATCHING_PARAMS, **kwargs}
            matches = Matcher.match_events(events_df, is_symmetric=True, **kwargs)

            # extract column-pairs to compare
            rater_names = [col.upper() for col in samples_df.columns if len(col) == 2]
            detector_names = [col for col in samples_df.columns if "det" in col.lower()]
            rater_rater_pairs = list(itertools.combinations(sorted(rater_names), 2))
            rater_detector_pairs = [(rater, detector) for rater in rater_names for detector in detector_names]
            comparison_columns = rater_rater_pairs + rater_detector_pairs
            end = time.time()
            if verbose:
                print(f"\tPreprocessing:\t{end - start:.2f}s")
        return samples_df, events_df, detector_results_df, matches, comparison_columns

    @staticmethod
    def analyze(events_df: pd.DataFrame,
                matches_df: pd.DataFrame = None,
                samples_df: pd.DataFrame = None,
                ignore_events: Set[cnst.EVENT_LABELS] = None,
                verbose=False):
        """
        Analyze the given events, event-matches and samples, by calculating various metrics and features.

        :param events_df: A DataFrame containing the detected events of each rater/detector.
        :param matches_df: A DataFrame containing the matched events between each pair of raters/detectors.
        :param samples_df: A DataFrame containing the detected samples of each rater/detector. Does not depend on
            the `ignore_events` parameter.
        :param ignore_events: A set of event labels to ignore when calculating metrics and features.
        :param verbose: Whether to print the progress of the analysis.

        :return: A dictionary containing the results of the analysis.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            start = time.time()
            ignore_events = ignore_events or set()
            results = super(DetectorComparisonAnalyzer).analyze(events_df, ignore_events, verbose)
            if matches_df and not matches_df.empty:
                results[DetectorComparisonAnalyzer.MATCH_RATIO_STR] = DetectorComparisonAnalyzer._calc_event_matching_ratios(
                    events_df, matches_df, ignore_events=ignore_events, verbose=verbose)
                results[DetectorComparisonAnalyzer.MATCH_FEATURES_STR] = DetectorComparisonAnalyzer._calc_matched_events_feature(
                    matches_df, ignore_events=ignore_events, verbose=verbose)
            if samples_df and not samples_df.empty:
                results[DetectorComparisonAnalyzer.SAMPLE_METRICS_STR] = DetectorComparisonAnalyzer._calc_sample_metrics(
                    samples_df, verbose=verbose)
            end = time.time()
            if verbose:
                print(f"Total Analysis Time:\t{end - start:.2f}s")
        return results

    @staticmethod
    def _calc_sample_metrics(samples_df: pd.DataFrame,
                             verbose=False):
        global_start = time.time()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = {}
            for metric_name, metric_short in DetectorComparisonAnalyzer.SAMPLE_METRICS.items():
                start = time.time()
                computed = DetectorComparisonAnalyzer.__calc_sample_metric_impl(samples_df, metric_short)
                results[metric_name] = computed
                end = time.time()
                if verbose:
                    print(f"\tCalculating `{metric_name}`:\t{end - start:.2f}s")
            global_end = time.time()
            if verbose:
                print(f"Total time:\t{global_end - global_start:.2f}s\n")
        return results

    @staticmethod
    def _calc_event_matching_ratios(events_df: pd.DataFrame,
                                    matches_df: pd.DataFrame,
                                    ignore_events: Set[cnst.EVENT_LABELS] = None,
                                    verbose=False) -> Dict[str, pd.DataFrame]:
        global_start = time.time()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ignore_events = ignore_events or set()
            event_counts = events_df.map(lambda cell: len([e for e in cell if e.event_label not in ignore_events]))
            match_counts = matches_df.map(
                lambda cell: len([k for k in cell.keys() if k.event_label not in ignore_events])
                if pd.notnull(cell) else np.nan
            )
            ratios = np.zeros_like(match_counts, dtype=float)
            for i in range(match_counts.index.size):
                for j in range(match_counts.columns.size):
                    gt_col, _pred_col = match_counts.columns[j]
                    ratios[i, j] = match_counts.iloc[i, j] / event_counts.iloc[i][gt_col]
            ratios = pd.DataFrame(100 * ratios, index=match_counts.index, columns=match_counts.columns)
            ratios = DetectorComparisonAnalyzer.group_and_aggregate(ratios, group_by=cnst.STIMULUS)
        global_end = time.time()
        if verbose:
            print(f"Total time:\t{global_end - global_start:.2f}s\n")
        return {DetectorComparisonAnalyzer.MATCH_RATIO_STR: ratios}

    @staticmethod
    def _calc_matched_events_feature(matches_df: pd.DataFrame,
                                     ignore_events: Set[cnst.EVENT_LABELS] = None,
                                     verbose=False) -> Dict[str, pd.DataFrame]:
        global_start = time.time()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = {}
            for feature in DetectorComparisonAnalyzer.MATCHED_EVENT_FEATURES:
                start = time.time()
                feature_diffs = DetectorComparisonAnalyzer.__calc_matched_events_feature_impl(matches_df, feature, ignore_events)
                results[feature] = feature_diffs
                end = time.time()
                if verbose:
                    print(f"\tCalculating Matched {feature}:\t{end - start:.2f}s")
        global_end = time.time()
        if verbose:
            print(f"Total time:\t{global_end - global_start:.2f}s\n")
        return results

    @staticmethod
    def __calc_sample_metric_impl(samples: pd.DataFrame,
                                  metric: str) -> pd.DataFrame:
        # extract the function to calculate the metric
        if metric == "acc" or metric == "accuracy" or metric == "balanced accuracy":
            measure_func = metrics.balanced_accuracy
        elif metric == "lev" or metric == "levenshtein":
            measure_func = metrics.levenshtein_distance
        elif metric == "kappa" or metric == "cohen kappa":
            measure_func = metrics.cohen_kappa
        elif metric == "mcc" or metric == "matthews correlation":
            measure_func = metrics.matthews_correlation
        elif metric == "fro" or metric == "frobenius" or metric == "l2":
            measure_func = lambda s1, s2: metrics.transition_matrix_distance(s1, s2, norm="fro")
        elif metric == "kl" or metric == "kl divergence" or metric == "kullback leibler":
            measure_func = lambda s1, s2: metrics.transition_matrix_distance(s1, s2, norm="kl")
        else:
            raise NotImplementedError(f"Unknown metric for samples:\t{metric}")

        # perform the calculation
        column_pairs = list(itertools.combinations(samples.columns, 2))
        res = {}
        for idx in samples.index:
            res[idx] = {}
            for pair in column_pairs:
                vals1, vals2 = samples.loc[idx, pair[0]], samples.loc[idx, pair[1]]
                if len(vals1) == 0 or pd.isnull(vals1).all():
                    res[idx][pair] = None
                elif len(vals2) == 0 or pd.isnull(vals2).all():
                    res[idx][pair] = None
                else:
                    res[idx][pair] = measure_func(vals1, vals2)
        res = pd.DataFrame.from_dict(res, orient="index")
        res.index.names = samples.index.names

        # aggregate over stimuli and return
        return DetectorComparisonAnalyzer.group_and_aggregate(res, cnst.STIMULUS)

    @staticmethod
    def __calc_matched_events_feature_impl(matches_df: pd.DataFrame,
                                           feature: str,
                                           ignore_events: Set[cnst.EVENT_LABELS] = None) -> pd.DataFrame:
        ignore_events = ignore_events or set()
        if feature == "Onset Jitter":
            diffs = matches_df.map(
                lambda cell: [k.start_time - v.start_time for k, v in cell.items() if
                              k.event_label not in ignore_events]
                if pd.notnull(cell) else np.nan
            )
        elif feature == "Offset Jitter":
            diffs = matches_df.map(
                lambda cell: [k.end_time - v.end_time for k, v in cell.items() if k.event_label not in ignore_events]
                if pd.notnull(cell) else np.nan
            )
        elif feature == "L2 Timing Difference":
            diffs = matches_df.map(
                lambda cell: [k.l2_timing_offset(v) for k, v in cell.items() if k.event_label not in ignore_events]
                if pd.notnull(cell) else np.nan
            )
        elif feature == "IoU":
            diffs = matches_df.map(
                lambda cell: [k.intersection_over_union(v) for k, v in cell.items() if
                              k.event_label not in ignore_events]
                if pd.notnull(cell) else np.nan
            )
        elif feature == "Overlap Time":
            diffs = matches_df.map(
                lambda cell: [k.overlap_time(v) for k, v in cell.items() if k.event_label not in ignore_events]
                if pd.notnull(cell) else np.nan
            )
        elif feature == "Duration Difference":
            diffs = matches_df.map(
                lambda cell: [k.duration - v.duration for k, v in cell.items() if k.event_label not in ignore_events]
                if pd.notnull(cell) else np.nan
            )
        elif feature == "Amplitude Difference":
            diffs = matches_df.map(
                lambda cell: [k.amplitude - v.amplitude for k, v in cell.items() if k.event_label not in ignore_events]
                if pd.notnull(cell) else np.nan
            )
        elif feature == "Azimuth Difference":
            diffs = matches_df.map(
                lambda cell: [k.azimuth - v.azimuth for k, v in cell.items() if k.event_label not in ignore_events]
                if pd.notnull(cell) else np.nan
            )
        elif feature == "Peak Velocity Difference":
            diffs = matches_df.map(
                lambda cell: [k.peak_velocity - v.peak_velocity for k, v in cell.items() if
                              k.event_label not in ignore_events]
                if pd.notnull(cell) else np.nan
            )
        else:
            raise ValueError(f"Unknown feature: {feature}")
        return DetectorComparisonAnalyzer.group_and_aggregate(diffs, group_by=cnst.STIMULUS)