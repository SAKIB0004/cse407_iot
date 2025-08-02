import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import tinytuya
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import os

# --------------- Device Setup ---------------
DEVICE_ID = "bf1fb51a6032098478au4s"
LOCAL_KEY = "ZD@.!(|l[$V|3K=F"
LOCAL_IP = "192.168.68.107"
VERSION = 3.5

unit_cost_bdt = 6
csv_path = "energy_history.csv"

# Tuya device setup
device = tinytuya.OutletDevice(DEVICE_ID, LOCAL_IP, LOCAL_KEY)
device.set_version(VERSION)

# Session state init
if 'history' not in st.session_state:
    if os.path.exists(csv_path):
        st.session_state.history = pd.read_csv(csv_path, parse_dates=['Time']).to_dict('records')
    else:
        st.session_state.history = []

if 'on_time' not in st.session_state:
    st.session_state.on_time = None

if 'duration_minutes' not in st.session_state:
    st.session_state.duration_minutes = 0

if 'last_update_time' not in st.session_state:
    st.session_state.last_update_time = datetime.now()

if 'accumulated_kwh' not in st.session_state:
    st.session_state.accumulated_kwh = 0.0

# Device status getter
def get_device_status():
    try:
        status = device.status()
        dps = status.get('dps', {})

        power_on = dps.get('1', False)
        power = dps.get('19', 0) / 10.0
        voltage = dps.get('20', 0) / 10.0
        current = dps.get('18', 0) / 1000.0

        current_time = datetime.now()
        delta_time_hours = (current_time - st.session_state.last_update_time).total_seconds() / 3600.0
        st.session_state.last_update_time = current_time

        incremental_kwh = (power / 1000.0) * delta_time_hours
        st.session_state.accumulated_kwh += incremental_kwh

        current_ma = current * 1000.0
        cost = st.session_state.accumulated_kwh * unit_cost_bdt

        if power_on:
            if not st.session_state.on_time:
                st.session_state.on_time = datetime.now()
            else:
                st.session_state.duration_minutes = int((datetime.now() - st.session_state.on_time).total_seconds() / 60)
        else:
            st.session_state.on_time = None
            st.session_state.duration_minutes = 0

        return power_on, power, voltage, current_ma, st.session_state.accumulated_kwh, cost, st.session_state.duration_minutes
    except Exception as e:
        st.warning(f"Error: {e}")
        return False, 0, 0, 0, 0, 0, 0

# Data update
def update_history_row():
    now = datetime.now()
    status = get_device_status()
    record = {
        "Time": now,
        "Current (mA)": status[3],
        "Voltage (V)": status[2],
        "Power (W)": status[1],
        "Energy (kWh)": status[4],
        "Cost (BDT)": status[5],
        "Duration (min)": status[6]
    }
    if len(st.session_state.history) == 0 or (now - pd.to_datetime(st.session_state.history[-1]['Time'])).total_seconds() >= 60:
        st.session_state.history.append(record)
        df = pd.DataFrame(st.session_state.history)
        df.to_csv(csv_path, index=False)
    else:
        df = pd.DataFrame(st.session_state.history)
    return df, status

# Toggle plug
def toggle_device(state: bool):
    try:
        device.turn_on() if state else device.turn_off()
        st.success(f"Device turned {'ON' if state else 'OFF'}")
    except Exception as e:
        st.error(f"Error toggling device: {e}")

# Auto-refresh every 1 minute
st_autorefresh(interval=60000, limit=None, key="refresh")

# Page config
st.set_page_config(page_title="Energy Monitor | Sakib", layout="wide")

# Sidebar page selector
page = st.sidebar.selectbox("📄 Select Page", ["Dashboard", "History", "Summary & Insights"])

# Fetch data and status
df, status = update_history_row()
power_on, power, voltage, current_ma, kwh, cost, duration = status

# Page: Dashboard
if page == "Dashboard":
    left_col, right_col = st.columns([4, 1])
    with right_col:
        st.image("sakib.png", caption="👤 Sakib", width=100)
    with left_col:
        st.title("💡 Sakib - IoT Energy Monitoring Dashboard")

    colA, colB = st.columns([1, 4])
    with colA:
        st.button("🔌 Turn ON", on_click=toggle_device, args=(True,))
        st.button("💡 Turn OFF", on_click=toggle_device, args=(False,))

    st.subheader("🔍 Real-Time Device Parameters")
    row1 = st.columns(4)
    row2 = st.columns(3)
    metrics_1 = [
        ("🔋 Current", f"{current_ma:.2f} mA"),
        ("⚡ Power", f"{power:.2f} W"),
        ("🔢 Voltage", f"{voltage:.2f} V"),
        ("📈 Energy", f"{kwh:.6f} kWh")
    ]
    metrics_2 = [
        ("💰 Cost Per Unit", "6.00 BDT/kWh"),
        ("💸 Current Cost", f"{cost:.4f} BDT"),
        ("⏱️ ON Duration", f"{duration} min")
    ]
    for col, (label, val) in zip(row1, metrics_1):
        with col:
            st.markdown(f"""
            <div style='background: linear-gradient(145deg, #fdfbfb, #ebedee); padding: 15px; border-radius: 10px; text-align: center;'>
                <h5>{label}</h5>
                <span style='font-size: 1.3rem;'>{val}</span>
            </div>
            """, unsafe_allow_html=True)

    for col, (label, val) in zip(row2, metrics_2):
        with col:
            st.markdown(f"""
            <div style='background: linear-gradient(145deg, #fffbe7, #f3f9ff); padding: 15px; border-radius: 10px; text-align: center;'>
                <h5>{label}</h5>
                <span style='font-size: 1.3rem;'>{val}</span>
            </div>
            """, unsafe_allow_html=True)

    st.success(f"✅ Device is {'ON' if power_on else 'OFF'}")

    st.subheader("📊 Live Graph of Power Parameters")
    if not df.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df['Time'], df['Current (mA)'], label="Current (mA)", color="purple")
        ax.plot(df['Time'], df['Voltage (V)'], label="Voltage (V)", color="orange")
        ax.plot(df['Time'], df['Power (W)'], label="Power (W)", color="blue")
        ax.plot(df['Time'], df['Energy (kWh)'], label="Energy (kWh)", color="green")
        ax.plot(df['Time'], df['Cost (BDT)'], label="Cost (BDT)", color="red")
        ax.set_xlabel("Time")
        ax.set_ylabel("Value")
        ax.legend()
        ax.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)

    with open(csv_path, "rb") as f:
        st.download_button(label="📥 Download CSV", data=f, file_name="energy_history.csv", mime="text/csv")

# Page: History
elif page == "History":
    st.title("📈 History Visualization")
    st.subheader("🕓 Parameter-wise 1-Minute Graphs")
    for metric, color in zip(["Current (mA)", "Voltage (V)", "Power (W)", "Energy (kWh)", "Cost (BDT)"],
                              ["purple", "orange", "blue", "green", "red"]):
        st.markdown(f"### {metric}")
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(df['Time'], df[metric], label=metric, color=color)
        ax.set_xlabel("Time")
        ax.set_ylabel(metric)
        ax.legend()
        ax.grid(True)
        plt.xticks(rotation=45)
        st.pyplot(fig)


# Page: Summary & Insights
elif page == "Summary & Insights":
    st.title("📊 Summary & Insights")

    st.subheader("📋 Statistical Summary")
    numeric_df = df.select_dtypes(include='number')
    st.dataframe(numeric_df.describe())

    st.subheader("📈 Correlation Heatmap")
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(numeric_df.corr(), annot=True, cmap="coolwarm", ax=ax)
    st.pyplot(fig)

    st.subheader("💡 Key Insights")
    st.markdown("""
    - Voltage and power usage are moderately correlated.
    - Power usage directly impacts both energy consumption and cost.
    - Regular monitoring can help reduce unnecessary power usage.
    """)

st.caption("👨‍💻 Dashboard by Mahmudul Haque Sakib | Streamlit + Tuya + Insights")
