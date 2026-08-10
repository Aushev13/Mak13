import streamlit as st
import pandas as pd
import io
import pdfplumber
import re
import tempfile
import os
import json
import base64
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

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
if 'payment_terms' not in st.session_state:
    st.session_state.payment_terms = ''
if 'kp_number' not in st.session_state:
    st.session_state.kp_number = ''
if 'kp_date' not in st.session_state:
    st.session_state.kp_date = datetime.today().strftime('%d.%m.%Y')
if 'last_kp_number' not in st.session_state:
    st.session_state.last_kp_number = 0
if 'normalized_df' not in st.session_state:
    st.session_state.normalized_df = None
if 'uploaded_filename' not in st.session_state:
    st.session_state.uploaded_filename = None

# ---------- Боковая панель ----------
with st.sidebar:
    st.header("🏢 Ваши реквизиты")
    supplier_name = st.text_input("Название организации", value=st.session_state.supplier['name'])
    supplier_inn = st.text_input("ИНН", value=st.session_state.supplier['inn'])
    supplier_kpp = st.text_input("КПП", value=st.session_state.supplier['kpp'])
    supplier_address = st.text_input("Адрес", value=st.session_state.supplier['address'])
    supplier_phone = st.text_input("Телефон", value=st.session_state.supplier['phone'])
    supplier_bank = st.text_area("Банковские реквизиты", value=st.session_state.supplier['bank'], height=68)
    payment_terms = st.text_area("Условия оплаты и доставки", value=st.session_state.payment_terms, height=68)
    if st.button("Сохранить реквизиты"):
        st.session_state.supplier['name'] = supplier_name
        st.session_state.supplier['inn'] = supplier_inn
        st.session_state.supplier['kpp'] = supplier_kpp
        st.session_state.supplier['address'] = supplier_address
        st.session_state.supplier['phone'] = supplier_phone
        st.session_state.supplier['bank'] = supplier_bank
        st.session_state.payment_terms = payment_terms
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
    sign_position = st.text_input("Должность", value=st.session_state.get('sign_position', 'Генеральный директор'))
    sign_name = st.text_input("ФИО", value=st.session_state.get('sign_name', 'Иванов И.И.'))
    if sign_position != st.session_state.get('sign_position') or sign_name != st.session_state.get('sign_name'):
        st.session_state['sign_position'] = sign_position
        st.session_state['sign_name'] = sign_name
    st.divider()
    st.header("💾 Профиль")
    def save_profile():
        profile = {
            'supplier': st.session_state.supplier,
            'payment_terms': st.session_state.payment_terms,
            'last_kp_number': st.session_state.last_kp_number,
            'logo': base64.b64encode(st.session_state.logo_bytes).decode('utf-8') if st.session_state.logo_bytes else None,
            'signature': base64.b64encode(st.session_state.signature_bytes).decode('utf-8') if st.session_state.signature_bytes else None,
            'stamp': base64.b64encode(st.session_state.stamp_bytes).decode('utf-8') if st.session_state.stamp_bytes else None,
            'sign_position': st.session_state.get('sign_position', 'Генеральный директор'),
            'sign_name': st.session_state.get('sign_name', 'Иванов И.И.')
        }
        return json.dumps(profile, ensure_ascii=False, indent=2)
    if st.button("Сохранить профиль"):
        profile_json = save_profile()
        st.download_button(label="📥 Скачать JSON", data=profile_json, file_name="profile.json", mime="application/json")
    profile_file = st.file_uploader("Загрузить профиль (JSON)", type=["json"])
    if profile_file:
        try:
            data = json.loads(profile_file.read().decode('utf-8'))
            st.session_state.supplier = data.get('supplier', st.session_state.supplier)
            st.session_state.payment_terms = data.get('payment_terms', '')
            st.session_state.last_kp_number = data.get('last_kp_number', 0)
            for key, field in [('logo', 'logo_bytes'), ('signature', 'signature_bytes'), ('stamp', 'stamp_bytes')]:
                if data.get(key):
                    st.session_state[field] = base64.b64decode(data[key])
                else:
                    st.session_state[field] = None
            st.session_state['sign_position'] = data.get('sign_position', 'Генеральный директор')
            st.session_state['sign_name'] = data.get('sign_name', 'Иванов И.И.')
            st.success("✅ Профиль загружен!")
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка загрузки профиля: {e}")

# ---------- Основная часть ----------
col1, col2 = st.columns(2)
with col1:
    uploaded_file = st.file_uploader("Загрузите накладную (XLSX или PDF)", type=["xlsx", "pdf"])
with col2:
    st.subheader("Покупатель")
    buyer_name = st.text_input("Название организации покупателя")
    buyer_inn = st.text_input("ИНН покупателя")
    buyer_email = st.text_input("Email покупателя (для отправки КП)")

next_number = st.session_state.last_kp_number + 1
col3, col4 = st.columns(2)
with col3:
    kp_number = st.text_input("№ КП", value=str(next_number))
with col4:
    kp_date = st.text_input("Дата КП", value=st.session_state.kp_date)

markup_percent = st.slider("Наценка (%)", 0, 200, 25, key="markup")

# ---------- Функции обработки ----------
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
        return pd.DataFrame(data, columns=headers)

def normalize_columns_auto(df):
    df.columns = [col.lower().strip() for col in df.columns]
    col_map = {}
    for col in df.columns:
        if 'наимен' in col or 'товар' in col or 'назван' in col or 'описан' in col:
            col_map['Наименование'] = col
        elif 'количеств' in col or 'кол-во' in col or 'кол' in col:
            col_map['Количество'] = col
        elif 'цена' in col and 'за' in col:
            col_map['Цена'] = col
        elif 'сумма' in col:
            col_map['Сумма'] = col
        elif 'ед' in col or 'изм' in col:
            col_map['Ед. изм.'] = col
        elif '№' in col or 'п/п' in col or 'номер' in col:
            col_map['№'] = col

    required = ['Наименование', 'Количество', 'Цена', 'Сумма']
    missing = [r for r in required if r not in col_map]
    if missing:
        return None

    rename_dict = {v: k for k, v in col_map.items() if k in required}
    df = df.rename(columns=rename_dict)
    for col in ['Количество', 'Цена', 'Сумма']:
        df[col] = df[col].astype(str).str.replace(',', '.').str.replace(' ', '')
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['Количество', 'Цена', 'Сумма'])
    if 'Ед. изм.' in col_map and col_map['Ед. изм.']:
        df['Ед. изм.'] = df[col_map['Ед. изм.']]
    else:
        df['Ед. изм.'] = 'шт'
    return df

def apply_manual_mapping(df, col_map):
    rename_dict = {v: k for k, v in col_map.items() if k in ['Наименование', 'Количество', 'Цена', 'Сумма']}
    df = df.rename(columns=rename_dict)
    required = ['Наименование', 'Количество', 'Цена', 'Сумма']
    df = df[required]
    for col in ['Количество', 'Цена', 'Сумма']:
        df[col] = df[col].astype(str).str.replace(',', '.').str.replace(' ', '')
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['Количество', 'Цена', 'Сумма'])
    if 'Ед. изм.' in col_map and col_map['Ед. изм.'] and col_map['Ед. изм.'] in df.columns:
        df['Ед. изм.'] = df[col_map['Ед. изм.']]
    else:
        df['Ед. изм.'] = 'шт'
    return df

def generate_pdf(df, markup, old_total, new_total, supplier, buyer_name, buyer_inn,
                 logo_bytes, signature_bytes, stamp_bytes, sign_position, sign_name,
                 kp_number, kp_date, payment_terms):
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
    terms_style = ParagraphStyle('Terms', parent=styles['Normal'], fontSize=9, spaceBefore=5)
    # Логотип
    logo_img = None
    if logo_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(logo_bytes)
            tmp_path = tmp.name
        logo_img = RLImage(tmp_path, width=30*mm, height=20*mm, hAlign='RIGHT')
        os.unlink(tmp_path)
    # Поставщик
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
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (1,0), (1,0), 'RIGHT')]))
    elements.append(header_table)
    elements.append(Spacer(1, 3*mm))
    # Покупатель
    buyer_text = f"<b>Покупатель:</b> {buyer_name}" if buyer_name else ""
    if buyer_inn:
        buyer_text += f", ИНН {buyer_inn}"
    if buyer_text:
        elements.append(Paragraph(buyer_text, company_style))
        elements.append(Spacer(1, 2*mm))
    # Заголовок
    title_text = "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ"
    if kp_number:
        title_text += f" № {kp_number}"
    elements.append(Paragraph(title_text, title_style))
    if kp_date:
        elements.append(Paragraph(f"от {kp_date}", header_style))
    elements.append(Paragraph(f"Наценка: {markup}%", header_style))
    elements.append(Spacer(1, 5*mm))
    # Таблица
    data = []
    headers = ['№', 'Наименование', 'Кол-во', 'Ед.', 'Цена (была)', 'Цена (стала)', 'Сумма (была)', 'Сумма (стала)']
    data.append([Paragraph(h, cell_style) for h in headers])
    for idx, row in df.iterrows():
        new_price = row['Цена'] * (1 + markup/100)
        new_sum = row['Сумма'] * (1 + markup/100)
        row_data = [
            Paragraph(str(row.get('№', idx+1)), cell_style),
            Paragraph(str(row['Наименование']), cell_style),
            Paragraph(str(int(row['Количество'])) if row['Количество']==int(row['Количество']) else str(row['Количество']), cell_style),
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
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (1,0), (1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#ecf0f1')),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-2), 0.5, colors.grey),
        ('BOX', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph(f"<b>Итого к оплате:</b> {new_total:,.2f} руб.", total_style))
    elements.append(Paragraph(f"<i>Сумма прописью: {int(new_total)} рублей 00 копеек</i>", header_style))
    # Условия
    if payment_terms:
        elements.append(Spacer(1, 3*mm))
        elements.append(Paragraph("<b>Условия оплаты и доставки:</b>", header_style))
        elements.append(Paragraph(payment_terms.replace('\n', '<br/>'), terms_style))
    # Подпись
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
    if sig_img: left_sig.append(sig_img)
    if stamp_img: left_sig.append(stamp_img)
    if left_sig:
        sig_table = Table([[left_sig[0]]] if len(left_sig)==1 else [[left_sig[0], left_sig[1]]])
        sig_table.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'), ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        left_part = sig_table
    else:
        left_part = Paragraph("(подпись и печать)", header_style)
    right_text = f"<b>{sign_position}</b><br/>{sign_name}"
    right_part = Paragraph(right_text, company_style)
    sig_data = [[left_part, right_part]]
    sig_table = Table(sig_data, colWidths=[80*mm, 50*mm])
    sig_table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'BOTTOM'), ('ALIGN',(0,0),(0,0),'CENTER'), ('ALIGN',(1,0),(1,0),'RIGHT')]))
    elements.append(sig_table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ---------- Основной процесс ----------
if uploaded_file is not None:
    current_filename = uploaded_file.name
    if st.session_state.uploaded_filename != current_filename:
        st.session_state.normalized_df = None
        st.session_state.uploaded_filename = current_filename

    file_extension = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_extension == 'xlsx':
            df_raw = pd.read_excel(uploaded_file, engine='openpyxl')
        elif file_extension == 'pdf':
            df_raw = extract_table_from_pdf(uploaded_file)
            if df_raw is None:
                st.error("❌ Не удалось извлечь таблицу из PDF. Убедитесь, что PDF текстовый (не скан).")
                st.stop()
        else:
            st.error("❌ Неподдерживаемый формат. Только XLSX и PDF.")
            st.stop()

        st.subheader("📄 Данные из файла (сырые)")
        st.dataframe(df_raw.head(10))

        if st.session_state.normalized_df is None:
            df_norm = normalize_columns_auto(df_raw)
            if df_norm is not None:
                st.session_state.normalized_df = df_norm
                st.rerun()
            else:
                st.warning("Не удалось автоматически определить колонки. Выберите соответствие вручную:")
                cols = list(df_raw.columns)
                col_name = st.selectbox("Выберите колонку для 'Наименование'", options=[''] + cols, key='manual_name')
                col_qty = st.selectbox("Выберите колонку для 'Количество'", options=[''] + cols, key='manual_qty')
                col_price = st.selectbox("Выберите колонку для 'Цена'", options=[''] + cols, key='manual_price')
                col_sum = st.selectbox("Выберите колонку для 'Сумма'", options=[''] + cols, key='manual_sum')
                col_unit = st.selectbox("Выберите колонку для 'Ед. изм.' (необязательно)", options=[''] + cols, key='manual_unit')

                if st.button("Применить ручное сопоставление"):
                    if not all([col_name, col_qty, col_price, col_sum]):
                        st.error("❌ Выберите все обязательные колонки (Наименование, Количество, Цена, Сумма).")
                    else:
                        mapping = {
                            'Наименование': col_name,
                            'Количество': col_qty,
                            'Цена': col_price,
                            'Сумма': col_sum
                        }
                        if col_unit:
                            mapping['Ед. изм.'] = col_unit
                        df = apply_manual_mapping(df_raw, mapping)
                        if df is not None:
                            st.session_state.normalized_df = df
                            st.rerun()
                        else:
                            st.error("Ошибка при применении маппинга. Проверьте данные.")
        else:
            df = st.session_state.normalized_df
            st.subheader("✏️ Редактирование данных")
            if '№' not in df.columns:
                df.insert(0, '№', range(1, len(df)+1))
            df['№'] = df['№'].astype(int)
            edited_df = st.data_editor(
                df,
                column_config={
                    "№": st.column_config.NumberColumn("№", disabled=True),
                    "Наименование": st.column_config.TextColumn("Наименование"),
                    "Количество": st.column_config.NumberColumn("Кол-во", min_value=0, step=1),
                    "Ед. изм.": st.column_config.TextColumn("Ед."),
                    "Цена": st.column_config.NumberColumn("Цена (была)", min_value=0, step=0.01, format="%.2f"),
                    "Сумма": st.column_config.NumberColumn("Сумма", disabled=True, format="%.2f"),
                },
                num_rows="dynamic",
                key="editor"
            )
            if not edited_df.empty:
                edited_df["Сумма"] = edited_df["Количество"] * edited_df["Цена"]
                df = edited_df

            old_total = df["Сумма"].sum()
            new_total = old_total * (1 + markup_percent/100)
            col1, col2, col3 = st.columns(3)
            col1.metric("Старая сумма", f"{old_total:,.2f} ₽")
            col2.metric("Новая сумма", f"{new_total:,.2f} ₽", delta=f"{new_total - old_total:,.2f} ₽")

            if not st.session_state.supplier['name']:
                st.warning("⚠️ Заполните реквизиты поставщика в боковой панели.")
            if not buyer_name:
                st.warning("⚠️ Укажите название покупателя.")

            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("📥 Скачать КП", type="primary"):
                    st.session_state.kp_number = kp_number
                    st.session_state.kp_date = kp_date
                    try:
                        entered_num = int(kp_number) if kp_number else 0
                        if entered_num > st.session_state.last_kp_number:
                            st.session_state.last_kp_number = entered_num
                        else:
                            st.session_state.last_kp_number += 1
                    except:
                        st.session_state.last_kp_number += 1
                    pdf_buffer = generate_pdf(
                        df, markup_percent, old_total, new_total,
                        st.session_state.supplier, buyer_name, buyer_inn,
                        st.session_state.logo_bytes, st.session_state.signature_bytes, st.session_state.stamp_bytes,
                        sign_position, sign_name, kp_number, kp_date,
                        st.session_state.payment_terms
                    )
                    st.download_button(
                        label="📥 Скачать PDF",
                        data=pdf_buffer,
                        file_name=f"KP_{kp_number if kp_number else 'без_номера'}.pdf",
                        mime="application/pdf"
                    )
            with col_btn2:
                if st.button("📧 Отправить на почту"):
                    if not buyer_email:
                        st.warning("Укажите email покупателя.")
                    elif not st.session_state.supplier['name']:
                        st.warning("Заполните реквизиты поставщика.")
                    else:
                        st.info(f"📧 Отправка на {buyer_email} ... (в реальном приложении добавьте SMTP)")
            with col_btn3:
                if st.button("🔗 Получить ссылку"):
                    st.info("🔗 Демо-ссылка: https://disk.yandex.ru/d/example (в реальном приложении загрузите на Яндекс Диск)")

    except Exception as e:
        st.error(f"Ошибка: {e}")
else:
    st.session_state.normalized_df = None
    st.info("Загрузите накладную (Excel или PDF), и приложение поможет вам сопоставить колонки.")