"""Health-equity choropleth over a grid of SYNTHETIC service areas.

There are no real geographic boundary files or demographic data behind this
map -- see equity/generate_equity_data.py. The point is to demonstrate a
working geopandas + folium choropleth pipeline, not to describe any real
place or population.
"""

from __future__ import annotations

import sys
from pathlib import Path

import folium
import geopandas as gpd
import streamlit as st
from streamlit.components.v1 import html as st_html

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from equity.generate_equity_data import generate_regions  # noqa: E402

st.set_page_config(page_title="Health Equity | HealthBridge", layout="wide")
st.title("Health Equity View")
st.warning(
    "**Synthetic data.** The regions on this map are a fabricated 5x5 grid, not real "
    "ZIP codes or census areas, and the metrics are randomly generated -- see "
    "equity/generate_equity_data.py.",
    icon="⚠️",
)

METRIC_OPTIONS = {
    "Deprivation index (1-10, higher = more deprived)": "deprivation_index",
    "Diabetes prevalence (%)": "diabetes_prevalence_pct",
    "Life expectancy (years)": "life_expectancy_years",
    "Population": "population",
}


@st.cache_data(show_spinner=False)
def load_regions() -> gpd.GeoDataFrame:
    return generate_regions()


regions = load_regions()

metric_label = st.selectbox("Metric", list(METRIC_OPTIONS.keys()))
metric_col = METRIC_OPTIONS[metric_label]

total_bounds = regions.total_bounds  # [minx, miny, maxx, maxy]
center = [(total_bounds[1] + total_bounds[3]) / 2, (total_bounds[0] + total_bounds[2]) / 2]
fmap = folium.Map(location=center, zoom_start=10, tiles="cartodbpositron")

folium.Choropleth(
    geo_data=regions.__geo_interface__,
    data=regions,
    columns=["region_id", metric_col],
    key_on="feature.properties.region_id",
    fill_color="YlOrRd",
    fill_opacity=0.75,
    line_opacity=0.4,
    legend_name=metric_label,
).add_to(fmap)

folium.GeoJson(
    regions.__geo_interface__,
    style_function=lambda _: {"fillOpacity": 0, "weight": 0},
    tooltip=folium.GeoJsonTooltip(
        fields=["region_id", "deprivation_index", "diabetes_prevalence_pct", "life_expectancy_years", "population"],
        aliases=["Region", "Deprivation index", "Diabetes prevalence (%)", "Life expectancy (yrs)", "Population"],
    ),
).add_to(fmap)

st_html(fmap._repr_html_(), height=550)

with st.expander("Underlying synthetic data"):
    st.dataframe(regions.drop(columns="geometry"), use_container_width=True)
