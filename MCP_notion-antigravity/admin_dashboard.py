import streamlit as st
import sqlite3
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go

# Set page config for maximum space and clean layout
st.set_page_config(page_title="X Growth Admin", page_icon="📈", layout="wide")

st.markdown('''
    <style>
    /* Add some visual polish */
    .stMetric {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #ff4b4b;
    }
    </style>
''', unsafe_allow_html=True)

# Database connection
DB_PATH = os.path.join("data", "analytics.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def fetch_data(query):
    conn = get_connection()
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

st.title("🚀 X Growth Engine - Executive Dashboard")
st.markdown("Monitor pipeline performance, viral scores, and AI content trends in real-time.")

try:
    posts_df = fetch_data("SELECT * FROM post_history ORDER BY generated_at DESC")
    trends_df = fetch_data("SELECT * FROM trend_analytics ORDER BY timestamp DESC")

    if not posts_df.empty:
        posts_df["generated_at"] = pd.to_datetime(posts_df["generated_at"])
        
        # Calculate periods for metrics comparison
        now = pd.Timestamp.now()
        last_7_days = posts_df[posts_df["generated_at"] >= (now - pd.Timedelta(days=7))]
        prev_7_days = posts_df[(posts_df["generated_at"] >= (now - pd.Timedelta(days=14))) & (posts_df["generated_at"] < (now - pd.Timedelta(days=7)))]

        # Current metrics
        total_posts = len(last_7_days)
        avg_score = round(last_7_days["viral_score"].mean(), 1) if not last_7_days.empty else 0
        published_posts = len(last_7_days[last_7_days["status"] == "published"])
        
        # Previous metrics for delta
        prev_total = len(prev_7_days)
        prev_score = round(prev_7_days["viral_score"].mean(), 1) if not prev_7_days.empty else 0
        prev_pub = len(prev_7_days[prev_7_days["status"] == "published"])
        
        def calculate_delta(curr, prev):
            if prev == 0: return 0
            return ((curr - prev) / prev) * 100

        # --- Key Metrics (Cards) ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Generated (7d)", f"{total_posts}", f"{calculate_delta(total_posts, prev_total):.1f}%")
        col2.metric("Avg Viral Score (7d)", f"{avg_score} / 100", f"{avg_score - prev_score:.1f} pts")
        col3.metric("Successfully Published (7d)", f"{published_posts}", f"{calculate_delta(published_posts, prev_pub):.1f}%")
        col4.metric("Engine Health", "Optimal", "")

        st.divider()

        # --- Interactive Charts (Plotly) ---
        colA, colB = st.columns(2)

        with colA:
            st.subheader("Viral Score Distribution")
            chart_data = posts_df[["generated_at", "viral_score"]].copy()
            chart_data = chart_data.sort_values(by="generated_at")
            
            fig1 = px.line(chart_data, x="generated_at", y="viral_score", 
                          line_shape='spline', markers=True, 
                          color_discrete_sequence=["#ff4b4b"],
                          labels={"generated_at": "Date", "viral_score": "Score"})
            fig1.update_layout(height=350, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig1, use_container_width=True)

        with colB:
            if not trends_df.empty:
                st.subheader("Recent Keyword Trends")
                top_trends = trends_df.head(8)[["keyword", "viral_potential", "search_volume"]]
                fig2 = px.bar(top_trends, x="viral_potential", y="keyword", orientation='h',
                             color="viral_potential", color_continuous_scale="Reds",
                             labels={"viral_potential": "Viral Potential", "keyword": ""})
                fig2.update_layout(height=350, yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.write("No trend recording found.")
                
        # --- System Alerts Panel ---
        st.subheader("System Alerts & Notifications")
        if avg_score < 50 and not last_7_days.empty:
            st.error("🔴 Warning: Average Viral Score in the last 7 days dropped below 50. Review x_growth_prompt.md styling.")
        elif published_posts == 0 and not last_7_days.empty:
            st.warning("🟡 Alert: Content is being generated but 0 posts published. Check API credentials or approval loops.")
        else:
            st.success("🟢 All systems nominal. Growth trajectory stable.")

        st.divider()

        # --- Content Log Table ---
        st.subheader("📝 Recent Content Log")
        log_view = posts_df[["generated_at", "post_type", "keyword", "viral_score", "status", "hook"]]
        
        # Style dataframe for streamlit
        def highlight_status(val):
            color = 'lightgreen' if val == 'published' else 'lightgray'
            return f'color: {color}'
            
        st.dataframe(log_view.head(20).style.map(highlight_status, subset=['status']), 
                     use_container_width=True, hide_index=True)

    else:
        st.info("No content generated yet. Awaiting first scheduled run.")

except Exception as e:
    st.error(f"Failed to load dashboard data. Is the database initialized? Error: {e}")

st.sidebar.markdown("### Control Panel")
if st.sidebar.button("↻ Refresh Data"):
    st.rerun()

st.sidebar.write("---")
st.sidebar.info("Executive Dashboard powered by Streamlit and Plotly. Apply 'kpi-dashboard-design' principles.")

