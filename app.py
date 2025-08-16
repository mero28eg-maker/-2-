import streamlit as st
from datetime import date
import pandas as pd
from calc import compute_headers_and_distribution, STAMP_DEFAULT

st.set_page_config(page_title="موزّع السواقط — ويب", layout="wide")

st.title("موزّع السواقط — واجهة المستخدم")
st.caption("جدول شهري مع إمكانية **تثبيت كمية لأي شهر (X)** وتلوين الصفوف المثبتة. الملخص يعرض فقط **F8/F9**.")

with st.form("inputs", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("قراءة البداية")
        b2 = st.number_input("الإستهلاك الكلي – بداية", value=0.0, step=0.001, format="%.3f")
        c2 = st.number_input("استهلاك الشهر السابق – بداية", value=0.0, step=0.1, format="%.1f")
        d2 = st.number_input("الاستهلاك الحالي – بداية (م³)", value=0.0, step=0.1, format="%.1f")
        e2 = st.number_input("الرصيد المتوفر – بداية", value=0.0, step=0.001, format="%.3f")
        topup1 = st.number_input("صافي قيمة الشحن 1", value=0.0, step=0.01, format="%.2f")
        topup2 = st.number_input("صافي قيمة الشحن 2", value=0.0, step=0.01, format="%.2f")
        sdate = st.date_input("تاريخ بداية الفترة", value=date.today().replace(day=1))
    with col2:
        st.subheader("قراءة النهاية")
        b3 = st.number_input("الإستهلاك الكلي – نهاية", value=0.0, step=0.001, format="%.3f")
        c3 = st.number_input("استهلاك الشهر السابق – نهاية", value=0.0, step=0.1, format="%.1f")
        d3 = st.number_input("الاستهلاك الحالي – نهاية (م³)", value=0.0, step=0.1, format="%.1f")
        e3 = st.number_input("الرصيد المتوفر – نهاية", value=0.0, step=0.001, format="%.3f")
        edate = st.date_input("تاريخ نهاية الفترة", value=date.today())

    st.markdown('---')
    st.subheader("التسعير")
    p_choices = ["2.35","2.50","2.60","3.00","4.00","يدوي"]
    p_opt = st.selectbox("السعر الأساسي (P1)", p_choices, index=1)
    p1 = st.number_input("P1 (لو اخترت يدوي)", value=2.50, step=0.01, format="%.2f") if p_opt=="يدوي" else float(p_opt)

    fee_choices = ["6.20","7.10","12.00","13.68","17.50","0","يدوي"]
    fee_opt = st.selectbox("Monthly Fee", fee_choices, index=5)
    fee = st.number_input("Monthly Fee (يدوي)", value=0.0, step=0.01, format="%.2f") if fee_opt=="يدوي" else float(fee_opt)

    stamp = st.number_input("دمغة الاستهلاك", value=float(STAMP_DEFAULT), step=0.001, format="%.3f")

    submit = st.form_submit_button("عرض الجدول", use_container_width=True)

if submit:
    base = compute_headers_and_distribution(
        b2=b2, c2=c2, d2=d2, e2=e2, sdate=sdate,
        b3=b3, c3=c3, d3=d3, e3=e3, edate=edate,
        topup1=topup1, topup2=topup2,
        p1=p1, fee=fee, stamp=stamp,
        fixed_quantities=None
    )
    months = base["months"]
    df_edit = pd.DataFrame({
        "Month": [m.strftime("%m/%Y") for m in months],
        "Quantity (m³)": [round(q,1) for q in base["q"]],
        "Fix (X)": [False]*len(months)
    })

    st.markdown("### حرّر الكميات وثبّت (X) عند الحاجة")
    edited = st.data_editor(
        df_edit,
        column_config={
            "Quantity (m³)": st.column_config.NumberColumn("Quantity (m³)", step=0.1, min_value=0.0, format="%.1f"),
            "Fix (X)": st.column_config.CheckboxColumn("Fix (X)"),
            "Month": st.column_config.TextColumn("Month")
        },
        use_container_width=True,
        num_rows="fixed",
        hide_index=True
    )

    # جمع الكميات المثبتة
    fixed_quantities = []
    for _, row in edited.iterrows():
        if row["Fix (X)"]:
            fixed_quantities.append(float(row["Quantity (m³)"]))
        else:
            fixed_quantities.append(None)

    res = compute_headers_and_distribution(
        b2=b2, c2=c2, d2=d2, e2=e2, sdate=sdate,
        b3=b3, c3=c3, d3=d3, e3=e3, edate=edate,
        topup1=topup1, topup2=topup2,
        p1=p1, fee=fee, stamp=stamp,
        fixed_quantities=fixed_quantities
    )

    st.markdown("### الملخص")
    c1, c2 = st.columns(2)
    c1.metric("F8 — الكمية المستهدفة (m³)", f"{res['F8']:.1f}")
    c2.metric("F9 — القيمة المستهدفة (EGP)", f"{res['F9']:.3f}")

    st.markdown("### جدول النتائج")
    out_df = pd.DataFrame({
        "Month": [m.strftime("%m/%Y") for m in res["months"]],
        "Quantity (m³)": [round(q,1) for q in res["q"]],
        "Value (EGP)": [f"{v:.3f}" for v in res["v"]],
        "Fixed": [bool(fx is not None and fx >= 0.0) for fx in fixed_quantities]
    })

    def _style_fixed(row):
        return ["background-color: #FFF3CD" if row.get("Fixed") else "" for _ in row]

    st.dataframe(out_df.style.apply(_style_fixed, axis=1), use_container_width=True)
