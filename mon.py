import time
import pandas as pd
import streamlit as st

from text_to_sql import generate_sql
from execute import execute_sql

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Text-to-SQL",
    page_icon="🤖",
    layout="wide"
)

# ============================================================
# CUSTOM CSS (keep your existing – abbreviated here)
# ============================================================
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #09090F, #12132A, #18143A); }
    .hero {
        background: linear-gradient(135deg, #4F46E5, #7C3AED, #2563EB);
        padding: 28px 32px;
        border-radius: 20px;
        color: white;
        box-shadow: 0 12px 40px rgba(79, 70, 229, 0.35);
        margin-bottom: 28px;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .hero h1 { margin: 0; font-size: 42px; font-weight: 700; }
    .hero p { margin: 8px 0 0 0; font-size: 17px; opacity: 0.85; }
    .metric-card {
        background: rgba(255,255,255,0.04);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 16px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.3s ease;
        height: 100%;
    }
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: rgba(124, 58, 237, 0.5);
        box-shadow: 0 8px 30px rgba(79, 70, 229, 0.25);
    }
    .metric-title { color: #9CA3AF; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500; }
    .metric-value { font-size: 28px; color: white; font-weight: 700; margin-top: 4px; }
    .stTextInput > div > div > input {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 14px !important;
        color: white !important;
        font-size: 16px !important;
        padding: 14px 18px !important;
        height: 56px !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #7C3AED !important;
        box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.2) !important;
    }
    .stButton > button {
        width: 100%;
        height: 56px;
        border-radius: 14px !important;
        border: none !important;
        background: linear-gradient(135deg, #7C3AED, #4F46E5) !important;
        color: white !important;
        font-size: 17px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 20px rgba(79, 70, 229, 0.3) !important;
    }
    .stButton > button:hover {
        transform: scale(1.02) !important;
        box-shadow: 0 8px 30px rgba(79, 70, 229, 0.5) !important;
    }
    .stButton > button[key^="suggest_"] {
        height: auto !important;
        min-height: 38px !important;
        padding: 8px 14px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 30px !important;
        color: #D1D5DB !important;
        box-shadow: none !important;
        white-space: normal !important;
    }
    .stButton > button[key^="suggest_"]:hover {
        background: rgba(124, 58, 237, 0.15) !important;
        border-color: #7C3AED !important;
        color: white !important;
        transform: translateY(-2px);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
        padding-bottom: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        color: #9CA3AF !important;
        border-radius: 10px !important;
        padding: 8px 20px !important;
        font-weight: 500 !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(124, 58, 237, 0.15) !important;
        color: #A78BFA !important;
        border-bottom: 2px solid #7C3AED !important;
    }
    .stCodeBlock {
        background: rgba(0,0,0,0.4) !important;
        border-radius: 14px !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        padding: 4px !important;
    }
    .stDataFrame {
        border-radius: 14px !important;
        overflow: hidden !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
    }
    hr { border-color: rgba(255,255,255,0.06) !important; margin: 24px 0 !important; }
    .footer {
        text-align: center;
        color: #4B5563;
        font-size: 13px;
        padding-top: 20px;
        border-top: 1px solid rgba(255,255,255,0.04);
        margin-top: 30px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HERO
# ============================================================
st.markdown("""
<div class="hero">
    <h1>🤖 Enterprise AI Text-to-SQL</h1>
    <p>Monolithic Architecture • SQLite • Gemini 2.0 Flash</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SUGGESTED QUERIES
# ============================================================
suggested_queries = [
    "Show me the top 5 customers with the highest total spend",
    "Which product has been ordered the most times?",
    "What is the total revenue for November 2024?",
    "List all products out of stock",
    "Show me customers who have never placed an order"
]

st.markdown("**💡 Try these:**")
cols = st.columns(len(suggested_queries))
for idx, (col, query) in enumerate(zip(cols, suggested_queries)):
    with col:
        display_text = query[:22] + "..." if len(query) > 22 else query
        if st.button(
            f"📌 {display_text}",
            key=f"suggest_{idx}",
            use_container_width=True,
            help=query
        ):
            st.session_state.question_input = query
            st.rerun()

st.divider()

# ============================================================
# USER INPUT
# ============================================================
col_input, col_button = st.columns([5, 1])
with col_input:
    question = st.text_input(
        "Ask a question about your e-commerce data",
        placeholder="e.g., Show me all delivered orders with total > 1000",
        label_visibility="collapsed",
        key="question_input"
    )
with col_button:
    run = st.button("🚀 Generate", use_container_width=True)

# ============================================================
# MAIN LOGIC
# ============================================================
if run:
    if not question.strip():
        st.warning("Please enter a question.")
        st.stop()

    try:
        with st.spinner("🤖 Thinking..."):
            # LLM time
            llm_start = time.time()
            result = generate_sql(question)  # ← CHANGED: handle both types
            # Support both old (string) and new (tuple) return types
            if isinstance(result, tuple):
                sql_query, usage = result
            else:
                sql_query = result
                usage = {}
            llm_time = round(time.time() - llm_start, 3)

            # Token usage (fallback to 0 if not available)
            input_tokens = usage.get("input_tokens", 0) if usage else 0
            output_tokens = usage.get("output_tokens", 0) if usage else 0
            total_tokens = usage.get("total_tokens", 0) if usage else 0

            # SQL execution time
            sql_start = time.time()
            columns, rows = execute_sql(sql_query)
            sql_time = round(time.time() - sql_start, 3)

        total_time = llm_time + sql_time

        # ============================================================
        # METRICS (5 columns)
        # ============================================================
        st.divider()
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.markdown("""
            <div class="metric-card">
                <div class="metric-title">🏗️ Architecture</div>
                <div class="metric-value">Monolithic</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">⚡ LLM Time</div>
                <div class="metric-value">{llm_time}s</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">🗄️ SQL Time</div>
                <div class="metric-value">{sql_time:.3f}s</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">📊 Rows</div>
                <div class="metric-value">{len(rows)}</div>
            </div>
            """, unsafe_allow_html=True)

        with col5:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">📝 Tokens</div>
                <div class="metric-value">{total_tokens}</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # ============================================================
        # TABS
        # ============================================================
        tab1, tab2, tab3 = st.tabs(["📊 Results", "💻 SQL", "📈 AI Stats"])

        with tab1:
            if len(rows) == 0:
                st.info("No records found.")
            else:
                df = pd.DataFrame(rows, columns=columns)
                st.dataframe(df, width="stretch", hide_index=True)

                csv = df.to_csv(index=False)
                st.download_button(
                    label="⬇️ Download Results (CSV)",
                    data=csv,
                    file_name=f"query_results_{int(time.time())}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

        with tab2:
            st.code(sql_query, language="sql")

        with tab3:
            st.info("📊 **Monolithic Architecture** – Single LLM call with full schema")
            st.markdown(f"""
            | Metric | Value |
            |--------|-------|
            | ⏱️ LLM Time | {llm_time}s |
            | 🗄️ SQL Execution Time | {sql_time:.3f}s |
            | ⚡ Total Time | {total_time:.3f}s |
            | 📥 Input Tokens | {input_tokens:,} |
            | 📤 Output Tokens | {output_tokens:,} |
            | 🔢 Total Tokens | {total_tokens:,} |
            | 📊 Rows Returned | {len(rows)} |
            | 🤖 Model | Gemini 2.0 Flash |
            | 🗄️ Database | SQLite |
            """)
            if not usage:
                st.caption("⚠️ Token tracking not enabled. Update `text_to_sql.py` to return usage metadata.")

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

# ============================================================
# FOOTER
# ============================================================
st.markdown("""
<div class="footer">
    Built with ❤️ using LangChain • FastAPI • Streamlit • Gemini
</div>
""", unsafe_allow_html=True)