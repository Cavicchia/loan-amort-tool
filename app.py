import streamlit as st
import pandas as pd
from pandas.tseries.offsets import MonthEnd
from datetime import datetime
import io

# ─── Sidebar inputs ───────────────────────────────────────
st.sidebar.header("Loan Parameters & Draw/Paydown Settings")

# Core loan inputs
principal = st.sidebar.number_input(
    "Loan amount", value=11_830_000, step=100_000, format="%d"
)
annual_rate_pct = st.sidebar.number_input(
    "Annual interest rate (%)", value=8.0, min_value=0.0, max_value=100.0, format="%.4f"
)
annual_rate = annual_rate_pct / 100
term_months = st.sidebar.number_input(
    "Term (months)", value=36, min_value=1, max_value=600, step=1, format="%d"
)

# Dates for starts
draw_base = st.sidebar.date_input(
    "First draw month (any date)", value=datetime.today()
)
start_date = pd.to_datetime(draw_base) + MonthEnd(0)
st.sidebar.markdown(f"**Draw start (month-end):** {start_date.strftime('%Y-%m-%d')}" )

paydown_base = st.sidebar.date_input(
    "First paydown month (any date)", value=start_date
)
paydown_start = pd.to_datetime(paydown_base) + MonthEnd(0)
st.sidebar.markdown(f"**Paydown start (month-end):** {paydown_start.strftime('%Y-%m-%d')}" )

# Interest handling mode
interest_mode = st.sidebar.radio(
    "Interest treatment",
    ("Capitalize interest into loan", "Pay interest out of cash")
)

# Construction draw mode
draw_mode = st.sidebar.radio(
    "Construction draw type",
    ("Fixed amount", "Custom per month")
)
if draw_mode == "Fixed amount":
    monthly_draw = st.sidebar.number_input(
        "Monthly construction draw", value=200_000, step=10_000, format="%d"
    )
    custom_draws = None
else:
    st.sidebar.markdown("#### Custom draws per month")
    custom_draws = [
        st.sidebar.number_input(
            f"Month {i} draw", value=0, step=1_000, format="%d", key=f"draw_{i}"
        ) for i in range(1, term_months+1)
    ]
    monthly_draw = None

# Paydown mode and parameters
paydown_mode = st.sidebar.radio(
    "Paydown type",
    ("Fixed paydown amount", "Custom per month")
)
paydowns_per_month = 0
paydown_amount = 0
if paydown_mode == "Fixed paydown amount":
    paydowns_per_month = st.sidebar.number_input(
        "Number of paydowns per month", value=3, min_value=0, step=1, format="%d"
    )
    paydown_amount = st.sidebar.number_input(
        "Paydown amount per settlement", value=50_000, step=5_000, format="%d"
    )
    custom_paydowns = None
else:
    st.sidebar.markdown("#### Custom paydowns per month")
    custom_paydowns = [
        st.sidebar.number_input(
            f"Month {i} paydowns (#)", value=0, min_value=0, step=1, key=f"pd_num_{i}"
        ) * st.sidebar.number_input(
            f"Month {i} paydown amount", value=0, step=1_000, key=f"pd_amt_{i}"
        ) for i in range(1, term_months+1)
    ]

# Derived values
monthly_rate = annual_rate / 12
n_payments = term_months

# ─── Build schedule rows ──────────────────────────────────
rows = []
balance = principal

for i in range(n_payments):
    period = i + 1
    date_dt = (start_date + MonthEnd(period)).to_pydatetime()
    # interest accured
    interest = balance * monthly_rate
    # draw
    draw_amt = monthly_draw if draw_mode == "Fixed amount" else custom_draws[i]
    # total draw depends on interest handling
    if interest_mode == "Capitalize interest into loan":
        total_draw = draw_amt + interest
    else:
        total_draw = draw_amt
    # paydown
    if date_dt < paydown_start:
        paydown = 0
    else:
        if paydown_mode == "Fixed paydown amount":
            paydown = paydowns_per_month * paydown_amount
        else:
            paydown = custom_paydowns[i]
    # ending balance
    end_bal = balance + total_draw - paydown

    rows.append({
        "Period": period,
        "Date": date_dt,
        "Beg Balance": balance,
        "Const. Draw": draw_amt,
        "Interest Draw": interest,
        "Total Draw": total_draw,
        "Paydown": paydown,
        "End Balance": end_bal
    })
    balance = end_bal

# ─── Write Excel with inline summary & formulas ──────────
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter",
                    date_format="yyyy-mm-dd", datetime_format="yyyy-mm-dd") as writer:
    wb = writer.book
    ws = wb.add_worksheet("Schedule")
    writer.sheets["Schedule"] = ws

    # Formats
    money_fmt = wb.add_format({"num_format": "$#,##0"})
    date_fmt = wb.add_format({"num_format": "yyyy-mm-dd"})
    pct_fmt = wb.add_format({"num_format": "0.00%"})
    text_fmt = wb.add_format({"bold": True})

    # Summary section (rows 0-6)
    ws.write(0, 0, "Annual Rate", text_fmt)
    ws.write_number(0, 1, annual_rate, pct_fmt)
    ws.write(1, 0, "Monthly Rate (=B1/12)", text_fmt)
    ws.write_formula(1, 1, "=B1/12", pct_fmt)
    ws.write(2, 0, "Term (months)", text_fmt)
    ws.write_number(2, 1, term_months)
    ws.write(3, 0, "Interest treatment", text_fmt)
    ws.write(3, 1, interest_mode)
    ws.write(4, 0, "Settlements/month", text_fmt)
    ws.write_number(4, 1, paydowns_per_month)
    ws.write(5, 0, "Amount/settlement", text_fmt)
    ws.write_number(5, 1, paydown_amount, money_fmt)
    # leave row 6 blank

    # Header row at 7
    header_row = 7
    headers = ["Period","Date","Beg Balance","Const. Draw",
               "Interest Draw","Total Draw","Paydown","End Balance"]
    for col, h in enumerate(headers):
        ws.write(header_row, col, h, text_fmt)

    # Data rows
    for idx, r in enumerate(rows):
        row_idx = header_row + 1 + idx
        excel_row = row_idx + 1
        ws.write_number(row_idx, 0, r["Period"])
        ws.write_datetime(row_idx, 1, r["Date"], date_fmt)
        if idx == 0:
            ws.write_number(row_idx, 2, principal, money_fmt)
        else:
            ws.write_formula(row_idx, 2, f"=H{excel_row-1}", money_fmt)
        ws.write_number(row_idx, 3, r["Const. Draw"], money_fmt)
        # Interest draw linking to monthly rate
        ws.write_formula(row_idx, 4, f"=C{excel_row}*$B$2", money_fmt)
        # Total draw formula depending on interest handling
        if interest_mode == "Capitalize interest into loan":
            ws.write_formula(row_idx, 5, f"=D{excel_row}+E{excel_row}", money_fmt)
        else:
            ws.write_formula(row_idx, 5, f"=D{excel_row}", money_fmt)
        # Paydown linking to B5 and B6 for fixed, else number
        if paydown_mode == "Fixed paydown amount":
            ws.write_formula(row_idx, 6, "=$B$5*$B$6", money_fmt)
        else:
            ws.write_number(row_idx, 6, r["Paydown"], money_fmt)
        # End balance
        ws.write_formula(row_idx, 7, f"=C{excel_row}+F{excel_row}-G{excel_row}", money_fmt)

    # Total interest sum below data
    sum_row = header_row + 1 + n_payments
    start_data = header_row + 2
    end_data = header_row + 1 + n_payments
    ws.write(sum_row, 3, "Total Interest:", text_fmt)
    ws.write_formula(sum_row, 4, f"=SUM(E{start_data}:E{end_data})", money_fmt)

# Flush buffer
output.seek(0)

# ─── Streamlit UI ────────────────────────────────────────
st.title("🔨 Loan Amort & Draw Schedule with Interest Options")
st.download_button(
    label="📥 Download schedule as Excel (.xlsx)",
    data=output.read(),
    file_name="amort_schedule.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
