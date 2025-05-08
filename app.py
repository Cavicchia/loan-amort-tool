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
lots_to_payoff_per_month = st.sidebar.number_input("Lots sold per month",    value=3,   min_value=0, step=1)
monthly_paydown          = paydown_per_lot * lots_to_payoff_per_month

monthly_rate = annual_rate / 12
n_payments   = years * 12

draw_mode = st.sidebar.radio("Construction draw type",
                             ("Fixed amount", "Custom per month"))

if draw_mode == "Fixed amount":
    monthly_draw = st.sidebar.number_input(
        "Monthly construction draw", value=200_000, step=10_000, format="%d"
    )
    custom_draws = None
else:
    # CSV input for custom draws
    default = ["0"] * n_payments
    draws_csv = st.sidebar.text_area(
        "Enter custom draws (comma‑separated):",
        value=",".join(default),
        height=120
    )
    vals = [v.strip() for v in draws_csv.split(",")]
    # parse to floats, pad/truncate to exactly n_payments
    custom_draws = []
    for v in vals[:n_payments]:
        try:
            custom_draws.append(float(v))
        except:
            custom_draws.append(0.0)
    if len(custom_draws) < n_payments:
        custom_draws += [0.0] * (n_payments - len(custom_draws))
    monthly_draw = None

base = st.sidebar.date_input("Pick any date in first month", value=datetime.today())
start_date = pd.to_datetime(base) + MonthEnd(0)
st.sidebar.markdown(f"**Start date (month‑end):** {start_date.strftime('%Y‑%m‑%d')}")

# ─── Build raw schedule rows ──────────────────────────────
rows = []
balance = principal
cumulative_drawn = 0

for i in range(n_payments):
    period = i + 1
    # interest on beg bal
    interest = balance * monthly_rate
    # choose draw
    draw_amt = monthly_draw if draw_mode=="Fixed amount" else custom_draws[i]
    total_draw = draw_amt + interest
    cumulative_drawn += draw_amt
    paydown = monthly_paydown
    end_bal = balance + total_draw - paydown
    # true month‑end datetime
    date_dt = (start_date + MonthEnd(period)).to_pydatetime()

    rows.append({
        "Period":         period,
        "Date":           date_dt,
        "Beg Balance":    balance,
        "Const. Draw":    draw_amt,
        "Interest Draw":  interest,
        "Total Draw":     total_draw,
        "Cum. Drawn":     cumulative_drawn,
        "Paydown":        paydown,
        "End Balance":    end_bal,
    })
    balance = end_bal

# ─── Write Excel with formulas ───────────────────────────
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter",
                    date_format="yyyy‑mm‑dd",
                    datetime_format="yyyy‑mm‑dd") as writer:

    wb = writer.book
    ws = wb.add_worksheet("Schedule")
    writer.sheets["Schedule"] = ws

    money_fmt = wb.add_format({"num_format":"$#,##0"})
    date_fmt  = wb.add_format({"num_format":"yyyy‑mm‑dd"})

    # Write headers
    headers = ["Period","Date","Beg Balance","Const. Draw",
               "Interest Draw","Total Draw","Cum. Drawn",
               "Paydown","End Balance"]
    for col, h in enumerate(headers):
        ws.write(0, col, h)

    # Write data rows with formulas
    for idx, r in enumerate(rows):
        excel_row = idx + 2  # Excel human row number
        row_idx   = idx + 1  # zero‑based index for xlsxwriter

        # Period & Date
        ws.write_number(row_idx, 0, r["Period"])
        ws.write_datetime(row_idx, 1, r["Date"], date_fmt)

        # Beg Balance
        if idx == 0:
            ws.write_number(row_idx, 2, principal, money_fmt)
        else:
            ws.write_formula(row_idx, 2, f"=I{excel_row-1}", money_fmt)

        # Construction Draw (static value)
        ws.write_number(row_idx, 3, r["Const. Draw"], money_fmt)

        # Interest Draw
        ws.write_formula(row_idx, 4, f"=C{excel_row}*{monthly_rate}", money_fmt)

        # Total Draw = D+E
        ws.write_formula(row_idx, 5, f"=D{excel_row}+E{excel_row}", money_fmt)

        # Cum. Drawn
        if idx == 0:
            ws.write_formula(row_idx, 6, f"=D{excel_row}", money_fmt)
        else:
            ws.write_formula(row_idx, 6,
                             f"=G{excel_row-1}+D{excel_row}", money_fmt)

        # Paydown
        ws.write_number(row_idx, 7, r["Paydown"], money_fmt)

        # End Balance = C + F - H
        ws.write_formula(row_idx, 8,
                         f"=C{excel_row}+F{excel_row}-H{excel_row}", money_fmt)

# Flush buffer
output.seek(0)

# ─── Streamlit UI ────────────────────────────────────────
st.title("🔨 Loan Amortization & Draw Schedule")
st.download_button(
    label="📥 Download schedule as Excel (.xlsx)",
    data=output.read(),
    file_name="amort_schedule.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
