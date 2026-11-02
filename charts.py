"""Consistent Plotly figures; calendar labels never depend on auto tick precision."""

import math
from datetime import date, datetime, time, timedelta

import plotly.graph_objects as go

BLUE = "#2563eb"
STATUS_COLORS = {
    "New": "#2563eb",
    "Contacted": "#0891b2",
    "Quoted": "#7c3aed",
    "Won": "#16a34a",
    "Lost": "#64748b",
}
URGENCY_COLORS = {"Low": "#94a3b8", "Normal": "#2563eb", "High": "#d97706", "Emergency": "#dc2626"}


def style_figure(fig, height=320):
    fig.update_layout(
        height=height,
        margin=dict(l=12, r=20, t=20, b=20),
        font=dict(size=13),
        showlegend=False,
        bargap=0.3,
        hoverlabel=dict(namelength=-1),
    )
    fig.update_xaxes(showgrid=False, automargin=True, fixedrange=False)
    fig.update_yaxes(rangemode="tozero", tickformat=",d", nticks=6, automargin=True)
    return fig


def category_figure(rows, field):
    labels = [r["Category"] for r in rows]
    counts = [r["Leads"] for r in rows]
    palette = STATUS_COLORS if field == "status" else URGENCY_COLORS if field == "urgency" else {}
    horizontal = field == "service"
    fig = go.Figure(
        go.Bar(
            x=counts if horizontal else labels,
            y=labels if horizontal else counts,
            orientation="h" if horizontal else "v",
            text=counts,
            textposition="outside",
            cliponaxis=False,
            marker_color=[palette.get(label, BLUE) for label in labels],
            hovertemplate=("%{y}: %{x} leads" if horizontal else "%{x}: %{y} leads")
            + "<extra></extra>",
        )
    )
    style_figure(fig, 350 if horizontal else 320)
    if horizontal:
        fig.update_yaxes(
            type="category",
            autorange="reversed",
            tickformat=None,
            tickmode="array",
            tickvals=labels,
        )
        fig.update_xaxes(title="Leads", rangemode="tozero", tickformat=",d", nticks=6)
    else:
        fig.update_yaxes(title="Leads")
        fig.update_xaxes(type="category")
    count_axis = fig.update_xaxes if horizontal else fig.update_yaxes
    count_axis(dtick=max(1, math.ceil(max(counts, default=0) / 5)))
    return fig


def volume_figure(volume):
    """Date positions with explicit date-only tick text and full dates on hover."""
    fig = go.Figure()
    style_figure(fig)
    if not volume:
        fig.add_annotation(text="No dated inquiries available", showarrow=False)
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        return fig
    monthly = volume[0]["Interval"] == "Month"
    dates = [date.fromisoformat(row["Period"]) for row in volume]
    labels = [(d.strftime("%b %Y") if monthly else f"{d:%b} {d.day}") for d in dates]
    # Select at most eight readable calendar ticks; preserve both endpoints.
    step = max(1, math.ceil((len(dates) - 1) / 7))
    indices = list(range(0, len(dates), step))
    if indices[-1] != len(dates) - 1:
        indices.append(len(dates) - 1)
    fig.add_bar(
        x=[d.isoformat() for d in dates],
        y=[row["Inquiries"] for row in volume],
        marker_color=BLUE,
        width=(20 if monthly else 0.72) * 86400000,
        hovertemplate="%{x|%b %d, %Y}<br>%{y} inquiries<extra></extra>",
    )
    padding = timedelta(days=16 if monthly else 0.6)
    # datetime padding is important for a single day: avoid a microsecond-wide auto range.
    start = datetime.combine(dates[0], time.min) - padding
    end = datetime.combine(dates[-1], time.min) + padding
    fig.update_xaxes(
        type="date",
        tickmode="array",
        tickvals=[dates[i].isoformat() for i in indices],
        ticktext=[labels[i] for i in indices],
        tickformat="%b %d",
        range=[start.isoformat(), end.isoformat()],
        title="America/New_York",
        tickangle=0,
    )
    fig.update_yaxes(
        title="Inquiries", dtick=max(1, math.ceil(max(row["Inquiries"] for row in volume) / 5))
    )
    return fig
