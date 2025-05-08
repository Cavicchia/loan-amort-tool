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
    monthly_draw = st.sidebar.number_input(
        "Monthly construction draw", value=200_000, step=10_000, format="%d"
    )
    custom_draws = None
else:
    default_vals = ["0"] * n_payments
    draws_csv = st.sidebar.text_area(
        "Enter custom draws, CSV (one per period):",
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

# ─── Generate Excel with formulas ───────────────────────────
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter",
                    date_format="yyyy-mm-dd", datetime_format="yyyy-mm-dd") as writer:

    workbook  = writer.book
    worksheet = workbook.add_worksheet("Schedule")
    writer.sheets["Schedule"] = worksheet

    # Formats
    money_fmt = workbook.add_format({"num_format":"$#,##0"})
    date_fmt  = workbook.add_format({"num_format":"yyyy-mm-dd"})

    # Headers
    headers = ["Period","Date","Beg Balance","Const. Draw","Interest Draw",
               "Total Draw","Cum. Drawn","Paydown","End Balance"]
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)

    # Fill rows with formulas or constants
    for i in range(n_payments):
        excel_row = i + 2  # Excel row number (header is row 1)
        row_idx   = i + 1  # zero-based for xlsxwriter

        # Period
        worksheet.write_number(row_idx, 0, i+1)

        # Date = true month-end
        dt = (start_date + MonthEnd(i+1)).to_pydatetime()
        worksheet.write_datetime(row_idx, 1, dt, date_fmt)

        # Beg Balance
        if i == 0:
            worksheet.write_number(row_idx, 2, principal, money_fmt)
        else:
            worksheet.write_formula(row_idx, 2, f"=I{excel_row-1}", money_fmt)

        # Construction Draw
        draw_val = monthly_draw if draw_mode=="Fixed amount" else custom_draws[i]
        worksheet.write_number(row_idx, 3, draw_val, money_fmt)

        # Interest Draw = Beg Balance * (annual_rate/12)
        worksheet.write_formula(row_idx, 4, f"=C{excel_row}*{monthly_rate}", money_fmt)

        # Total Draw = D + E
        worksheet.write_formula(row_idx, 5, f"=D{excel_row}+E{excel_row}", money_fmt)

        # Cum. Drawn
        if i == 0:
            worksheet.write_formula(row_idx, 6, f"=D{excel_row}", money_fmt)
        else:
            worksheet.write_formula(row_idx, 6, f"=G{excel_row-1}+D{excel_row}", money_fmt)

        # Paydown (static)
        worksheet.write_number(row_idx, 7, monthly_paydown, money_fmt)

        # End Balance = Beg + Total Draw – Paydown
        worksheet.write_formula(row_idx, 8, f"=C{excel_row}+F{excel_row}-H{excel_row}", money_fmt)

    writer.save()
    output.seek(0)

st.title("🔨 Loan Amortization & Draw Schedule")
st.download_button(
    label="📥 Download schedule as Excel (.xlsx)",
    data=output.read(),
    file_name="amort_schedule.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
