import streamlit as st
import os
import subprocess
import sys

# ── Setup Logic ───────────────────────────────────────────────────────────
def run_script_with_stream(command, status_text):
    """Executes a script and streams its output to the Streamlit UI."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Use a container to display the logs
    log_container = st.empty()
    logs = []
    
    for line in iter(process.stdout.readline, ""):
        logs.append(line.strip())
        # Keep only the last 5 lines for brevity
        log_container.code("\n".join(logs[-5:]))
        
    process.stdout.close()
    return_code = process.wait()
    
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command, "\n".join(logs))


def run_backend_setup():
    """Run backend training and pipeline if data is missing."""
    _root = os.path.dirname(os.path.abspath(__file__))
    models_meta = os.path.join(_root, "data", "models", "model_metadata.json")
    farm_model = os.path.join(_root, "farm_risk_model.joblib")
    cache_json = os.path.join(_root, "data", "processed", "cache.json")
    
    # Check if we've already done this in this session to avoid double-runs
    if "setup_complete" in st.session_state and st.session_state.setup_complete:
        return

    # Check for missing data files
    needs_training = not os.path.exists(models_meta)
    needs_farm_model = not os.path.exists(farm_model)
    needs_pipeline = not os.path.exists(cache_json)

    if needs_training or needs_farm_model or needs_pipeline:
        st.markdown("""
        <div style="text-align:center; padding-top:4rem;">
          <h1>🌾 foreGASt</h1>
          <p>Initializing your agricultural fertilizer intelligence dashboard...</p>
        </div>
        """, unsafe_allow_html=True)

        if needs_training:
            with st.status("Training XGBoost price models...") as status:
                st.write("Reading historical data and training...")
                try:
                    run_script_with_stream([sys.executable, "backend/train_models.py"], "Training")
                    status.update(label="✅ Price models ready!", state="complete")
                except subprocess.CalledProcessError as e:
                    st.error(f"❌ Error training price models: {e.output}")
                    st.stop()

        if needs_farm_model:
            with st.status("Training farm risk classifier...") as status:
                try:
                    run_script_with_stream([sys.executable, "backend/training_and_eval.py"], "Risk Classifier")
                    status.update(label="✅ Risk model ready!", state="complete")
                except subprocess.CalledProcessError as e:
                    st.error(f"❌ Error training risk model: {e.output}")
                    st.stop()

        if needs_pipeline:
            with st.status("Generating fresh forecasts and buy signals...") as status:
                try:
                    run_script_with_stream([sys.executable, "backend/run_pipeline.py"], "Generating Pipeline")
                    status.update(label="✅ Data generated!", state="complete")
                except subprocess.CalledProcessError as e:
                    st.error(f"❌ Error running pipeline: {e.output}")
                    st.stop()
        
        st.success("Setup complete. Redirecting...")
    
    st.session_state.setup_complete = True


# ── Execution ──────────────────────────────────────────────────────────────
run_backend_setup()
st.switch_page("pages/login.py")
