import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

# ReportLab Imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

# Streamlit Page Setup
st.set_page_config(
    page_title="Dynamic IT Quotation Builder",
    page_icon="⚡",
    layout="wide"
)

# ==========================================
# 1. CORE MATH ENGINE
# ==========================================
def calculate_quotation(raw_items: list, tax_mode: str = "INTRASTATE") -> pd.DataFrame:
    processed = []
    for item in raw_items:
        qty = float(item.get("Quantity", 0))
        unit_price = float(item.get("Unit Price (INR)", 0.0))
        subtotal = qty * unit_price
        
        if tax_mode == "INTRASTATE":
            cgst_rate, sgst_rate, igst_rate = 0.09, 0.09, 0.0
        else:
            cgst_rate, sgst_rate, igst_rate = 0.0, 0.0, 0.18

        cgst_amt = round(subtotal * cgst_rate, 2)
        sgst_amt = round(subtotal * sgst_rate, 2)
        igst_amt = round(subtotal * igst_rate, 2)
        total_tax = cgst_amt + sgst_amt + igst_amt
        line_total = subtotal + total_tax

        processed.append({
            "Description": item.get("Description", ""),
            "HSN Code": str(item.get("HSN Code", "")),
            "Qty": int(qty),
            "Unit Price (INR)": unit_price,
            "Subtotal (INR)": subtotal,
            "CGST 9% (INR)": cgst_amt,
            "SGST 9% (INR)": sgst_amt,
            "IGST 18% (INR)": igst_amt,
            "Total Tax (INR)": total_tax,
            "Line Total (INR)": line_total
        })

    return pd.DataFrame(processed)


# ==========================================
# 2. DYNAMIC PDF GENERATOR (IN-MEMORY)
# ==========================================
def generate_pdf_bytes(df: pd.DataFrame, meta: dict, terms_list: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    NAVY_PRIMARY = colors.HexColor("#1A365D")
    TEXT_DARK = colors.HexColor("#2D3748")
    BORDER_GREY = colors.HexColor("#CBD5E0")
    ALT_ROW_BG = colors.HexColor("#F7FAFC")

    title_style = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, textColor=NAVY_PRIMARY)
    hdr_label = ParagraphStyle('HdrLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=NAVY_PRIMARY)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, textColor=TEXT_DARK, leading=11)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=TEXT_DARK, leading=10)
    cell_bold = ParagraphStyle('CellB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_DARK, leading=10)
    th_style = ParagraphStyle('TH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.white, leading=10)

    story = []

    # Dynamic Header Banner
    header_data = [
        [
            Paragraph("IT PROCUREMENT QUOTATION", title_style),
            Paragraph(f"<b>Quotation #:</b> {meta['quotation_no']}<br/>"
                      f"<b>Date:</b> {meta['date']}<br/>"
                      f"<b>Valid Until:</b> {meta['valid_until']}", body_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[3.5 * inch, 3.7 * inch])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY_PRIMARY, spaceAfter=12))

    # Dynamic Vendor & Client Parties
    party_data = [
        [Paragraph("ISSUER (VENDOR)", hdr_label), Paragraph("PREPARED FOR (CLIENT)", hdr_label)],
        [
            Paragraph(f"<b>{meta['vendor_name']}</b><br/>{meta['vendor_addr'].replace('\n', '<br/>')}<br/><b>GSTIN:</b> {meta['vendor_gst']}", body_style),
            Paragraph(f"<b>{meta['client_name']}</b><br/>{meta['client_addr'].replace('\n', '<br/>')}<br/><b>GSTIN:</b> {meta['client_gst']}", body_style)
        ]
    ]
    party_table = Table(party_data, colWidths=[3.6 * inch, 3.6 * inch])
    party_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(party_table)
    story.append(Spacer(1, 12))

    # Column Formatting (Intrastate vs Interstate)
    if meta['tax_mode'] == "INTRASTATE":
        cols_to_render = ["Description", "HSN Code", "Qty", "Unit Price (INR)", "Subtotal (INR)", "CGST 9% (INR)", "SGST 9% (INR)", "Line Total (INR)"]
        col_widths = [1.8 * inch, 0.7 * inch, 0.4 * inch, 0.9 * inch, 0.9 * inch, 0.75 * inch, 0.75 * inch, 1.0 * inch]
    else:
        cols_to_render = ["Description", "HSN Code", "Qty", "Unit Price (INR)", "Subtotal (INR)", "IGST 18% (INR)", "Line Total (INR)"]
        col_widths = [2.2 * inch, 0.8 * inch, 0.4 * inch, 1.0 * inch, 1.0 * inch, 0.8 * inch, 1.0 * inch]

    table_content = [[Paragraph(col, th_style) for col in cols_to_render]]

    # Data Rows
    for _, row in df.iterrows():
        r_cells = []
        for col in cols_to_render:
            val = row[col]
            fmt_val = f"₹{val:,.2f}" if isinstance(val, (int, float)) and col not in ["Qty", "HSN Code"] else str(val)
            r_cells.append(Paragraph(fmt_val, cell_style))
        table_content.append(r_cells)

    # Grand Totals Row
    summary_row = []
    for col in cols_to_render:
        if col == "Description":
            summary_row.append(Paragraph("<b>GRAND TOTAL</b>", cell_bold))
        elif col in ["Qty", "HSN Code"]:
            summary_row.append(Paragraph("", cell_bold))
        else:
            summary_row.append(Paragraph(f"<b>₹{df[col].sum():,.2f}</b>", cell_bold))
    table_content.append(summary_row)

    item_table = Table(table_content, colWidths=col_widths, repeatRows=1)
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), NAVY_PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ('BOX', (0, 0), (-1, -1), 1, NAVY_PRIMARY),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#EDF2F7")),
    ]
    for r in range(1, len(table_content) - 1):
        if r % 2 == 0:
            t_style.append(('BACKGROUND', (0, r), (-1, r), ALT_ROW_BG))

    item_table.setStyle(TableStyle(t_style))
    story.append(item_table)
    story.append(Spacer(1, 15))

    # Dynamic Terms & Conditions Section
    terms_html = "<b>Terms & Conditions:</b><br/>"
    for idx, term in enumerate(terms_list, start=1):
        if term.strip():
            terms_html += f"{idx}. {term.strip()}<br/>"
    
    story.append(Paragraph(terms_html, body_style))
    
    doc.build(story)
    return buffer.getvalue()


# ==========================================
# 3. DYNAMIC UI CONTROLS
# ==========================================
st.title("⚡ Dynamic IT Quotation Generator")
st.markdown("Select an execution mode below or build your custom quotation dynamically.")

# Mode Switcher (Simulating Option 1 vs Option 2)
execution_mode = st.radio(
    "Select Execution Mode:",
    ["Option 1: Load Pre-populated Sample Data", "Option 2: Dynamic Custom Data Entry"],
    horizontal=True
)

st.divider()

# Sidebar Setup
st.sidebar.header("⚙️ Quotation Settings")

tax_selection = st.sidebar.radio("GST Structure", ["INTRASTATE (CGST 9% + SGST 9%)", "INTERSTATE (IGST 18%)"])
tax_mode = "INTRASTATE" if "INTRASTATE" in tax_selection else "INTERSTATE"

# Sidebar Metadata Inputs
quotation_no = st.sidebar.text_input("Quotation No.", "IT-QUO-2026-089")
issue_date = st.sidebar.date_input("Issue Date", datetime.today())
validity_days = st.sidebar.number_input("Validity Period (Days)", value=30, min_value=1)
valid_until = issue_date + timedelta(days=validity_days)

# Main Form Layout: Top Details
col_vendor, col_client = st.columns(2)

with col_vendor:
    st.subheader("🏢 Issuer (Vendor) Details")
    if "Option 1" in execution_mode:
        v_name = st.text_input("Vendor Company Name", "Apex Enterprise Technologies Solutions Pvt Ltd")
        v_addr = st.text_area("Vendor Address", "Plot 42, Electronics City Phase 1, Bengaluru, KA - 560100", height=70)
        v_gst = st.text_input("Vendor GSTIN", "29AAACA0000A1Z5")
    else:
        v_name = st.text_input("Vendor Company Name", "", placeholder="e.g. Acme Cloud Solutions")
        v_addr = st.text_area("Vendor Address", "", placeholder="Enter Vendor Street Address, City, Pincode...", height=70)
        v_gst = st.text_input("Vendor GSTIN", "", placeholder="e.g. 29AAACA0000A1Z5")

with col_client:
    st.subheader("👤 Client Details")
    if "Option 1" in execution_mode:
        c_name = st.text_input("Client Company Name", "Nexus Global Cloud Operations India Ltd")
        c_addr = st.text_area("Client Address", "Cyber City, Tower B, 8th Floor, Gurugram, HR - 122002", height=70)
        c_gst = st.text_input("Client GSTIN", "06AAACN1111B1Z2")
    else:
        c_name = st.text_input("Client Company Name", "", placeholder="e.g. Enterprise Client Ltd")
        c_addr = st.text_area("Client Address", "", placeholder="Enter Client Billing Address...", height=70)
        c_gst = st.text_input("Client GSTIN", "", placeholder="e.g. 06AAACN1111B1Z2")

st.divider()

# Main Form Layout: Line Items
st.subheader("📦 Line Items")
st.caption("Add, edit, or delete items using the dynamic table grid below.")

if "Option 1" in execution_mode:
    initial_items = [
        {"Description": "Dell Latitude 5440 Core i7 16GB RAM 512GB SSD", "HSN Code": "8471", "Quantity": 5, "Unit Price (INR)": 85000.00},
        {"Description": "Cisco Catalyst 24-Port Managed Gigabit Switch", "HSN Code": "8517", "Quantity": 2, "Unit Price (INR)": 42000.00},
        {"Description": "Logitech MX Keys & Mouse Enterprise Combo", "HSN Code": "8471", "Quantity": 5, "Unit Price (INR)": 12500.00},
        {"Description": "APC Smart-UPS 2200VA LCD 230V Tower", "HSN Code": "8504", "Quantity": 1, "Unit Price (INR)": 68000.00}
    ]
else:
    initial_items = [
        {"Description": "", "HSN Code": "8471", "Quantity": 1, "Unit Price (INR)": 0.0}
    ]

# Editable Dynamic Grid
edited_df = st.data_editor(
    pd.DataFrame(initial_items),
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Quantity": st.column_config.NumberColumn(min_value=1, step=1, default=1),
        "Unit Price (INR)": st.column_config.NumberColumn(min_value=0.0, format="₹%.2f", default=0.0),
        "HSN Code": st.column_config.TextColumn(default="8471"),
        "Description": st.column_config.TextColumn(default="Item Description")
    }
)

raw_line_items = [item for item in edited_df.to_dict(orient="records") if item.get("Description", "").strip()]

# Terms & Conditions Customizer
st.divider()
st.subheader("📜 Terms & Conditions")
terms_input = st.text_area(
    "Edit Terms & Conditions (One rule per line):",
    value=(
        "Payment: 50% advance along with Purchase Order; balance prior to delivery.\n"
        "GST: Input tax credit details registered under statutory compliance laws.\n"
        "Warranty: All hardware carries standard OEM warranty per component guidelines.\n"
        f"Validity: Quotation remains valid for {validity_days} calendar days from issue date."
    ),
    height=100
)
terms_list = terms_input.split("\n")

# Financial Calculation & Export Buttons
if raw_line_items:
    df_calc = calculate_quotation(raw_line_items, tax_mode=tax_mode)
    
    st.subheader("📊 Financial Overview")
    subtotal_val = df_calc["Subtotal (INR)"].sum()
    tax_val = df_calc["Total Tax (INR)"].sum()
    grand_total_val = df_calc["Line Total (INR)"].sum()

    m1, m2, m3 = st.columns(3)
    m1.metric("Subtotal (Excl. Tax)", f"₹{subtotal_val:,.2f}")
    m2.metric(f"Total GST ({'18%' if tax_mode == 'INTERSTATE' else '9%+9%'})", f"₹{tax_val:,.2f}")
    m3.metric("Grand Total (Incl. Tax)", f"₹{grand_total_val:,.2f}")

    meta = {
        "quotation_no": quotation_no,
        "date": issue_date.strftime("%d-%b-%Y"),
        "valid_until": valid_until.strftime("%d-%b-%Y"),
        "vendor_name": v_name if v_name else "Vendor Name",
        "vendor_addr": v_addr if v_addr else "Vendor Address",
        "vendor_gst": v_gst if v_gst else "N/A",
        "client_name": c_name if c_name else "Client Name",
        "client_addr": c_addr if c_addr else "Client Address",
        "client_gst": c_gst if c_gst else "N/A",
        "tax_mode": tax_mode
    }

    st.divider()
    st.subheader("📥 Export Documents")
    col_csv, col_pdf = st.columns(2)

    # CSV Download
    csv_bytes = df_calc.to_csv(index=False).encode('utf-8')
    col_csv.download_button(
        label="📄 Download Formatted CSV",
        data=csv_bytes,
        file_name=f"Quotation_{quotation_no}.csv",
        mime="text/csv",
        use_container_width=True
    )

    # PDF Download
    pdf_bytes = generate_pdf_bytes(df_calc, meta, terms_list)
    col_pdf.download_button(
        label="📕 Download PDF Quotation",
        data=pdf_bytes,
        file_name=f"Quotation_{quotation_no}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
else:
    st.warning("Please add at least one line item with a valid description to calculate metrics and export files.")