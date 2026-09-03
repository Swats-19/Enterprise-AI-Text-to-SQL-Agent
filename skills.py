# skills_ui.py

import time
import pandas as pd
import streamlit as st
import sqlparse
import os
from skills.orchestrator import run_agent

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Text-to-SQL - Skills Architecture",
    page_icon="🧠",
    layout="wide"
)

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #09090F, #12132A, #18143A); }
    .hero {
        background: linear-gradient(135deg, #7C3AED, #4F46E5, #2563EB);
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
    .approval-card {
        background: rgba(255,255,255,0.05);
        border: 2px solid rgba(124, 58, 237, 0.3);
        border-radius: 20px;
        padding: 24px;
        margin: 16px 0;
        box-shadow: 0 8px 32px rgba(79, 70, 229, 0.15);
    }
    .approval-card h3 {
        color: #A78BFA;
        margin-top: 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HERO
# ============================================================
st.markdown("""
<div class="hero">
    <h1>🤖 AI Text-to-SQL</h1>
    <p>Skills Architecture • LangGraph • PostgreSQL • Self-Healing</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("⚙️ Configuration")
    
    db_url = st.text_input(
        "Database URL",
        value=os.getenv("DATABASE_URL", ""),
        help="Connection string for your database"
    )
    
    st.divider()
    
    demo_mode = st.checkbox(
        "🎬 Demo Mode",
        value=False,
        help="Forces wrong SQL on first attempt to show self-healing"
    )
    
    st.divider()
    
    st.markdown("**💡 Example Questions**")
    examples = [
        "Show me the top 5 customers with the highest total spend",
        "Which product has been ordered the most times?",
        "What is the total revenue for November 2024?",
        "List all products out of stock",
    ]
    for ex in examples:
        if st.button(f"📌 {ex[:20]}...", key=f"ex_{ex[:10]}", use_container_width=True):
            st.session_state.question_input = ex
            st.rerun()

# ============================================================
# SUGGESTED QUERIES (main area)
# ============================================================
suggested_queries = [
    "Show me the top 5 customers with the highest total spend",
    "Which product has been ordered the most times?",
    "What is the total revenue for November 2024?",
    "List all products out of stock",
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
        "Ask a question about your data",
        placeholder="e.g., Show me all delivered orders with total > 1000",
        label_visibility="collapsed",
        key="question_input"
    )
with col_button:
    run = st.button("🚀 Generate", use_container_width=True)

# ============================================================
# SESSION STATE
# ============================================================
if "step" not in st.session_state:
    st.session_state.step = "input"  # "input" | "approval" | "results"
if "agent_state" not in st.session_state:
    st.session_state.agent_state = None
if "agent_result" not in st.session_state:
    st.session_state.agent_result = None
if "human_decision" not in st.session_state:
    st.session_state.human_decision = None
if "human_feedback_text" not in st.session_state:
    st.session_state.human_feedback_text = ""

# ============================================================
# NEW: LangGraph thread ID for checkpoint resume
# ============================================================
if "current_thread_id" not in st.session_state:
    st.session_state.current_thread_id = None

# ============================================================
# STEP 1: INPUT + GENERATE
# ============================================================
if run and st.session_state.step == "input":
    if not question.strip():
        st.warning("Please enter a question.")
        st.stop()
    
    # Reset state for new query
    st.session_state.step = "input"
    st.session_state.agent_state = None
    st.session_state.agent_result = None
    st.session_state.human_decision = None
    st.session_state.human_feedback_text = ""
    st.session_state.current_thread_id = None
    
    with st.spinner("🧠 Agent is thinking..."):
        try:
            result = run_agent(
                question=question,
                db_url=db_url,
                demo_mode=demo_mode,
                skip_human=False,
                resume=False
            )
            
            if result.get("status") == "needs_human_approval":
                st.session_state.agent_state = result.get("state")
                st.session_state.agent_result = result
                st.session_state.current_thread_id = result.get("thread_id")
                st.session_state.step = "approval"
                st.rerun()
            else:
                st.session_state.agent_result = result
                st.session_state.step = "results"
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# ============================================================
# STEP 2: HUMAN APPROVAL
# ============================================================
if st.session_state.step == "approval":
    result = st.session_state.agent_result
    sql = result.get("sql", "No SQL generated.")
    formatted_sql = sqlparse.format(sql, reindent=True, keyword_case='upper') if sql else "No SQL generated."
    
    st.divider()
    st.markdown("""
    <div class="approval-card">
        <h3>👤 Human Approval Required</h3>
        <p style="color: #9CA3AF;">Please review the SQL before execution.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.code(formatted_sql, language="sql")
    
    col1, col2 = st.columns([2, 3])
    
    with col1:
        st.markdown("**Approve or Reject**")
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("✅ Approve", use_container_width=True, type="primary"):
                st.session_state.human_decision = "approve"
                st.session_state.step = "input"
                with st.spinner("⏳ Executing..."):
                    result = run_agent(
                        question=question,
                        db_url=db_url,
                        demo_mode=demo_mode,
                        skip_human=False,
                        resume=True,
                        human_decision={"approved": True},
                        thread_id=st.session_state.current_thread_id
                    )
                    if result.get("status") == "needs_human_approval":
                        st.session_state.agent_state = result.get("state")
                        st.session_state.agent_result = result
                        st.session_state.current_thread_id = result.get("thread_id")
                        st.session_state.step = "approval"
                    else:
                        st.session_state.agent_result = result
                        st.session_state.step = "results"
                    st.rerun()
        
        with col_btn2:
            if st.button("❌ Reject", use_container_width=True):
                st.session_state.human_decision = "reject"
                st.session_state.step = "input"
                with st.spinner("🔄 Rejected. Regenerating..."):
                    result = run_agent(
                        question=question,
                        db_url=db_url,
                        demo_mode=demo_mode,
                        skip_human=False,
                        resume=True,
                        human_decision={"feedback": "User rejected the query. Please generate a different SQL."},
                        thread_id=st.session_state.current_thread_id
                    )
                    if result.get("status") == "needs_human_approval":
                        st.session_state.agent_state = result.get("state")
                        st.session_state.agent_result = result
                        st.session_state.current_thread_id = result.get("thread_id")
                        st.session_state.step = "approval"
                    else:
                        st.session_state.agent_result = result
                        st.session_state.step = "results"
                    st.rerun()
    
    with col2:
        st.markdown("**💬 Feedback (optional)**")
        feedback = st.text_input(
            "Enter feedback to improve the query",
            placeholder="e.g., LIMIT 5 instead of 100",
            key="feedback_input",
            label_visibility="collapsed"
        )
        if st.button("📤 Submit Feedback", use_container_width=True):
            if feedback:
                st.session_state.human_feedback_text = feedback
                st.session_state.human_decision = "feedback"
                st.session_state.step = "input"
                with st.spinner("🔄 Regenerating with feedback..."):
                    result = run_agent(
                        question=question,
                        db_url=db_url,
                        demo_mode=demo_mode,
                        skip_human=False,
                        resume=True,
                        human_decision={"feedback": feedback},
                        thread_id=st.session_state.current_thread_id
                    )
                    if result.get("status") == "needs_human_approval":
                        st.session_state.agent_state = result.get("state")
                        st.session_state.agent_result = result
                        st.session_state.current_thread_id = result.get("thread_id")
                        st.session_state.step = "approval"
                    else:
                        st.session_state.agent_result = result
                        st.session_state.step = "results"
                    st.rerun()
    
    st.stop()

# ============================================================
# STEP 3: RESULTS
# ============================================================
if st.session_state.step == "results":
    result = st.session_state.agent_result
    
    if not result:
        st.info("No results yet.")
        st.stop()
    
    if result.get("status") == "rejected":
        st.error("❌ Query rejected by human.")
        st.stop()
    
    if result.get("status") == "error" or result.get("error"):
        st.error(f"❌ Error: {result.get('error', 'Unknown error')}")
        st.stop()
    
    # ---- Display Results ----
    sql = result.get("sql")
    if sql:
        st.divider()
        
        # ---- Metrics ----
        metrics = result.get("metrics", {})
        attempts = result.get("attempts", {})
        
        # ------------------------------------------------------------
        # Calculate actual node executions from token metrics/state
        # ------------------------------------------------------------
        judge_attempts = attempts.get("judge", 0)
        human_attempts = attempts.get("human", 0)
        execution_attempts = attempts.get("execution", 0)
        
        # If backend counters represent retries only, successful workflows
        # still need to show the nodes that actually ran.
        if judge_attempts == 0 and (
            metrics.get("judge_input_tokens", 0) > 0
            or metrics.get("judge_output_tokens", 0) > 0
        ):
            judge_attempts = 1
        
        if human_attempts == 0 and result.get("human_approved") is not None:
            human_attempts = 1
        
        if execution_attempts == 0 and (
            metrics.get("execution_time", 0) > 0
            or result.get("status") == "success"
        ):
            execution_attempts = 1
        
        display_attempts = {
            "judge": judge_attempts,
            "human": human_attempts,
            "execution": execution_attempts
        }
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            total_tokens = (
                metrics.get("generator_input_tokens", 0) +
                metrics.get("generator_output_tokens", 0) +
                metrics.get("judge_input_tokens", 0) +
                metrics.get("judge_output_tokens", 0)
            )
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">📝 Total Tokens</div>
                <div class="metric-value">{total_tokens}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            total_time = metrics.get("total_time", 0)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">⚡ Total Time</div>
                <div class="metric-value">{total_time:.2f}s</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">🔄 Judge Attempts</div>
                <div class="metric-value">{judge_attempts}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            human_approved = result.get("human_approved")
            status_text = "✅ Approved" if human_approved else "⏳ Waiting"
            if human_approved is False:
                status_text = "❌ Rejected"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">👤 Human Status</div>
                <div class="metric-value" style="font-size: 20px;">{status_text}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            status = result.get("status", "unknown")
            emoji = "✅" if status == "success" else "🔄" if status == "pending" else "❌"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">📊 Status</div>
                <div class="metric-value" style="font-size: 20px;">{emoji} {status.replace('_', ' ').title()}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # ---- Tabs ----
        tab1, tab2, tab3 = st.tabs(["📊 Results", "💻 SQL", "📈 AI Stats"])
        
        with tab1:
            data = result.get("data")
            if data:
                columns = result.get("columns", [])
                if columns and len(columns) > 0:
                    df = pd.DataFrame(data, columns=columns)
                    st.dataframe(df, width="stretch", hide_index=True)
                    
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Download Results (CSV)",
                        data=csv,
                        file_name=f"query_results_{int(time.time())}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.json(data[:5])
            else:
                st.info("No data returned.")
        
        with tab2:
            formatted_sql = sqlparse.format(sql, reindent=True, keyword_case='upper') if sql else "No SQL generated."
            st.code(formatted_sql, language="sql")
            
            if result.get("judge_feedback"):
                st.caption(f"🧑‍⚖️ Judge Feedback: {result['judge_feedback']}")
            if result.get("human_feedback"):
                st.caption(f"👤 Human Feedback: {result['human_feedback']}")
        
        with tab3:
            st.markdown("#### 🔄 Attempts")
            st.json(display_attempts)
            st.markdown("#### 📊 Detailed Metrics")
            st.json(metrics)
            st.markdown("#### 📋 Full Result")
            st.json({k: v for k, v in result.items() if k not in ['sql', 'data']})

# ============================================================
# FOOTER
# ============================================================
st.markdown("""
<div class="footer">
    Built with ❤️ using LangGraph • FastAPI • Streamlit • Gemini • PostgreSQL
</div>
""", unsafe_allow_html=True)