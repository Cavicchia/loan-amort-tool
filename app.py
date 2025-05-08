import streamlit as st
import pandas as pd
from pandas.tseries.offsets import MonthEnd
from datetime import datetime
import io

# ─── Sidebar inputs ───────────────────────────────────────
st.sidebar.header("Loan & Draw & Paydown Parameters")

# Core loan inputs
principal = st.sidebar.number_input(
    "Loan amount", value=11_830_000, step=100_000, format="%d"
)
annual_rate = st.sidebar.number_input(
    "Annual interest rate (%)", value=8.0, min_value=0.0, max_value=100.0, format="%.4f"
) / 100
term_months = st.sidebar.number_input(
    "Term (months)", value=36, min_value=1, max_value=600, step=1, format="%d"
)

# Draw mode selection
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
    st.sidebar.markdown("#### Enter draw for each month:")
    custom_draws = []
    for i in range(1, term_months + 1):
        val = st.sidebar.number_input(
            f"Month {i} draw", value=0, step=1_000, format="%d", key=f"draw_{i}"
        )
        custom_draws.append(val)
    monthly_draw = None

# Paydown mode selection
paydown_mode = st.sidebar.radio(
    "Paydown type",
    ("Fixed paydown", "Custom per month")
)
if paydown_mode == "Fixed paydown":
    paydowns_per_month = st.sidebar.number_input(
        "Number of paydowns per month", value=3, min_value=0, step=1, format="%d"
    )
    paydown_amount = st.sidebar.number_input(
        "Paydown amount per paydown", value=50_000, step=5_000, format="%d"
    )
    custom_paydowns = None
else:
    st.sidebar.markdown("#### Enter paydowns for each month:")
    custom_paydowns = []
    for i in range(1, term_months + 1):
        num = st.sidebar.number_input(
            f"Month {i} paydowns (#)", value=0, min_value=0, step=1, key=f"pd_num_{i}"
        )
        amt = st.sidebar.number_input(
            f"Month {i} paydown amount", value=0, step=1_000, key=f"pd_amt_{i}"
        )
        custom_paydowns.append(num * amt)
monthly_rate = annual_rate / 12

# Date picker anchored to true month-end
base = st.sidebar.date_input(
    "Pick any date in first month", value=datetime.today()
)
start_date = pd.to_datetime(base) + MonthEnd(0)
st.sidebar.markdown(
    f"**Start date (month-end):** {start_date.strftime('%Y-%m-%d')}"
)

# ─── Build schedule rows ──────────────────────────────────
rows = []
balance = principal

for i in range(term_months):
    period = i + 1
    interest = balance * monthly_rate
    draw_amt = (monthly_draw if draw_mode == "Fixed amount" else custom_draws[i])
    total_draw = draw_amt + interest
    if paydown_mode == "Fixed paydown":
        paydown = paydowns_per_month * paydown_amount
    else:
        paydown = custom_paydowns[i]
    end_bal = balance + total_draw - paydown
    date_dt = (start_date + MonthEnd(period)).to_pydatetime()
    rows.append({
        "Period": period,
        "Date": date_dt,
        "Beg Balance": balance,
        "Const. Draw": draw_amt,
        "Interest Draw": interest,
        "Total Draw": total_draw,
        "Paydown": paydown,
        "End Balance": end_bal,
    })
    balance = end_bal

# ─── Write Excel with inline summary & formulas ──────────
output = io.BytesIO()
with pd.ExcelWriter(
    output, engine="xlsxwriter",
    date_format="yyyy-mm-dd", datetime_format="yyyy-mm-dd"
) as writer:
    wb = writer.book
    ws = wb.add_worksheet("Schedule")
    writer.sheets["Schedule"] = ws

    money_fmt = wb.add_format({"num_format": "$#,##0"})
    date_fmt = wb.add_format({"num_format": "yyyy-mm-dd"})

    # Inline summary at top
    ws.write(0, 0, "Annual Rate (%)")
    ws.write_number(0, 1, annual_rate * 100)
    ws.write(1, 0, "Monthly Rate")
    ws.write_number(1, 1, monthly_rate)
    ws.write(2, 0, "Term (months)")
    ws.write_number(2, 1, term_months)

    # Leave row 3 blank
    header_row = 4
    headers = [
        "Period", "Date", "Beg Balance", "Const. Draw",
        "Interest Draw", "Total Draw", "Paydown", "End Balance"
    ]
    for col, h in enumerate(headers):
        ws.write(header_row, col, h)

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
        # Link interest draw to monthly rate cell B1
        ws.write_formula(row_idx, 4, f"=C{excel_row}*$B$2", money_fmt)
        ws.write_formula(row_idx, 5, f"=D{excel_row}+E{excel_row}", money_fmt)
        ws.write_number(row_idx, 6, r["Paydown"], money_fmt)
        ws.write_formula(row_idx, 7, f"=C{excel_row}+F{excel_row}-G{excel_row}", money_fmt)

    # Total interest sum below data
    sum_row_idx = header_row + 1 + term_months
    start_excel = header_row + 2  # first data row index+1
    end_excel = header_row + 1 + term_months  # last data row index+1
    ws.write(sum_row_idx, 3, "Total Interest:")
    ws.write_formula(
        sum_row_idx, 4,
        f"=SUM(E{start_excel}:E{end_excel})",
        money_fmt
    )

# Flush buffer
output.seek(0)

# ─── Streamlit UI ────────────────────────────────────────
st.title("🔨 Loan Amortization & Draw Schedule with Inline Summary")
st.download_button(
    label="📥 Download schedule as Excel (.xlsx)",
    data=output.read(),
    file_name="amort_schedule.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
