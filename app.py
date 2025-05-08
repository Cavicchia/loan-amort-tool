import streamlit as st
import pandas as pd
from pandas.tseries.offsets import MonthEnd
from datetime import datetime
import io

# ─── Sidebar inputs ───────────────────────────────────────
st.sidebar.header("Loan & Draw Parameters")

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
    ("Fixed amount", "Per-lot variable")
)
if paydown_mode == "Fixed amount":
    monthly_paydown = st.sidebar.number_input(
        "Monthly paydown amount", value=150_000, step=5_000, format="%d"
    )
else:
    paydown_per_lot = st.sidebar.number_input(
        "Paydown per lot sold", value=50_000, step=5_000, format="%d"
    )
    lots_sold = st.sidebar.number_input(
        "Lots sold per month", value=3, min_value=0, step=1, format="%d"
    )
    monthly_paydown = paydown_per_lot * lots_sold

# Date picker anchored to true month-end
base = st.sidebar.date_input(
    "Pick any date in first month", value=datetime.today()
)
start_date = pd.to_datetime(base) + MonthEnd(0)
st.sidebar.markdown(
    f"**Start date (month-end):** {start_date.strftime('%Y-%m-%d')}"
)

# Derived values
monthly_rate = annual_rate / 12
n_payments = term_months

# ─── Build schedule rows ──────────────────────────────────
rows = []
balance = principal
cumulative_drawn = 0

for i in range(n_payments):
    period = i + 1
    interest = balance * monthly_rate
    draw_amt = monthly_draw if draw_mode == "Fixed amount" else custom_draws[i]
    total_draw = draw_amt + interest
    cumulative_drawn += draw_amt
    paydown = monthly_paydown
    end_bal = balance + total_draw - paydown
    date_dt = (start_date + MonthEnd(period)).to_pydatetime()

    rows.append({
        "Period": period,
        "Date": date_dt,
        "Beg Balance": balance,
        "Const. Draw": draw_amt,
        "Interest Draw": interest,
        "Total Draw": total_draw,
        "Cum. Drawn": cumulative_drawn,
        "Paydown": paydown,
        "End Balance": end_bal,
    })
    balance = end_bal

# Convert to DataFrame and compute total interest paid
df = pd.DataFrame(rows)
total_interest_paid = df['Interest Draw'].sum()

# ─── Write Excel with formulas ───────────────────────────
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

    # Write headers
    headers = [
        "Period", "Date", "Beg Balance", "Const. Draw",
        "Interest Draw", "Total Draw", "Cum. Drawn",
        "Paydown", "End Balance"
    ]
    for col, h in enumerate(headers):
        ws.write(0, col, h)

    # Write data rows with formulas
    for idx, r in enumerate(rows):
        excel_row = idx + 2
        row_idx = idx + 1

        ws.write_number(row_idx, 0, r["Period"])
        ws.write_datetime(row_idx, 1, r["Date"], date_fmt)

        if idx == 0:
            ws.write_number(row_idx, 2, principal, money_fmt)
        else:
            ws.write_formula(row_idx, 2, f"=I{excel_row-1}", money_fmt)

        ws.write_number(row_idx, 3, r["Const. Draw"], money_fmt)
        ws.write_formula(row_idx, 4, f"=C{excel_row}*{monthly_rate}", money_fmt)
        ws.write_formula(row_idx, 5, f"=D{excel_row}+E{excel_row}", money_fmt)

        if idx == 0:
            ws.write_formula(row_idx, 6, f"=D{excel_row}", money_fmt)
        else:
            ws.write_formula(row_idx, 6, f"=G{excel_row-1}+D{excel_row}", money_fmt)

        ws.write_number(row_idx, 7, r["Paydown"], money_fmt)
        ws.write_formula(row_idx, 8, f"=C{excel_row}+F{excel_row}-H{excel_row}", money_fmt)

output.seek(0)

# ─── Streamlit UI ────────────────────────────────────────
st.title("🔨 Loan Amortization & Draw Schedule")

# Summary section
st.subheader("Loan Summary")
st.markdown(f"- **Interest rate:** {annual_rate*100:.2f}%")
st.markdown(f"- **Term:** {term_months} months")
st.markdown(f"- **Total interest paid:** ${total_interest_paid:,.2f}")

# Display results
st.dataframe(df, use_container_width=True)

# Download Excel
st.download_button(
    label="📥 Download schedule as Excel (.xlsx)",
    data=output.read(),
    file_name="amort_schedule.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
