# Event-Matching Logic
# Implementation of different methods to match two sequences of gaze-events, that may have been detected by different
# human annotators or detection algorithms, as discussed in section "Event Matching Methods" in the article:
#     Startsev, M., Zemblys, R. Evaluating Eye Movement Event Detection: A Review of the State of the Art
#     Behav Res 55, 1653–1714 (2023). https://doi.org/10.3758/s13428-021-01763-7

from typing import Sequence, Dict, Union

from GazeEvents.BaseEvent import BaseEvent


def first_overlap_matching(ground_truth: Sequence[BaseEvent],
                           predictions: Sequence[BaseEvent],
                           min_overlap: float = 0,
                           allow_cross_matching: bool = True) -> Dict[BaseEvent, Union[BaseEvent, Sequence[BaseEvent]]]:
    """
    Matches the first predicted event that overlaps with each ground-truth event, above a minimal overlap time.
    """
    return generic_matching(ground_truth, predictions, allow_cross_matching,
                            min_overlap=min_overlap, reduction="first")


def last_overlap_matching(ground_truth: Sequence[BaseEvent],
                          predictions: Sequence[BaseEvent],
                          min_overlap: float = 0,
                          allow_cross_matching: bool = True) -> Dict[BaseEvent, Union[BaseEvent, Sequence[BaseEvent]]]:
    """
    Matches the last predicted event that overlaps with each ground-truth event, above a minimal overlap time.
    """
    return generic_matching(ground_truth, predictions, allow_cross_matching,
                            min_overlap=min_overlap, reduction="last")


def longest_overlap_matching(ground_truth: Sequence[BaseEvent],
                             predictions: Sequence[BaseEvent],
                             min_overlap: float = 0,
                             allow_cross_matching: bool = True) -> Dict[BaseEvent, Union[BaseEvent, Sequence[BaseEvent]]]:
    """
    Matches the longest predicted event that overlaps with each ground-truth event, above a minimal overlap time.
    """
    return generic_matching(ground_truth, predictions, allow_cross_matching,
                            min_overlap=min_overlap, reduction="longest")


def max_overlap_matching(ground_truth: Sequence[BaseEvent],
                         predictions: Sequence[BaseEvent],
                         min_overlap: float = 0,
                         allow_cross_matching: bool = True) -> Dict[BaseEvent, Union[BaseEvent, Sequence[BaseEvent]]]:
    """
    Matches the predicted event with maximum overlap with each ground-truth event, above a minimal overlap time.
    """
    return generic_matching(ground_truth, predictions, allow_cross_matching,
                            min_overlap=min_overlap, reduction="max overlap")


def iou_matching(ground_truth: Sequence[BaseEvent],
                 predictions: Sequence[BaseEvent],
                 min_iou: float = 0,
                 allow_cross_matching: bool = True) -> Dict[BaseEvent, Union[BaseEvent, Sequence[BaseEvent]]]:
    """
    Matches the predicted event with maximum intersection-over-union with each ground-truth event, above a minimal value.
    """
    return generic_matching(ground_truth, predictions, allow_cross_matching,
                            min_iou=min_iou, reduction="iou")


def onset_latency_matching(ground_truth: Sequence[BaseEvent],
                           predictions: Sequence[BaseEvent],
                           max_onset_latency: float = 0,
                           allow_cross_matching: bool = True) -> Dict[BaseEvent, Union[BaseEvent, Sequence[BaseEvent]]]:
    """
    Matches the predicted event with least onset latency with each ground-truth event, below a maximum latency.
    """
    return generic_matching(ground_truth, predictions, allow_cross_matching,
                            max_onset_latency=max_onset_latency, reduction="onset latency")


def offset_latency_matching(ground_truth: Sequence[BaseEvent],
                            predictions: Sequence[BaseEvent],
                            max_offset_latency: float = 0,
                            allow_cross_matching: bool = True) -> Dict[BaseEvent, Union[BaseEvent, Sequence[BaseEvent]]]:
    """
    Matches the predicted event with least offset latency with each ground-truth event, below a maximum latency.
    """
    return generic_matching(ground_truth, predictions, allow_cross_matching,
                            max_offset_latency=max_offset_latency, reduction="offset latency")


def window_based_matching(ground_truth: Sequence[BaseEvent],
                          predictions: Sequence[BaseEvent],
                          max_onset_latency: float = 0,
                          max_offset_latency: float = 0,
                          allow_cross_matching: bool = True,
                          reduction: str = "iou") -> Dict[BaseEvent, Union[BaseEvent, Sequence[BaseEvent]]]:
    """
    Finds all predicted events with onset- and offset-latencies within a specified window for each ground-truth event,
    and chooses the best gt-prediction match based on the specified reduction function.
    """
    return generic_matching(ground_truth, predictions, allow_cross_matching,
                            max_onset_latency=max_onset_latency,
                            max_offset_latency=max_offset_latency,
                            reduction=reduction)


def generic_matching(ground_truth: Sequence[BaseEvent],
                     predictions: Sequence[BaseEvent],
                     allow_cross_matching: bool,
                     min_overlap: float = - float("inf"),
                     min_iou: float = - float("inf"),
                     max_onset_latency: float = float("inf"),
                     max_offset_latency: float = float("inf"),
                     reduction: str = "all") -> Dict[BaseEvent, Union[BaseEvent, Sequence[BaseEvent]]]:
    """
    Match each ground-truth event to a predicted event(s) that satisfies the specified criteria.

    :param ground_truth: sequence of ground-truth events
    :param predictions: sequence of predicted events
    :param allow_cross_matching: if True, a ground-truth event can match a predicted event of a different type
    :param min_overlap: minimum overlap time (in ms) to consider a possible match
    :param min_iou: minimum intersection-over-union to consider a possible match
    :param max_onset_latency: maximum absolute difference (in ms) between the start times of the GT and predicted events
    :param max_offset_latency: maximum absolute difference (in ms) between the end times of the GT and predicted events
    :param reduction: name of reduction function used to choose a predicted event(s) from multiple matching ones:
        - 'all': return all matched events
        - 'first': return the first matched event
        - 'last': return the last matched event
        - 'longest': return the longest matched event
        - 'max overlap': return the matched event with maximum overlap with the GT event
        - 'iou': return the matched event with the maximum intersection-over-union with the GT event
        - 'onset latency': return the matched event with the least onset latency
        - 'offset latency': return the matched event with the least offset latency
    :return: dictionary, where keys are ground-truth events and values are their matched predicted event(s)
    :raises NotImplementedError: if the reduction function is not implemented
    """
    matches = {}
    for gt in ground_truth:
        possible_matches = _find_matches(gt=gt,
                                         predictions=predictions,
                                         allow_cross_matching=allow_cross_matching,
                                         min_overlap=min_overlap,
                                         min_iou=min_iou,
                                         max_onset_latency=max_onset_latency,
                                         max_offset_latency=max_offset_latency)
        p = _choose_match(gt, possible_matches, reduction)
        if len(p):
            matches[gt] = p
    return matches


def _find_matches(gt: BaseEvent,
                  predictions: Sequence[BaseEvent],
                  allow_cross_matching: bool,
                  min_overlap: float,
                  min_iou: float,
                  max_onset_latency: float,
                  max_offset_latency: float,) -> Sequence[BaseEvent]:
    """
    Find predicted events that are possible matches for the ground-truth event, based on the specified criteria.

    :param gt: ground-truth event
    :param predictions: sequence of predicted events
    :param allow_cross_matching: if True, a GT event can match a predicted event of a different type
    :param min_overlap: minimum overlap time to consider a possible match
    :param min_iou: minimum intersection-over-union to consider a possible match
    :param max_onset_latency: maximum absolute difference between the start times of the GT and predicted events
    :param max_offset_latency: maximum absolute difference between the end times of the GT and predicted events
    :return: sequence of predicted events that are possible matches for the ground-truth event
    """
    if not allow_cross_matching:
        predictions = [p for p in predictions if p.event_type() == gt.event_type()]
    predictions = [p for p in predictions if
                   gt.overlap_time(p) >= min_overlap and
                   gt.intersection_over_union(p) >= min_iou and
                   abs(p.start_time - gt.start_time) <= max_onset_latency and
                   abs(p.end_time - gt.end_time) <= max_offset_latency]
    return predictions


def _choose_match(gt: BaseEvent,
                  matches: Sequence[BaseEvent],
                  reduction: str) -> Union[BaseEvent, Sequence[BaseEvent]]:
    """
    Choose predicted event(s) matching the ground-truth event, based on the reduction function.
    Possible reduction functions:
        - 'all': return all matched events
        - 'first': return the first matched event
        - 'last': return the last matched event
        - 'longest': return the longest matched event
        - 'max overlap': return the matched event with maximum overlap with the GT event
        - 'iou': return the matched event with the maximum intersection-over-union with the GT event
        - 'onset latency': return the matched event with the least onset latency
        - 'offset latency': return the matched event with the least offset latency

    :param gt: ground-truth event
    :param matches: sequence of predicted events matching with the GT event
    :param reduction: reduction function to choose a predicted event from multiple matching ones

    :return: predicted event(s) matching the ground-truth event
    :raises NotImplementedError: if the reduction function is not implemented
    """
    reduction = reduction.lower().replace("_", " ").strip()
    if len(matches) == 0:
        return []
    if len(matches) == 1:
        return [matches[0]]
    if reduction == "all":
        return matches
    if reduction == "first":
        return [min(matches, key=lambda e: e.start_time)]
    if reduction == "last":
        return [max(matches, key=lambda e: e.start_time)]
    if reduction == "longest":
        return [max(matches, key=lambda e: e.duration)]
    if reduction == "max overlap":
        return [max(matches, key=lambda e: gt.overlap_time(e))]
    if reduction == "iou":
        return [max(matches, key=lambda e: gt.intersection_over_union(e))]
    if reduction == "onset latency":
        return [min(matches, key=lambda e: abs(e.start_time - gt.start_time))]
    if reduction == "offset latency":
        return [min(matches, key=lambda e: abs(e.end_time - gt.end_time))]
    raise NotImplementedError(f"Reduction function '{reduction}' is not implemented")
