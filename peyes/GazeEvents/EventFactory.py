import warnings
import numpy as np
import pandas as pd
from abc import ABC
from typing import List, Optional, Dict

import peyes.Config.constants as cnst
import peyes.Config.experiment_config as cnfg
import peyes.Utils.array_utils as arr_utils
from peyes.GazeEvents.BaseEvent import BaseEvent
from peyes.GazeEvents.BlinkEvent import BlinkEvent
from peyes.GazeEvents.FixationEvent import FixationEvent
from peyes.GazeEvents.SaccadeEvent import SaccadeEvent
from peyes.GazeEvents.PSOEvent import PSOEvent
from peyes.GazeEvents.SmoothPursuitEvent import SmoothPursuitEvent


class EventFactory(ABC):

    # TODO: add `make from event table` that parses event-summary table and creates events

    @staticmethod
    def make(label: cnfg.EVENT_LABELS, t: np.ndarray, **event_data) -> Optional[BaseEvent]:
        """
        Creates a single GazeEvent from the given data.

        :param label: The type of event to create
        :param t: The timestamps of the event
        :param event_data: The data to use for the event (e.g. x, y, pupil, etc.)

        :return: a GazeEvent object
        :raise: ValueError if the given event type is not valid
        """
        if label == cnfg.EVENT_LABELS.UNDEFINED:
            return None
        if len(t) < cnfg.MINIMUM_SAMPLES_IN_EVENT:
            # TODO: log warning
            return None
        vd = event_data.get("viewer_distance", cnfg.DEFAULT_VIEWER_DISTANCE)
        ps = event_data.get("pixel_size", cnfg.SCREEN_MONITOR.pixel_size)
        x = event_data.get("x", np.full_like(t, fill_value=np.nan))
        y = event_data.get("y", np.full_like(t, fill_value=np.nan))
        pupil = event_data.get("pupil", np.full_like(t, fill_value=np.nan))
        if label == cnfg.EVENT_LABELS.FIXATION:
            return FixationEvent(timestamps=t, x=x, y=y, pupil=pupil, viewer_distance=vd, pixel_size=ps)
        if label == cnfg.EVENT_LABELS.SACCADE:
            return SaccadeEvent(timestamps=t, x=x, y=y, pupil=pupil, viewer_distance=vd, pixel_size=ps)
        if label == cnfg.EVENT_LABELS.PSO:
            return PSOEvent(timestamps=t, x=x, y=y, pupil=pupil, viewer_distance=vd, pixel_size=ps)
        if label == cnfg.EVENT_LABELS.SMOOTH_PURSUIT:
            return SmoothPursuitEvent(timestamps=t, x=x, y=y, pupil=pupil, viewer_distance=vd, pixel_size=ps)
        if label == cnfg.EVENT_LABELS.BLINK:
            return BlinkEvent(timestamps=t, x=x, y=y, pupil=pupil, viewer_distance=vd, pixel_size=ps)
        raise ValueError(f"Invalid event type: {label}")

    @staticmethod
    def make_multiple(labels: np.ndarray, t: np.ndarray, **kwargs) -> List[BaseEvent]:
        """
        Creates a list of GazeEvents from the given data.

        :param labels: array of event labels
        :param t: array of timestamps (must be same length as ets)
        :param kwargs: dictionary of arrays of event data (e.g. x, y, pupil, etc.)

        :return: a list of GazeEvent objects
        :raise: ValueError if the length of `ets` and `t` are not the same
        """
        if len(labels) != len(t):
            raise ValueError("Length of `ets` and `t` must be the same")
        chunk_idxs = arr_utils.get_chunk_indices(labels)
        event_list = []
        for idxs in chunk_idxs:
            l: cnfg.EVENT_LABELS = labels[idxs[0]]
            event_data = {}
            for k, v in kwargs.items():
                event_data[k] = v[idxs] if hasattr(v, "__len__") else v
            event = EventFactory.make(l, t[idxs], **event_data)
            event_list.append(event)
        event_list = [ev for ev in event_list if ev is not None]  # filter Undefined (=None) events
        return event_list

    @staticmethod
    def make_from_gaze_data(gaze: pd.DataFrame,
                            vd: float = cnfg.DEFAULT_VIEWER_DISTANCE,
                            ps: float = cnfg.SCREEN_MONITOR.pixel_size,
                            column_mapping: Optional[Dict[str, str]] = None) -> List[BaseEvent]:
        if column_mapping:
            gaze = gaze.rename(columns=column_mapping, inplace=False)
        t = EventFactory.__extract_field(gaze, cnst.T, safe=False)
        l = EventFactory.__extract_field(gaze, cnst.EVENT, safe=False)  # event label
        x = EventFactory.__extract_field(gaze, cnst.X, safe=True)
        y = EventFactory.__extract_field(gaze, cnst.Y, safe=True)
        p = EventFactory.__extract_field(gaze, cnst.PUPIL, safe=True)  # pupil size
        return EventFactory.make_multiple(l, t, x=x, y=y, pupil=p, viewer_distance=vd, pixel_size=ps)

    @staticmethod
    def __extract_field(gaze: pd.DataFrame, field: str, safe: bool = True) -> np.ndarray:
        try:
            return gaze[field].values
        except KeyError:
            err_str = f"\"{field}\":\tUnable to extract \"{field}\" data from the given DataFrame."
            if safe:
                warnings.warn(err_str, RuntimeWarning)
                return np.full(shape=gaze.shape[0], fill_value=np.nan)
            raise KeyError(err_str)
