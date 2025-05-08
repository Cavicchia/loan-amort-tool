import streamlit as st
import pandas as pd
from pandas.tseries.offsets import MonthEnd
from datetime import datetime
import io

# ─── Sidebar inputs ───────────────────────────────────────
st.sidebar.header("Loan & Draw Parameters")
principal   = st.sidebar.number_input("Loan amount", value=11_830_000, step=100_000, format="%d")
annual_rate = st.sidebar.slider("Annual interest rate (%)", 0.0, 20.0, 8.0) / 100
years       = st.sidebar.number_input("Term (years)", value=3, min_value=1, max_value=30)

paydown_per_lot          = st.sidebar.number_input("Paydown per lot sold", value=50_000, step=5_000, format="%d")
lots_to_payoff_per_month = st.sidebar.number_input("Lots sold per month", value=3, min_value=0, step=1)
monthly_paydown = paydown_per_lot * lots_to_payoff_per_month

monthly_rate = annual_rate / 12
n_payments   = years * 12

draw_mode = st.sidebar.radio(
    "Construction draw type",
    ("Fixed amount", "Custom per month")
)

if draw_mode == "Fixed amount":
    monthly_draw = st.sidebar.number_input("Monthly construction draw", value=200_000, step=10_000, format="%d")
    custom_draws = None
else:
    default_vals = ["0"] * n_payments
    draws_csv = st.sidebar.text_area(
        "Enter custom draws (CSV, one per period):",
        value=",".join(default_vals),
        height=120
    )
    custom_draws = []
    for val in draws_csv.split(","):
        try:
            custom_draws.append(float(val.strip()))
        except:
            custom_draws.append(0.0)
    custom_draws = (custom_draws + [0.0]*n_payments)[:n_payments]
    monthly_draw = None

base = st.sidebar.date_input("Pick any date in first month", value=datetime.today())
start_date = pd.to_datetime(base) + MonthEnd(0)
st.sidebar.markdown(f"**Start date (month-end):** {start_date.strftime('%Y-%m-%d')}")

# ─── Build your schedule rows ────────────────────────────
rows = []
balance = principal
cumulative_drawn = 0

for n in range(1, n_payments + 1):
    interest_draw = balance * monthly_rate
    construction_draw = monthly_draw if draw_mode=="Fixed amount" else custom_draws[n-1]
    total_draw = construction_draw + interest_draw
    cumulative_drawn += construction_draw
    paydown = monthly_paydown
    ending_balance = balance + total_draw - paydown
    period_end = (start_date + MonthEnd(n)).strftime("%Y-%m-%d")

    rows.append({
        "Period":        n,
        "Date":          period_end,
        "Beg Balance":   balance,
        "Const. Draw":   construction_draw,
        "Interest Draw": interest_draw,
        "Total Draw":    total_draw,
        "Cum. Drawn":    cumulative_drawn,
        "Paydown":       paydown,
        "End Balance":   ending_balance,
    })
    balance = ending_balance

# ─── Write Excel with formulas ───────────────────────────
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter",
                    date_format="yyyy-mm-dd",
                    datetime_format="yyyy-mm-dd") as writer:

    wb = writer.book
    ws = wb.add_worksheet("Schedule")
    writer.sheets["Schedule"] = ws

    money_fmt = wb.add_format({"num_format":"$#,##0"})
    date_fmt  = wb.add_format({"num_format":"yyyy-mm-dd"})

    headers = ["Period","Date","Beg Balance","Const. Draw","Interest Draw",
               "Total Draw","Cum. Drawn","Paydown","End Balance"]
    for col, h in enumerate(headers):
        ws.write(0, col, h)

    for i, r in enumerate(rows):
        excel_row = i + 2
        # Period & Date
        ws.write_number(i+1, 0, r["Period"])
        ws.write_datetime(i+1, 1, datetime.fromisoformat(r["Date"]), date_fmt)
        # Beginning Balance
        if i == 0:
            ws.write_number(i+1, 2, principal, money_fmt)
        else:
            ws.write_formula(i+1, 2, f"=I{excel_row-1}", money_fmt)
        # Construction Draw (constant)
        ws.write_number(i+1, 3, r["Const. Draw"], money_fmt)
        # Interest Draw formula
        ws.write_formula(i+1, 4, f"=C{excel_row}*{monthly_rate}", money_fmt)
        # Total Draw = D+E
        ws.write_formula(i+1, 5, f"=D{excel_row}+E{excel_row}", money_fmt)
        # Cum. Drawn
        if i == 0:
            ws.write_formula(i+1, 6, f"=D{excel_row}", money_fmt)
        else:
            ws.write_formula(i+1, 6, f"=G{excel_row-1}+D{excel_row}", money_fmt)
        # Paydown static
        ws.write_number(i+1, 7, r["Paydown"], money_fmt)
        # End Balance formula
        ws.write_formula(i+1, 8, f"=C{excel_row}+F{excel_row}-H{excel_row}", money_fmt)

# close the writer and rewind buffer
output.seek(0)

# ─── Streamlit UI ────────────────────────────────────────
st.title("🔨 Loan Amortization & Draw Schedule")
st.download_button(
    label="📥 Download schedule as Excel (.xlsx)",
    data=output.getvalue(),
    file_name="amort_schedule.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
