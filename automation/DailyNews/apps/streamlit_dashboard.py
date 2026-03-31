from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from antigravity_mcp.config import get_settings


def _has_text(value: object) -> bool:
    return bool(str(value or "").strip())


def _report_delivery_state(row: pd.Series) -> str:
    """Prefer an explicit delivery label over the overloaded stored status field."""
    if _has_text(row.get("notion_page_id", "")):
        return "notion_synced"
    raw_status = str(row.get("status", "draft") or "draft").strip()
    return raw_status or "draft"


def _fetch_dataframe(db_path: Path, query: str) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(db_path) as connection:
            return pd.read_sql_query(query, connection)
    except Exception:
        return pd.DataFrame()


def _metric_card(title: str, value: str, caption: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-title">{title}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-caption">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    settings = get_settings()
    st.set_page_config(page_title="Antigravity Content Engine", page_icon="AG", layout="wide")
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
        html, body, [class*="css"] {
          font-family: "IBM Plex Sans", sans-serif;
        }
        .stApp {
          background:
            radial-gradient(circle at top left, rgba(243, 118, 54, 0.18), transparent 28%),
            radial-gradient(circle at top right, rgba(28, 96, 144, 0.14), transparent 26%),
            linear-gradient(180deg, #f6f3ee 0%, #f1eee9 100%);
        }
        .metric-card {
          background: rgba(255, 255, 255, 0.82);
          border: 1px solid rgba(0, 0, 0, 0.08);
          border-radius: 18px;
          padding: 18px 20px;
          box-shadow: 0 12px 32px rgba(23, 29, 35, 0.08);
          min-height: 132px;
        }
        .metric-title {
          font-size: 0.82rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: #8b5b34;
          margin-bottom: 12px;
        }
        .metric-value {
          font-size: 2rem;
          font-weight: 700;
          color: #13263a;
          margin-bottom: 8px;
        }
        .metric-caption {
          color: #576575;
          font-size: 0.92rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Antigravity Content Engine")
    st.caption("Operational cockpit for briefs, approvals, MCP runs, and publishing health.")

    runs_df = _fetch_dataframe(settings.pipeline_state_db, "SELECT * FROM job_runs ORDER BY started_at DESC LIMIT 50")
    reports_df = _fetch_dataframe(
        settings.pipeline_state_db, "SELECT * FROM content_reports ORDER BY updated_at DESC LIMIT 50"
    )
    analytics_df = _fetch_dataframe(
        settings.analytics_db, "SELECT * FROM post_history ORDER BY generated_at DESC LIMIT 50"
    )
    if not reports_df.empty:
        reports_df = reports_df.copy()
        reports_df["delivery_state"] = reports_df.apply(_report_delivery_state, axis=1)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _metric_card("Tracked Runs", str(len(runs_df.index)), "Recent pipeline executions stored locally.")
    with col2:
        local_draft_reports = 0 if reports_df.empty else int((reports_df["delivery_state"] == "draft").sum())
        _metric_card("Local Draft Reports", str(local_draft_reports), "Reports stored locally and not yet synced to Notion.")
    with col3:
        notion_synced_reports = (
            0 if reports_df.empty else int((reports_df["delivery_state"] == "notion_synced").sum())
        )
        _metric_card("Notion-Synced Reports", str(notion_synced_reports), "Reports mirrored to Notion.")
    with col4:
        published_posts = (
            0
            if analytics_df.empty or "status" not in analytics_df
            else int((analytics_df["status"] == "published").sum())
        )
        _metric_card("Channel Deliveries", str(published_posts), "Cross-channel outputs recorded in analytics.")

    chart_left, chart_right = st.columns([1.2, 1])

    with chart_left:
        st.subheader("Pipeline Status Timeline")
        if runs_df.empty:
            st.info("No pipeline runs recorded yet.")
        else:
            chart_df = runs_df.copy()
            chart_df["started_at"] = pd.to_datetime(chart_df["started_at"])
            fig = px.scatter(
                chart_df,
                x="started_at",
                y="job_name",
                color="status",
                size="processed_count",
                color_discrete_map={
                    "success": "#1f6f50",
                    "partial": "#c7841d",
                    "failed": "#b8402a",
                    "running": "#1c6090",
                    "skipped": "#6b7280",
                },
                labels={"started_at": "Started", "job_name": "Job"},
            )
            fig.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    with chart_right:
        st.subheader("Report Status Mix")
        if reports_df.empty:
            st.info("No content reports stored yet.")
        else:
            pie_df = reports_df.groupby("delivery_state").size().reset_index(name="count")
            fig = px.pie(
                pie_df,
                names="delivery_state",
                values="count",
                color="delivery_state",
                color_discrete_map={
                    "draft": "#d98c2b",
                    "notion_synced": "#1f6f50",
                    "failed": "#b8402a",
                },
                hole=0.56,
            )
            fig.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Recent Reports")
    if reports_df.empty:
        st.write("No reports available.")
    else:
        view_columns = [
            column
            for column in ["report_id", "category", "window_name", "delivery_state", "approval_state", "updated_at"]
            if column in reports_df.columns
        ]
        st.dataframe(reports_df[view_columns], use_container_width=True, hide_index=True)

    st.subheader("Recent Runs")
    if runs_df.empty:
        st.write("No run history available.")
    else:
        view_columns = [
            column
            for column in [
                "run_id",
                "job_name",
                "status",
                "processed_count",
                "published_count",
                "started_at",
                "finished_at",
                "error_text",
            ]
            if column in runs_df.columns
        ]
        st.dataframe(runs_df[view_columns], use_container_width=True, hide_index=True)
