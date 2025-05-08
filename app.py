import streamlit as st
import pandas as pd
from pandas.tseries.offsets import MonthEnd
from datetime import datetime
import csv

# ─── Sidebar inputs ───────────────────────────────────────
st.sidebar.header("Loan & Draw Parameters")

# Core loan inputs
principal   = st.sidebar.number_input("Loan amount", value=11_830_000, step=100_000, format="%d")
annual_rate = st.sidebar.slider("Annual interest rate (%)", 0.0, 20.0, 8.0) / 100
years       = st.sidebar.number_input("Term (years)", value=3, min_value=1, max_value=30)

# Paydown inputs
paydown_per_lot          = st.sidebar.number_input("Paydown per lot sold", value=50_000, step=5_000, format="%d")
lots_to_payoff_per_month = st.sidebar.number_input("Lots sold per month", value=3, min_value=0, step=1)
monthly_paydown = paydown_per_lot * lots_to_payoff_per_month

# Derived values
monthly_rate = annual_rate / 12
n_payments   = years * 12

# Choose draw mode
draw_mode = st.sidebar.radio(
    "Construction draw type",
    ("Fixed amount", "Custom per month")
)

if draw_mode == "Fixed amount":
    # Fixed draw
    monthly_draw = st.sidebar.number_input(
        "Monthly construction draw", value=200_000, step=10_000, format="%d"
    )
    custom_draws = None

else:
    # Custom per‑month draws via comma‑separated list
    default_vals = ["0"] * n_payments
    draws_csv = st.sidebar.text_area(
        "🔢 Enter custom draws, one per period (comma‑separated):",
        value=",".join(default_vals),
        height=120
    )
    custom_draws = []
    for val in draws_csv.split(","):
        try:
            custom_draws.append(float(val.strip()))
        except:
            custom_draws.append(0.0)
    if len(custom_draws) < n_payments:
        custom_draws += [0.0] * (n_payments - len(custom_draws))
    else:
        custom_draws = custom_draws[:n_payments]
    monthly_draw = None

# Date picker anchored to true month‑end
base = st.sidebar.date_input("Pick any date in first month", value=datetime.today())
start_date = pd.to_datetime(base) + MonthEnd(0)
st.sidebar.markdown(f"**Start date (month-end):** {start_date.strftime('%Y-%m-%d')}")

# ─── Build schedule ───────────────────────────────────────
rows = []
balance = principal
cumulative_drawn = 0

for n in range(1, n_payments + 1):
    interest_draw = balance * monthly_rate
    if draw_mode == "Fixed amount":
        construction_draw = monthly_draw
    else:
        construction_draw = custom_draws[n-1]

    total_draw        = construction_draw + interest_draw
    cumulative_drawn += construction_draw
    paydown           = monthly_paydown
    ending_balance    = balance + total_draw - paydown
    period_end        = (start_date + MonthEnd(n)).strftime("%Y-%m-%d")

    rows.append({
        "Period":        n,
        "Date":          period_end,
        "Beg Balance":   f"{balance:,.2f}",
        "Const. Draw":   f"{construction_draw:,.2f}",
        "Interest Draw": f"{interest_draw:,.2f}",
        "Total Draw":    f"{total_draw:,.2f}",
        "Cum. Drawn":    f"{cumulative_drawn:,.2f}",
        "Paydown":       f"{paydown:,.2f}",
        "End Balance":   f"{ending_balance:,.2f}",
    })

    balance = ending_balance

df = pd.DataFrame(rows)

# ─── Display & download ──────────────────────────────────
st.title("🔨 Loan Amortization & Draw Schedule")
st.dataframe(df, use_container_width=True)

csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Download schedule as CSV",
    data=csv_bytes,
    file_name="amort_schedule.csv",
    mime="text/csv"
)
