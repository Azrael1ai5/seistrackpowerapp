import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ----------------------------------------------------------------------
# Title with Logo/Icon
# ----------------------------------------------------------------------
col1, col2 = st.columns([1, 4])
with col1:
    # Replace with the correct path or URL for your logo image.
    st.image("images/LOGO DARK BACKGROUND.png", width=120)
with col2:
    st.title("Seistrack Power Analysis")
    st.markdown("Created By: Eric G. Bundalian")

st.markdown(
    """
    This application allows you to upload a **CSV** or **Excel** file containing plant power data and visualize it interactively.

    **Required Columns (after renaming):**
    - **Time:** The date and time of the measurement (e.g., 2025-04-09 02:20:00)
    - **PV(W):** Photovoltaic power output in Watts.
    - **Meter(W):** Utility meter reading in Watts (negative values may indicate power import).
    - **Load(W):** Power consumption/load in Watts.

    If your file has extra rows above the real headers (e.g., title rows), specify how many rows to skip and which row contains the actual column headers.
    """
)

# ----------------------------------------------------------------------
# File Uploader
# ----------------------------------------------------------------------
uploaded_file = st.file_uploader("Upload your file", type=["csv", "xlsx", "xls"])
if not uploaded_file:
    st.stop()

# ----------------------------------------------------------------------
# User Inputs: Rows to Skip and Header Row
# ----------------------------------------------------------------------
st.write("### File Reading Options")
skip_rows = st.number_input(
    label="Number of rows to skip at the top (before header)",
    min_value=0,
    value=0,
    step=1,
    help="Set to 0 if the header is in the very first row after any skipped rows."
)
header_row = st.number_input(
    label="Row index for the column headers (0-based). Set to -1 if there is no header row.",
    min_value=-1,
    value=0,
    step=1,
    help=("For example, if the real header is on the 2nd line in Excel (after skipping 1 row), "
          "set skip_rows=1 and header_row=0.")
)

# ----------------------------------------------------------------------
# Read the File Based on the Options
# ----------------------------------------------------------------------
file_extension = os.path.splitext(uploaded_file.name)[1].lower()
try:
    if file_extension == ".csv":
        if header_row >= 0:
            df_raw = pd.read_csv(uploaded_file, skiprows=skip_rows, header=header_row)
        else:
            df_raw = pd.read_csv(uploaded_file, skiprows=skip_rows, header=None)
    elif file_extension in [".xlsx", ".xls"]:
        if header_row >= 0:
            df_raw = pd.read_excel(uploaded_file, skiprows=skip_rows, header=header_row)
        else:
            df_raw = pd.read_excel(uploaded_file, skiprows=skip_rows, header=None)
    else:
        st.error("Unsupported file type!")
        st.stop()
except Exception as e:
    st.error(f"Error reading file: {e}")
    st.stop()

st.write("### Columns in the uploaded file:")
st.write(df_raw.columns.tolist())
st.dataframe(df_raw.head(10))

# ----------------------------------------------------------------------
# Column Renaming
# ----------------------------------------------------------------------
required_columns = ["Time", "PV(W)", "Meter(W)", "Load(W)"]
st.write("### Rename Columns")
for desired_col in required_columns:
    if desired_col not in df_raw.columns:
        available_options = [c for c in df_raw.columns if c not in required_columns]
        if available_options:
            col_to_rename = st.selectbox(
                f"Select a column to rename to '{desired_col}'",
                options=available_options,
                key=f"rename_{desired_col}"
            )
            if st.button(f"Rename '{col_to_rename}' to '{desired_col}'", key=f"btn_{desired_col}"):
                df_raw.rename(columns={col_to_rename: desired_col}, inplace=True)
                st.success(f"Renamed '{col_to_rename}' to '{desired_col}'!")
        else:
            st.error("No available columns to rename.")
st.write("### Updated Columns:")
st.write(df_raw.columns.tolist())

# ----------------------------------------------------------------------
# Parse the Time Column
# ----------------------------------------------------------------------
if "Time" not in df_raw.columns:
    st.error("Cannot proceed without a 'Time' column. Please rename a column to 'Time'.")
    st.stop()
else:
    try:
        df_raw["Time"] = pd.to_datetime(df_raw["Time"], errors="coerce")
    except Exception as e:
        st.error(f"Error parsing 'Time' column: {e}")
        st.stop()

# ----------------------------------------------------------------------
# Validate Required Columns
# ----------------------------------------------------------------------
missing_columns = [c for c in required_columns if c not in df_raw.columns]
if missing_columns:
    st.error(f"The file is missing the following required column(s): {', '.join(missing_columns)}")
    st.stop()

# ----------------------------------------------------------------------
# Clean Data: Drop rows with invalid Time
# ----------------------------------------------------------------------
df_raw.dropna(subset=["Time"], inplace=True)

# ----------------------------------------------------------------------
# Automatic Calibration (Goodwe Integration)
# ----------------------------------------------------------------------
st.title("Goodwe (SEMS) to Actual Meter Calibration")

st.markdown("""
This tool calculates the correction factor of SEMS data vs actual Meralco Meter Reading  based on Min and Max
""")

st.header("Step 1: Input Min and Max from SEMS and Meter reading [02] OFF Peak PMax and [04] Peak Pmax")

col1, col2 = st.columns(2)

with col1:
    min_meter = st.number_input("SEMS Min (kW)", value=0.00)
    max_meter = st.number_input("SEMS Max (kW)", value=200.00)

with col2:
    min_actual = st.number_input("Grid Min Reading [02] (kW)", value=0.00)
    max_actual = st.number_input("Grid Max Reading [04] (kW)", value=200.00)

# Calculate slope (m) and intercept (b)
try:
    m = (max_actual - min_actual) / (max_meter - min_meter)
    b = min_actual - (m * min_meter)

    st.success(f"Calibration Formula: Adjusted = {m:.5f} × Meter Reading + ({b:.5f})")
except ZeroDivisionError:
    st.error("Invalid input: Max and Min Meter Readings cannot be the same.")

st.header("Step 2: Input Energy value from SEMS")

reading_input = st.number_input("SEMS Reading to check in (KW):", value=100.00)
adjusted_value = m * reading_input + b

st.header(f"**Calibrated Energy Reading:** {adjusted_value:.2f} kW")

# Automatically adjust the raw data using the calibration factor:
df_raw["PV(W)"] = m * df_raw["PV(W)"] + b
df_raw["Meter(W)"] = m * df_raw["Meter(W)"] + b
df_raw["Load(W)"] = m * df_raw["Load(W)"] + b

# ----------------------------------------------------------------------
# Prepare Data for Plotting
# ----------------------------------------------------------------------
df = df_raw.copy()
df.set_index("Time", inplace=True)
st.subheader("Data Preview")
# Display the entire processed dataframe
st.dataframe(df)
df_plot = df.reset_index()

# ----------------------------------------------------------------------
# Download Processed CSV File
# ----------------------------------------------------------------------
st.download_button(
    label="Download Processed CSV",
    data=df_plot.to_csv(index=False),
    file_name="processed_data.csv",
    mime="text/csv"
)

# ----------------------------------------------------------------------
# Compute Summary Statistics (in KW) for each sensor
# ----------------------------------------------------------------------
df_plot["PV_KW"] = df_plot["PV(W)"] / 1000
df_plot["Load_KW"] = df_plot["Load(W)"] / 1000
df_plot["Meter_KW_abs"] = df_plot["Meter(W)"].abs() / 1000

total_pv = df_plot["PV_KW"].sum()
min_pv = df_plot["PV_KW"].min()
max_pv = df_plot["PV_KW"].max()
avg_pv = df_plot["PV_KW"].mean()

total_load = df_plot["Load_KW"].sum()
min_load = df_plot["Load_KW"].min()
max_load = df_plot["Load_KW"].max()
avg_load = df_plot["Load_KW"].mean()

total_meter = df_plot["Meter_KW_abs"].sum()
min_meter = df_plot["Meter_KW_abs"].min()
max_meter = df_plot["Meter_KW_abs"].max()
avg_meter = df_plot["Meter_KW_abs"].mean()

# Extract a representative date (assuming a single day)
data_date = df_plot["Time"].min().strftime("%b %d, %Y")

st.subheader("Summary Statistics (in KW)")
st.markdown(f"""
<span style="font-weight:bold; color:blue; font-size:24px;">DATE: {data_date}</span>

<span style="color:yellow; font-weight:bold;">LOAD:</span><br/>
- <span style="color:yellow; font-weight:bold;">Total:</span> {total_load:.0f} KW  
- <span style="color:yellow; font-weight:bold;">Min:</span> {min_load:.0f} KW  
- <span style="color:yellow; font-weight:bold;">Max:</span> {max_load:.0f} KW  
- <span style="color:yellow; font-weight:bold;">Average:</span> {avg_load:.0f} KW  

<span style="color:green; font-weight:bold;">PV:</span><br/>
- <span style="color:green; font-weight:bold;">Total:</span> {total_pv:.0f} KW  
- <span style="color:green; font-weight:bold;">Min:</span> {min_pv:.0f} KW  
- <span style="color:green; font-weight:bold;">Max:</span> {max_pv:.0f} KW  
- <span style="color:green; font-weight:bold;">Average:</span> {avg_pv:.0f} KW  

<span style="color:red; font-weight:bold;">METER (Absolute Values):</span><br/>
- <span style="color:red; font-weight:bold;">Total:</span> {total_meter:.0f} KW  
- <span style="color:red; font-weight:bold;">Min:</span> {min_meter:.0f} KW  
- <span style="color:red; font-weight:bold;">Max:</span> {max_meter:.0f} KW  
- <span style="color:red; font-weight:bold;">Average:</span> {avg_meter:.0f} KW
""", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Series Visibility Toggle (Sidebar)
# ----------------------------------------------------------------------
st.sidebar.header("Toggle Series Visibility")
show_pv = st.sidebar.checkbox("Show PV(W)", value=True)
show_meter = st.sidebar.checkbox("Show Meter(W)", value=True)
show_load = st.sidebar.checkbox("Show Load(W)", value=True)

visible_series = []
if show_pv:
    visible_series.append("PV(W)")
if show_meter:
    visible_series.append("Meter(W)")
if show_load:
    visible_series.append("Load(W)")

# ----------------------------------------------------------------------
# Define Base Colors for Each Series
# ----------------------------------------------------------------------
color_map = {
    "PV(W)": "green",
    "Meter(W)": "red",
    "Load(W)": "yellow"
}

# ----------------------------------------------------------------------
# Create the Base Plotly Figure Using Visible Series Only
# ----------------------------------------------------------------------
st.subheader("Plant Power Data Over Time")
fig = px.line(
    df_plot,
    x="Time",
    y=visible_series,
    markers=True,
    title="Plant Power Data Over Time",
    labels={"value": "Power (W)", "variable": "Measurement", "Time": "Time"},
    color_discrete_map=color_map
)
fig.update_xaxes(tickformat="%H:%M:%S")
fig.update_layout(
    xaxis=dict(rangeslider=dict(visible=True), title="Time"),
    yaxis_title="Power (W)",
    legend_title_text="Measurements",
    margin=dict(l=40, r=40, t=40, b=40)
)

# ----------------------------------------------------------------------
# Add Markers for Max and Min Values (Only for Visible Series)
# ----------------------------------------------------------------------
for col in ["PV(W)", "Meter(W)", "Load(W)"]:
    if col not in visible_series:
        continue
    if df_plot[col].dtype.kind in 'biufc' and not df_plot[col].empty:
        if col == "Meter(W)":
            max_idx = df_plot[col].abs().idxmax()
            min_idx = df_plot[col].abs().idxmin()
        else:
            max_idx = df_plot[col].idxmax()
            min_idx = df_plot[col].idxmin()
        max_time = df_plot.loc[max_idx, "Time"]
        max_val = df_plot.loc[max_idx, col]
        min_time = df_plot.loc[min_idx, "Time"]
        min_val = df_plot.loc[min_idx, col]
        fig.add_scatter(
            x=[max_time],
            y=[max_val],
            mode="markers+text",
            marker=dict(color=color_map[col], size=12, symbol="star"),
            text=[f"{max_val/1000:.0f} KW"],
            textposition="top center",
            name=f"{col} Max"
        )
        fig.add_scatter(
            x=[min_time],
            y=[min_val],
            mode="markers+text",
            marker=dict(color=color_map[col], size=12, symbol="diamond"),
            text=[f"{min_val/1000:.0f} KW"],
            textposition="bottom center",
            name=f"{col} Min"
        )

# ----------------------------------------------------------------------
# Sidebar: Highlight Data Points by Range with Enhanced Marker Style in Blue
# ----------------------------------------------------------------------
st.sidebar.header("Highlight Data Points by Range")
def add_highlight_trace(x_data, y_data, series_name):
    fig.add_scatter(
        x=x_data,
        y=y_data,
        mode="markers",
        marker=dict(
            color="blue",
            size=14,
            symbol="circle",
            line=dict(width=3, color="black")
        ),
        name=f"{series_name} Highlight"
    )

# Highlight for PV(W)
highlight_pv = st.sidebar.checkbox("Highlight PV(W) Range")
if highlight_pv and show_pv:
    pv_lower = st.sidebar.number_input("PV(W) Lower Threshold", value=float(df_plot["PV(W)"].min()), key="pv_lower")
    pv_upper = st.sidebar.number_input("PV(W) Upper Threshold", value=float(df_plot["PV(W)"].max()), key="pv_upper")
    df_highlight_pv = df_plot[(df_plot["PV(W)"] >= pv_lower) & (df_plot["PV(W)"] <= pv_upper)]
    if not df_highlight_pv.empty:
        add_highlight_trace(df_highlight_pv["Time"], df_highlight_pv["PV(W)"], "PV(W)")

# Highlight for Meter(W)
highlight_meter = st.sidebar.checkbox("Highlight Meter(W) Range")
if highlight_meter and show_meter:
    meter_lower = st.sidebar.number_input("Meter(W) Lower Threshold", value=float(df_plot["Meter(W)"].min()), key="meter_lower")
    meter_upper = st.sidebar.number_input("Meter(W) Upper Threshold", value=float(df_plot["Meter(W)"].max()), key="meter_upper")
    df_highlight_meter = df_plot[(df_plot["Meter(W)"] >= meter_lower) & (df_plot["Meter(W)"] <= meter_upper)]
    if not df_highlight_meter.empty:
        add_highlight_trace(df_highlight_meter["Time"], df_highlight_meter["Meter(W)"], "Meter(W)")

# Highlight for Load(W)
highlight_load = st.sidebar.checkbox("Highlight Load(W) Range")
if highlight_load and show_load:
    load_lower = st.sidebar.number_input("Load(W) Lower Threshold", value=float(df_plot["Load(W)"].min()), key="load_lower")
    load_upper = st.sidebar.number_input("Load(W) Upper Threshold", value=float(df_plot["Load(W)"].max()), key="load_upper")
    df_highlight_load = df_plot[(df_plot["Load(W)"] >= load_lower) & (df_plot["Load(W)"] <= load_upper)]
    if not df_highlight_load.empty:
        add_highlight_trace(df_highlight_load["Time"], df_highlight_load["Load(W)"], "Load(W)")

# ----------------------------------------------------------------------
# Display the Final Line Figure
# ----------------------------------------------------------------------
st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# Donut Chart: Total Sensor Values for a Selected Time Frame
# ----------------------------------------------------------------------
st.subheader("HARVEST VS GRID")
st.markdown("Select a time range to compute the total (summed) values for PV(W) and Meter(W) relative to total Load(W). According to the data logic, **LOAD = PV + |METER|**. Therefore, we calculate:")
st.markdown("""
- **Total PV (KW)**  
- **Total Meter (KW)** [using the absolute value]  
- **Total Load (KW) = Total PV + Total Meter  
""")
time_min = df_plot["Time"].min().to_pydatetime()
time_max = df_plot["Time"].max().to_pydatetime()
total_time_range = st.sidebar.slider(
    "Select Time Range for Total Calculation",
    min_value=time_min,
    max_value=time_max,
    value=(time_min, time_max),
    format="HH:MM:SS"
)
df_total = df_plot[(df_plot["Time"] >= total_time_range[0]) & (df_plot["Time"] <= total_time_range[1])]

if df_total.empty:
    st.warning("No data in the selected time range for total calculation.")
else:
    total_pv = df_total["PV(W)"].sum() / 1000.0
    total_meter_abs = df_total["Meter(W)"].abs().sum() / 1000.0
    total_load = total_pv + total_meter_abs
    pie_data_total = pd.DataFrame({
        "Sensor": ["SOLAR", "GRID"],
        "Total (KW)": [total_pv, total_meter_abs]
    })
    color_map_donut = {"SOLAR": "green", "GRID": "red"}
    fig_total = px.pie(
        pie_data_total,
        values="Total (KW)",
        names="Sensor",
        title="INVERTER VS GRID RATIO TO LOAD",
        color="Sensor",
        color_discrete_map=color_map_donut,
        hole=0.4
    )
    fig_total.update_traces(
        texttemplate="%{label}: %{value:.0f} KW<br>%{percent}",
        textposition='outside',
        textinfo='none'
    )
    st.plotly_chart(fig_total, use_container_width=True)
    
    # ----------------------------------------------------------------------
    # Display Selected Time Range Under the Donut Chart
    # ----------------------------------------------------------------------
    selected_start = total_time_range[0].strftime("%b %d, %Y %H:%M:%S")
    selected_end = total_time_range[1].strftime("%b %d, %Y %H:%M:%S")
    st.markdown(f"**Selected Time Range:** {selected_start}  to  {selected_end}")

# ----------------------------------------------------------------------
# Changelog TXT Report Download
# ----------------------------------------------------------------------
changelog_text = """
Changelog for Seistrack Power Analysis App
==========================================

Version 1.0 – Original Script:
- Basic file uploader for CSV/Excel files.
- Reads data with a fixed configuration (no options for skipping rows or header selection).
- Basic plotting of data without advanced customization.

Version 1.1 – Added Title with Logo/Icon:
- Displayed a logo alongside the title and "Created By" text.

Version 1.2 – Configurable File Reading Options:
- Added user inputs to specify the number of rows to skip and the header row index.

Version 1.3 – Dynamic Column Renaming:
- Implemented a section to rename columns to required names ("Time", "PV(W)", "Meter(W)", "Load(W)").

Version 1.4 – Time Parsing and Data Cleaning:
- Parsed the "Time" column into datetime objects with error handling.
- Dropped rows with invalid time data.

Version 1.5 – Data Preparation and Conversion:
- Prepared the DataFrame for analysis.
- Created new columns converting power values from Watts to kilowatts (KW), including absolute values for Meter.

Version 1.6 – Summary Statistics Calculation:
- Calculated summary statistics (Total, Min, Max, Average in KW) for LOAD, PV, and METER.
- Extracted and formatted the date from the dataset as "MMM DD, YYYY".
- Displayed summary statistics in bold colored text (LOAD in yellow, PV in green, METER in red, DATE in blue with larger font).

Version 1.7 – Series Visibility and Interactive Line Chart:
- Added sidebar toggles for displaying PV, Meter, and Load series.
- Created an interactive Plotly line chart with time on the x-axis (formatted as HH:MM:SS).
- Added max/min markers with values in KW (no decimal places).

Version 1.8 – Data Point Highlighting:
- Integrated sidebar options for highlighting data points within defined ranges using blue markers.

Version 1.9 – Donut Chart (HARVEST VS GRID) Implementation:
- Added a donut chart that calculates total PV and total absolute Meter values over a user-selected time range.
- The donut chart reflects the data logic: LOAD = PV + |METER|.
- Displays two slices: "SOLAR" (for PV) and "GRID" (for Meter) with a text template showing the label, value (KW), and percentage.

Version 2.0 – Final Customizations:
- Adjusted the donut chart text template to display the label, the whole-number value followed by "KW", and the percentage on a new line.
- Integrated a download button to download the changelog as a TXT file.
- Added a display of the selected time range below the donut chart.
- Added an option to download the full processed CSV file from the Data Preview section.

Version 3 – Automatic Calibration Integration:
- Added an automatic calibration step using a default calibration factor.
- The calibration factor (default = 1.0) is applied to PV, Meter, and Load values before further processing.
- Streamlined the calibration process so that it runs automatically without a separate file upload.

Final Version Summary:
- Enhanced file upload, dynamic column renaming, and time parsing.
- Automatic calibration of sensor values using Goodwe calibration parameters.
- Interactive visualizations with a line chart and a donut chart.
- Comprehensive summary statistics with styled, colored text.
- Downloadable processed CSV and changelog TXT report.
"""

st.download_button(
    label="Download Changelog as TXT",
    data=changelog_text,
    file_name="changelog.txt",
    mime="text/plain"
)
