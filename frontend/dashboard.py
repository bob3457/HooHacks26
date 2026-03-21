import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="AgriSignal Pro", page_icon="🌾", layout="wide")

# --- 2. HEADER & STYLING ---
st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; color: #E85D04;}
    .alert-box { padding: 20px; background-color: #ffcccc; border-radius: 10px; color: #cc0000; font-weight:bold;}
    .success-box { padding: 20px; background-color: #ccffcc; border-radius: 10px; color: #006600; font-weight:bold;}
    </style>
""", unsafe_allow_html=True)

st.title("🌾 AgriSignal Pro: Risk Mitigation Engine")
st.markdown("Automated Farm Loan Portfolio Monitoring & Proactive Hedging")
st.divider()

# --- 3. SYNTHETIC DATA VISUALIZATION (For the Judges) ---
# We load the dummy data you made earlier to show a "Portfolio"
@st.cache_data
def load_data():
    try:
        return pd.read_csv('data/agriculture-and-farming-dataset/synthetic_farm_borrowers.csv')
    except:
        return pd.DataFrame()

df = load_data()

if not df.empty:
    st.subheader("📊 Live Portfolio Overview")
    col1, col2, col3 = st.columns(3)
    
    # KPIs
    with col1:
        st.metric(label="Total Borrowers", value=f"{len(df):,}")
    with col2:
        high_risk = len(df[df['Requires_Intervention'] == 1])
        st.metric(label="Flagged for Intervention", value=f"{high_risk:,}", delta=f"{high_risk} High Risk", delta_color="inverse")
    with col3:
        st.metric(label="Average LTV", value=f"{df['Current_LTV_Ratio'].mean()*100:.1f}%")

    # Simple Charts
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        fig1 = px.histogram(df, x="Crop_Type", color="Requires_Intervention", 
                            title="Risk Distribution by Crop Type", barmode='group')
        st.plotly_chart(fig1, use_container_width=True)
    
    with chart_col2:
        fig2 = px.scatter(df, x="Farm_Area_Acres", y="Current_LTV_Ratio", color="Requires_Intervention",
                          title="LTV vs. Acreage (Red = High Risk)")
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

# --- 4. THE LOAN OFFICER TOOL (Where your ML model shines) ---
st.subheader("🔍 Run Individual Farm Risk Assessment")
st.markdown("Input a borrower's specific metrics to run them through our predictive fertilizer-stress model.")

# Create the form for input
with st.form("risk_form"):
    input_col1, input_col2 = st.columns(2)
    
    with input_col1:
        crop_type = st.selectbox("Crop Type", ["Maize", "Wheat", "Cotton", "Soybean", "Tomato"])
        farm_acres = st.number_input("Farm Acreage", min_value=10.0, max_value=5000.0, value=250.0)
        irrigation = st.selectbox("Irrigation Type", ["Sprinkler", "Drip", "Flood", "Rain-fed"])
        soil = st.selectbox("Soil Type", ["Loamy", "Clay", "Sandy", "Silty"])
        
    with input_col2:
        season = st.selectbox("Season", ["Kharif", "Rabi", "Zaid"])
        fert_tons = st.number_input("Est. Fertilizer Need (Tons)", value=45.0)
        ltv = st.slider("Current Loan-to-Value (LTV) Ratio", 0.0, 1.0, 0.75)
        delinquency = st.number_input("Months Since Last Delinquency (-1 for never)", value=-1)
        
    submit_button = st.form_submit_button(label="Run Prediction Engine")

# --- 5. API CALL TO YOUR FASTAPI BACKEND ---
if submit_button:
    st.write("Analyzing macroeconomic data and borrower profile...")
    
    # This payload matches the schema we made for FastAPI
    payload = {
        "Crop_Type": crop_type,
        "Farm_Area_Acres": farm_acres,
        "Irrigation_Type": irrigation,
        "Soil_Type": soil,
        "Season": season,
        "Fertilizer_Used_Tons": fert_tons,
        "Current_LTV_Ratio": ltv,
        "Months_Since_Delinquency": delinquency
    }
    
    try:
        # We assume your FastAPI server is running on port 8000
        response = requests.post("http://127.0.0.1:8000/risk", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            
            # Display Results!
            res_col1, res_col2 = st.columns(2)
            
            with res_col1:
                st.markdown(f'<p class="big-font">Stress Probability: {result["stress_probability"] * 100:.1f}%</p>', unsafe_allow_html=True)
            
            with res_col2:
                if result['requires_intervention']:
                    st.markdown(f'<div class="alert-box">🚨 HIGH RISK DETECTED<br>Action Required: {result["recommended_action"]}</div>', unsafe_allow_html=True)
                    if st.button("Dispatch Intervention Offer (SMS)"):
                        st.toast("✅ SMS Offer sent to Borrower!", icon="📱")
                else:
                    st.markdown('<div class="success-box">✅ Account is Healthy. No intervention needed.</div>', unsafe_allow_html=True)
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            
    except requests.exceptions.ConnectionError:
        st.error("🚨 Could not connect to the API! Make sure your FastAPI backend (`uvicorn api.main:app`) is running!")