import streamlit as st
import pandas as pd
import joblib
import plotly.express as px

# --- 1. CONFIGURATION & MODEL LOADING ---
st.set_page_config(page_title="AgriSignal Pro", page_icon="🌾", layout="wide")

# @st.cache_resource ensures the model only loads once into memory, keeping the app lightning fast
@st.cache_resource
def load_ml_model():
    try:
        return joblib.load('data/models/farm_risk_model.joblib')
    except Exception as e:
        st.error(f"🚨 Model not found! Ensure 'farm_risk_model.joblib' is in data/models/. Error: {e}")
        return None

model = load_ml_model()

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

# --- 3. SYNTHETIC DATA VISUALIZATION ---
@st.cache_data
def load_portfolio_data():
    try:
        return pd.read_csv('data/agriculture-and-farming-dataset/synthetic_farm_borrowers.csv')
    except:
        return pd.DataFrame()

df = load_portfolio_data()

if not df.empty:
    st.subheader("📊 Live Portfolio Overview")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="Total Borrowers", value=f"{len(df):,}")
    with col2:
        high_risk = len(df[df['Requires_Intervention'] == 1])
        st.metric(label="Flagged for Intervention", value=f"{high_risk:,}", delta=f"{high_risk} High Risk", delta_color="inverse")
    with col3:
        st.metric(label="Average LTV", value=f"{df['Current_LTV_Ratio'].mean()*100:.1f}%")

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

# --- 4. THE ML PREDICTION ENGINE ---
st.subheader("🔍 Run Individual Farm Risk Assessment")

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

# --- 5. EXECUTE THE JOBLIB MODEL ---
if submit_button:
    if model is None:
        st.error("Cannot run prediction: Model failed to load.")
    else:
        st.write("Analyzing macroeconomic data and borrower profile...")
        
        # 1. Format the UI inputs into a Pandas DataFrame exactly like the training data
        input_df = pd.DataFrame([{
            'Crop_Type': crop_type,
            'Farm_Area_Acres': farm_acres,
            'Irrigation_Type': irrigation,
            'Soil_Type': soil,
            'Season': season,
            'Fertilizer_Used_Tons': fert_tons,
            'Current_LTV_Ratio': ltv,
            'Months_Since_Delinquency': delinquency
        }])
        
        # 2. Feed it directly to the model!
        # [:, 1] gets the probability of the "1" class (Requires Intervention)
        stress_probability = model.predict_proba(input_df)[0][1]
        is_high_risk = stress_probability > 0.65
        
        # 3. Display Results
        res_col1, res_col2 = st.columns(2)
        
        with res_col1:
            st.markdown(f'<p class="big-font">Stress Probability: {stress_probability * 100:.1f}%</p>', unsafe_allow_html=True)
        
        with res_col2:
            if is_high_risk:
                st.markdown('<div class="alert-box">🚨 HIGH RISK DETECTED<br>Action Required: Offer 60-day interest-only period.</div>', unsafe_allow_html=True)
                if st.button("Dispatch Intervention Offer (SMS)"):
                    st.toast("✅ SMS Offer sent to Borrower!", icon="📱")
            else:
                st.markdown('<div class="success-box">✅ Account is Healthy. No intervention needed.</div>', unsafe_allow_html=True)