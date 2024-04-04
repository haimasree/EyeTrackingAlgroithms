import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import Config.constants as cnst

_HEATMAP_COLORMAP = "HOT"


def similarity_heatmap(data: pd.DataFrame, title: str, similarity_measure: str) -> go.Figure:
    fig = px.imshow(data.T,
                    title=title,
                    color_continuous_scale=_HEATMAP_COLORMAP,
                    labels=dict(x=cnst.TRIAL.capitalize(), y="Detectors", color=similarity_measure),
                    x=data.index.get_level_values(cnst.TRIAL),
                    aspect="auto")
    fig.update_layout(
        xaxis=dict(side="top"),
        yaxis=dict(tickmode="array",
                   tickvals=np.arange(len(data.columns)),
                   ticktext=data.columns.tolist()
                   ),
        coloraxis=dict(colorbar_x=1.,
                       colorbar_title_side='right',
                       ),
    )
    return fig


def count_grid(data: pd.DataFrame, **kwargs) -> go.Figure:
    """
    Creates a grid of bar plots, showing the count of each value in each cell of the DataFrame.
    :param data: DataFrame with the data to plot. Each cell should contain a Series with the counts of each value.
    :param kwargs: Additional arguments to pass to the plot:
        - title: Title of the plot.
        - column_title_mapper: Function to map column names to titles.
        - row_title_mapper: Function to map row names to titles.
    """
    fig = make_subplots(rows=data.index.size,
                        cols=data.columns.size,
                        row_titles=[kwargs.get("row_title_mapper", lambda x: x)(r) for r in data.index],
                        column_titles=[kwargs.get("column_title_mapper", lambda x: x)(c) for c in data.columns])
    for row_num, row_name in enumerate(data.index):
        for col_num, col_name in enumerate(data.columns):
            cell = data.loc[row_name, col_name]
            new_trace = go.Bar(x=cell.index, y=cell.values, name=col_name)
            fig.add_trace(
                row=row_num + 1,
                col=col_num + 1,
                trace=new_trace,
            )
    fig.update_layout(
        title_text=kwargs.get("title", "Counts"),
        showlegend=False
    )
    return fig


def distributions_grid(data: pd.DataFrame, plot_type: str, **kwargs) -> go.Figure:
    """
    Creates a grid of histograms or violin plots, showing the distribution of values in each cell of the DataFrame.
    :param data: DataFrame with the data to plot. Each cell should contain a list of values.
    :param plot_type: Type of plot to use. Either "histogram" or "violin".
    :param kwargs: Additional arguments to pass to the plot:
        - title: Title of the plot.
        - column_title_mapper: Function to map column names to titles.
        - row_title_mapper: Function to map row names to titles.
        - max_bins: Maximum number of bins to use in histograms (see go.Histogram).
        - points: Points to show in violin plots (see go.Violin).
        - side: Side of the violin plot to show (see go.Violin).
    """
    plot_type = plot_type.lower().strip()
    fig = make_subplots(rows=data.index.size,
                        cols=data.columns.size,
                        row_titles=[kwargs.get("row_title_mapper", lambda x: x)(r) for r in data.index],
                        column_titles=[kwargs.get("column_title_mapper", lambda x: x)(c) for c in data.columns])
    for row_num, row_name in enumerate(data.index):
        for col_num, col_name in enumerate(data.columns):
            cell = data.loc[row_name, col_name]
            if plot_type == "histogram" or plot_type == "bar":
                new_trace = go.Histogram(x=cell,
                                         showlegend=False,
                                         nbinsx=kwargs.get("max_bins", 20))
            elif plot_type == "violin":
                new_trace = go.Violin(y=cell,
                                      showlegend=False,
                                      name="",
                                      points=kwargs.get("points", "all"),
                                      side=kwargs.get("side", "positive"))
            elif plot_type == "box":
                # TODO: Implement box plots
                raise NotImplementedError("Box plots are not supported yet.")
            else:
                raise NotImplementedError(f"Cannot draw distribution grid with Plot type {plot_type}")
            fig.add_trace(
                row=row_num + 1,
                col=col_num + 1,
                trace=new_trace,
            )
    fig.update_layout(
        title_text=kwargs.get("title", "Distributions"),
        showlegend=False
    )
    return fig