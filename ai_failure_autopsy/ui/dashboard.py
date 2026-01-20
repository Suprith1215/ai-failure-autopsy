import streamlit as st
import json
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import time
import random
import requests
import smtplib
from email.message import EmailMessage
from fpdf import FPDF

# ================= BASIC CONFIG =================
st.set_page_config(
    page_title="AI Failure Autopsy Dashboard",
    layout="wide"
)

DATA_DIR = Path("data/classifications")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ================= SEVERITY =================
SEVERITY_SCORE_MAP = {
    "Hallucination": 5,
    "Data Drift": 4,
    "Retrieval Failure": 3,
    "Prompt Design Failure": 2,
    "Tool Misuse": 1
}

# ================= AUTH (UNCHANGED) =================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None

if not st.session_state.authenticated:
    st.markdown("## 🔒 Enterprise Login")
    provider = st.selectbox("SSO Provider", ["Google Workspace", "Azure AD", "Okta"])
    role = st.selectbox("Role", ["Viewer", "Engineer", "Admin"])

    if st.button("Login"):
        st.session_state.authenticated = True
        st.session_state.role = role
        st.rerun()   # ✅ FIXED

    st.stop()


role = st.session_state.role

# ================= LOAD DATA =================
records = []
for file in DATA_DIR.glob("*.json"):
    with open(file, encoding="utf-8") as f:
        obj = json.load(f)
        obj["timestamp"] = obj.get("timestamp", file.stat().st_mtime)
        obj["model"] = obj.get("model", "CustomerSupportBot-v1")
        records.append(obj)

df = pd.DataFrame(records)

if df.empty:
    df = pd.DataFrame(columns=[
        "incident_id", "failure_type", "severity_score",
        "confidence", "recommended_fix", "timestamp", "model"
    ])

df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")

# ================= HEADER =================
st.markdown("## 🛡️ AI Failure Autopsy Dashboard")
st.caption("Enterprise AI Reliability • Monitoring • Self-Healing")
st.markdown("---")

# ================= EXEC SUMMARY =================
st.markdown("### 📊 Executive Summary")

total = len(df)
avg_severity = round(df["severity_score"].mean(), 2) if total else 0
high_risk = (df["severity_score"] >= 4).sum()

grade = (
    "A" if avg_severity < 2 else
    "B" if avg_severity < 3 else
    "C" if avg_severity < 4 else
    "D"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Incidents", total)
c2.metric("High Severity", high_risk)
c3.metric("Avg Severity", avg_severity)
c4.metric("Reliability Grade", grade)

# ================= 🔔 ALERTS (NEW) =================
st.markdown("---")
st.markdown("### 🔔 Live Alerts")

enable_alerts = st.checkbox("Enable alerts for High severity incidents")

SLACK_WEBHOOK = st.text_input(
    "Slack Webhook URL",
    type="password",
    help="Optional — paste Slack Incoming Webhook"
)

EMAIL_TO = st.text_input(
    "Email Alert Receiver",
    help="Optional — example: sre@company.com"
)

def send_slack_alert(message):
    if SLACK_WEBHOOK:
        requests.post(SLACK_WEBHOOK, json={"text": message})

def send_email_alert(message):
    if EMAIL_TO:
        email = EmailMessage()
        email.set_content(message)
        email["Subject"] = "🚨 AI Reliability Alert"
        email["From"] = "ai-monitor@company.com"
        email["To"] = EMAIL_TO

        try:
            with smtplib.SMTP("localhost") as server:
                server.send_message(email)
        except Exception:
            pass  # safe fail for local dev

if enable_alerts and high_risk > 0:
    alert_msg = f"🚨 {high_risk} high-severity AI failures detected."
    send_slack_alert(alert_msg)
    send_email_alert(alert_msg)
    st.warning("Alerts sent")

# ================= MODEL METRICS =================
st.markdown("---")
st.markdown("### 📈 Model Reliability Metrics")

model_stats = (
    df.groupby("model")
      .agg(
          incidents=("incident_id", "count"),
          avg_severity=("severity_score", "mean"),
          avg_confidence=("confidence", "mean")
      )
      .reset_index()
)

model_stats["reliability_score"] = (100 - model_stats["avg_severity"] * 15).clip(0, 100)
st.dataframe(model_stats, use_container_width=True)

# ================= DISTRIBUTION =================
st.markdown("---")
st.markdown("### 📊 Failure Distribution")

left, right = st.columns([1.3, 1])

with left:
    st.dataframe(
        df[["incident_id", "model", "failure_type", "severity_score", "confidence"]],
        use_container_width=True
    )

with right:
    if total:
        fig, ax = plt.subplots()
        df["failure_type"].value_counts().plot.pie(autopct="%1.1f%%", ax=ax)
        ax.set_ylabel("")
        st.pyplot(fig)

# ================= TIMELINE =================
st.markdown("---")
st.markdown("### 📈 Reliability Drift Timeline")

if total:
    trend = (
        df.sort_values("timestamp")
          .groupby(df["timestamp"].dt.date)["severity_score"]
          .mean()
    )

    fig, ax = plt.subplots()
    trend.plot(marker="o", linewidth=2, ax=ax)
    ax.set_ylabel("Avg Severity (1–5)")
    ax.grid(alpha=0.3)
    st.pyplot(fig)

# ================= 🧠 LLM ROOT CAUSE ANALYSIS (NEW) =================
st.markdown("---")
st.markdown("### 🧠 AI Root Cause Analysis")

st.caption("LLM-generated failure reasoning and prevention insights")

def llm_root_cause(failure_type, description):
    return f"""
Root Cause Analysis:
The failure was caused by **{failure_type}**, likely due to insufficient grounding,
missing validation, or stale internal representations.

Primary contributing factors:
- Weak retrieval validation
- Missing guardrails
- Insufficient monitoring feedback loops

Recommended long-term fix:
Introduce continuous validation, automated regression checks,
and runtime reliability scoring.
""".strip()

for _, row in df.sort_values("severity_score", ascending=False).iterrows():
    with st.expander(f"🔍 {row['incident_id']} • RCA"):
        st.markdown(
            llm_root_cause(
                row["failure_type"],
                row.get("recommended_fix", "")
            )
        )

# ================= PDF REPORT =================
st.markdown("---")
st.markdown("### 📄 Export Executive PDF Report")

if st.button("Generate PDF Report"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(0, 10, "AI Reliability Executive Report", ln=True)
    pdf.ln(4)
    pdf.cell(0, 10, f"Total Incidents: {total}", ln=True)
    pdf.cell(0, 10, f"High Severity: {high_risk}", ln=True)
    pdf.cell(0, 10, f"Avg Severity: {avg_severity}", ln=True)
    pdf.cell(0, 10, f"Reliability Grade: {grade}", ln=True)

    path = "ai_reliability_report.pdf"
    pdf.output(path)

    with open(path, "rb") as f:
        st.download_button("Download PDF", f, file_name="AI_Reliability_Report.pdf")

# ================= SIMULATION =================
if role in ["Engineer", "Admin"]:
    st.markdown("---")
    st.markdown("### 🧪 Incident Simulation")

    sim_type = st.selectbox("Failure Type", list(SEVERITY_SCORE_MAP.keys()))
    sim_model = st.text_input("Model Name", "CustomerSupportBot-v1")

    if st.button("Inject Incident"):
        new_id = f"sim_{int(time.time())}"
        obj = {
            "incident_id": new_id,
            "failure_type": sim_type,
            "severity_score": SEVERITY_SCORE_MAP[sim_type],
            "confidence": round(random.uniform(0.6, 1.0), 2),
            "recommended_fix": "Auto-generated mitigation plan",
            "model": sim_model,
            "timestamp": datetime.now().timestamp()
        }
        (DATA_DIR / f"{new_id}.json").write_text(json.dumps(obj, indent=2))
        st.success("Incident injected")

# ================= FOOTER =================
st.markdown(
    "<div style='text-align:center; opacity:0.5; margin-top:40px;'>"
    "Enterprise AI Reliability Platform • Internal Use Only"
    "</div>",
    unsafe_allow_html=True
)
