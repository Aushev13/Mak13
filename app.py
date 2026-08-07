import streamlit as st
import pandas as pd
import io
import pdfplumber
from PIL import Image
import re
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import tempfile
import os

st.set_page_config(page_title="Генератор КП", layout="wide")
st.title("📄 Генератор коммерческого предложения")

# ---------- Инициализация сессионных переменных ----------
if 'supplier' not in st.session_state:
st.session_state.supplier = {
'name': '',
'inn': '',
'kpp': '',
'address': '',
'phone': '',
'bank': ''
}

if 'logo_bytes' not in st.session_state:
st.session_state.logo_bytes = None
if 'signature_bytes' not in st.session_state:
st.session_state.signature_bytes = None
if 'stamp_bytes' not in st.session_state:
st.session_state.stamp_bytes = None

# ---------- Боковая панель ----------
with st.sidebar:
st.header("🏢 Ваши реквизиты")
supplier_name = st.text_input("Название организации", value=st.session_state.supplier['name'])
supplier_inn = st.text_input("ИНН", value=st.session_state.supplier['inn'])
supplier_kpp = st.text_input("КПП", value=st.session_state.supplier['kpp'])
supplier_address = st.text_input("Адрес", value=st.session_state.supplier['address'])
supplier_phone = st.text_input("Телефон", value=st.session_state.supplier['phone'])
supplier_bank = st.text_area("Банковские реквизиты", value=st.session_state.supplier['bank'], height=68)
if st.button("Сохранить реквизиты"):
st.session_state.supplier['name'] = supplier_name
st.session_state.supplier['inn'] = supplier_inn
st.session_state.supplier['kpp'] = supplier_kpp
st.session_state.supplier['address'] = supplier_address
st.session_state.supplier['phone'] = supplier_phone
st.session_state.supplier['bank'] = supplier_bank
st.success("✅ Реквизиты сохранены!")

st.divider()
st.header("🖼️ Загрузить изображения")
logo_file = st.file_uploader("Логотип (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo")
if logo_file:
st.session_state.logo_bytes = logo_file.getvalue()
st.image(logo_file, width=100, caption="Логотип загружен")

signature_file = st.file_uploader("Подпись (PNG/JPG)", type=["png", "jpg", "jpeg"], key="signature")
if signature_file:
st.session_state.signature_bytes = signature_file.getvalue()
st.image(signature_file, width=100, caption="Подпись загружена")

stamp_file = st.file_uploader("Печать (PNG/JPG)", type=["png", "jpg", "jpeg"], key="stamp")
if stamp_file:
st.session_state.stamp_bytes = stamp_file.getvalue()
st.image(stamp_file, width=100, caption="Печать загружена")

st.subheader("Подпись (текст)")
sign_position = st.text_input("Должность", "Генеральный директор")
sign_name = st.text_input("ФИО", "Иванов И.И.")

# ---------- Основная часть ----------
col1, col2 = st.columns(2)
with col1:
uploaded_file = st.file_uploader("Загрузите накладную (XLSX или PDF)", type=["xlsx", "pdf"])
with col2:
st.subheader("Покупатель")
buyer_name = st.text_input("Название организации покупателя")
buyer_inn = st.text_input("ИНН покупателя")

markup_percent = st.slider("Наценка (%)", 0, 200, 25, key="markup")

# ---------- Функции ----------
def extract_table_from_pdf(pdf_file):
with pdfplumber.open(pdf_file) as pdf:
all_rows = []
for page in pdf.pages:
tables = page.extract_tables()
for table in tables:
for row in table:
if row and any(cell and str(cell).strip() for cell in row):
all_rows.append([str(cell).strip() if cell else '' for cell in row])
if not all_rows:
return None
headers = all_rows[0]
data = all_rows[1:]
df = pd.DataFrame(data, columns=headers)
return df

def normalize_columns(df):
df.columns = [col.lower().strip() for col in df.columns]
col_map = {}
for col in df.columns:
if 'наимен' in col or 'товар' in col or 'назван' in col:
col_map['Наименование'] = col
elif 'количеств' in col or 'кол-во' in col or 'кол' in col:
col_map['Количество'] = col
elif 'цена' in col and 'за' in col:
col_map['Цена'] = col
elif 'сумма' in col:
col_map['Сумма'] = col
elif 'ед' in col or 'изм' in col:
col_map['Ед. изм.'] = col
elif '№' in col or 'п/п' in col:
col_map['№'] = col
rename_dict = {v: k for k, v in col_map.items() if k in ['Наименование', 'Количество', 'Цена', 'Сумма', 'Ед. изм.', '№']}
df = df.rename(columns=rename_dict)
required = ['Наименование', 'Количество', 'Цена', 'Сумма']
for col in required:
if col not in df.columns:
st.error(f"❌ Не найдена колонка '{col}'. Проверьте заголовки файла.")
return None
for col in ['Количество', 'Цена', 'Сумма']:
df[col] = df[col].astype(str).str.replace(',', '.').str.replace(' ', '')
df[col] = pd.to_numeric(df[col], errors='coerce')
df = df.dropna(subset=['Количество', 'Цена', 'Сумма'])
return df

def generate_pdf(df, markup, old_total, new_total, supplier, buyer_name, buyer_inn,
logo_bytes, signature_bytes, stamp_bytes, sign_position, sign_name):
buffer = io.BytesIO()
doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
leftMargin=15*mm, rightMargin=15*mm,
topMargin=20*mm, bottomMargin=15*mm)
elements = []
styles = getSampleStyleSheet()

title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, spaceAfter=6)
header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=9, textColor=colors.grey)
company_style = ParagraphStyle('Company', parent=styles['Normal'], fontSize=10, leading=12)
cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8)
total_style = ParagraphStyle('Total', parent=styles['Normal'], fontSize=12, alignment=TA_RIGHT, spaceBefore=10)

# Логотип
logo_img = None
if logo_bytes:
with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
tmp.write(logo_bytes)
tmp_path = tmp.name
logo_img = RLImage(tmp_path, width=30*mm, height=20*mm, hAlign='RIGHT')
os.unlink(tmp_path)

supplier_text = f"<b>Поставщик:</b> {supplier['name']}<br/>"
if supplier['inn']:
supplier_text += f"ИНН {supplier['inn']}"
if supplier['kpp']:
supplier_text += f", КПП {supplier['kpp']}"
if supplier['address']:
supplier_text += f"<br/>{supplier['address']}"
if supplier['phone']:
supplier_text += f"<br/>тел. {supplier['phone']}"
if supplier['bank']:
supplier_text += f"<br/>{supplier['bank']}"
left_part = Paragraph(supplier_text, company_style)

header_data = [[left_part, logo_img if logo_img else '']]
header_table = Table(header_data, colWidths=[130*mm, 40*mm])
header_table.setStyle(TableStyle([
('VALIGN', (0,0), (-1,-1), 'TOP'),
('ALIGN', (1,0), (1,0), 'RIGHT'),
]))
elements.append(header_table)
elements.append(Spacer(1, 3*mm))

buyer_text = f"<b>Покупатель:</b> {buyer_name}" if buyer_name else ""
if buyer_inn:
buyer_text += f", ИНН {buyer_inn}"
if buyer_text:
elements.append(Paragraph(buyer_text, company_style))
elements.append(Spacer(1, 2*mm))

elements.append(Paragraph("КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ", title_style))
elements.append(Paragraph(f"На основании накладной № ___ от 24.07.2026", header_style))
elements.append(Paragraph(f"Наценка: {markup}%", header_style))
elements.append(Spacer(1, 5*mm))

# Таблица
data = []
headers = ['№', 'Наименование', 'Кол-во', 'Ед.', 'Цена (была)', 'Цена (стала)', 'Сумма (была)', 'Сумма (стала)']
data.append([Paragraph(h, cell_style) for h in headers])

for idx, row in df.iterrows():
new_price = row['Цена'] * (1 + markup / 100)
new_sum = row['Сумма'] * (1 + markup / 100)
row_data = [
Paragraph(str(row.get('№', idx+1)), cell_style),
Paragraph(str(row['Наименование']), cell_style),
Paragraph(str(int(row['Количество'])) if row['Количество'] == int(row['Количество']) else str(row['Количество']), cell_style),
Paragraph(str(row.get('Ед. изм.', 'шт')), cell_style),
Paragraph(f"{row['Цена']:.2f}", cell_style),
Paragraph(f"{new_price:.2f}", cell_style),
Paragraph(f"{row['Сумма']:.2f}", cell_style),
Paragraph(f"{new_sum:.2f}", cell_style)
]
data.append(row_data)

data.append([
Paragraph('<b>ИТОГО</b>', cell_style), '', '', '',
Paragraph(f"<b>{old_total:.2f}</b>", cell_style),
Paragraph(f"<b>{new_total:.2f}</b>", cell_style),
Paragraph(f"<b>{old_total:.2f}</b>", cell_style),
Paragraph(f"<b>{new_total:.2f}</b>", cell_style)
])

table = Table(data, colWidths=[12*mm, 55*mm, 12*mm, 12*mm, 22*mm, 22*mm, 25*mm, 25*mm], repeatRows=1)
table.setStyle(TableStyle([
('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
('ALIGN', (0, 0), (-1, -1), 'CENTER'),
('ALIGN', (1, 0), (1, -1), 'LEFT'),
('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
('FONTSIZE', (0, 0), (-1, 0), 9),
('BOTTOMPADDING', (0, 0), (-1, 0), 6),
('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
('BOX', (0, 0), (-1, -1), 1, colors.black),
]))

elements.append(table)
elements.append(Spacer(1, 5*mm))
elements.append(Paragraph(f"<b>Итого к оплате:</b> {new_total:,.2f} руб.", total_style))
elements.append(Paragraph(f"<i>Сумма прописью: {int(new_total)} рублей 00 копеек</i>", header_style))

# Подпись и печать
elements.append(Spacer(1, 8*mm))
sig_img = None
if signature_bytes:
with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
tmp.write(signature_bytes)
tmp_path = tmp.name
sig_img = RLImage(tmp_path, width=30*mm, height=15*mm)
os.unlink(tmp_path)
stamp_img = None
if stamp_bytes:
with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
tmp.write(stamp_bytes)
tmp_path = tmp.name
stamp_img = RLImage(tmp_path, width=20*mm, height=20*mm)
os.unlink(tmp_path)

left_sig = []
if sig_img:
left_sig.append(sig_img)
if stamp_img:
left_sig.append(stamp_img)
if left_sig:
sig_table = Table([[left_sig[0]]] if len(left_sig)==1 else [[left_sig[0], left_sig[1]]])
sig_table.setStyle(TableStyle([
('ALIGN', (0,0), (-1,-1), 'CENTER'),
('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
]))
left_part = sig_table
else:
left_part = Paragraph("(подпись и печать)", header_style)

right_text = f"<b>{sign_position}</b><br/>{sign_name}"
right_part = Paragraph(right_text, company_style)

sig_data = [[left_part, right_part]]
sig_table = Table(sig_data, colWidths=[80*mm, 50*mm])
sig_table.setStyle(TableStyle([
('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
('ALIGN', (0,0), (0,0), 'CENTER'),
('ALIGN', (1,0), (1,0), 'RIGHT'),
]))
elements.append(sig_table)

doc.build(elements)
buffer.seek(0)
return buffer

# ---------- Основной процесс ----------
if uploaded_file is not None:
file_extension = uploaded_file.name.split('.')[-1].lower()
try:
if file_extension == 'xlsx':
df = pd.read_excel(uploaded_file, engine='openpyxl')
elif file_extension == 'pdf':
df = extract_table_from_pdf(uploaded_file)
if df is None:
st.error("❌ Не удалось извлечь таблицу из PDF. Убедитесь, что PDF содержит текстовую таблицу (не скан).")
st.stop()
else:
st.error("❌ Неподдерживаемый формат. В облачной версии работают только Excel и текстовые PDF. Фото и сканы не поддерживаются.")
st.stop()

st.subheader("📄 Исходные данные (извлечённые)")
st.dataframe(df)

df = normalize_columns(df)
if df is None:
st.stop()

old_total = df["Сумма"].sum()
new_total = old_total * (1 + markup_percent / 100)

col1, col2, col3 = st.columns(3)
col1.metric("Старая сумма", f"{old_total:,.2f} ₽")
col2.metric("Новая сумма", f"{new_total:,.2f} ₽", delta=f"{new_total - old_total:,.2f} ₽")

if not st.session_state.supplier['name']:
st.warning("⚠️ Заполните реквизиты поставщика в боковой панели.")
if not buyer_name:
st.warning("⚠️ Укажите название покупателя.")

if st.button("Сформировать КП", type="primary"):
pdf_buffer = generate_pdf(
df, markup_percent, old_total, new_total,
st.session_state.supplier,
buyer_name, buyer_inn,
st.session_state.logo_bytes,
st.session_state.signature_bytes,
st.session_state.stamp_bytes,
sign_position, sign_name
)
st.download_button(
label="📥 Скачать КП (PDF)",
data=pdf_buffer,
file_name="Kommercheskoe_predlozhenie.pdf",
mime="application/pdf"
)
except Exception as e:
st.error(f"Ошибка: {e}")
else:
st.info("Загрузите накладную (Excel или текстовый PDF), укажите реквизиты и сформируйте КП.")