"""Shared OMOP CDM database connection for the Streamlit analytics app."""

from __future__ import annotations

import os

import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

OMOP_DB_URL = os.environ.get("OMOP_DB_URL", "postgresql://omop:omop@localhost:5434/omop")


@st.cache_resource
def get_engine() -> Engine:
    return create_engine(OMOP_DB_URL, pool_pre_ping=True)
