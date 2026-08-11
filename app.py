import streamlit as st
import pandas as pd
import io
import pdfplumber
import re
import tempfile
import os
import json
import base64
import urllib.request
import shutil
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Функция для получения шрифта с поддержкой кириллицы ---
def get_cyrillic_font():
    """
    Возвращает имя зарегистрированного шрифта для кириллицы.
    Сначала проверяет системные пути, если нет — скачивает DejaVuSans из интернета.
    """
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/System/Library/Fonts/Supplemental/Arial.ttf',  # macOS
        'C:/Windows/Fonts/arial.ttf'  # Windows
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('CyrillicFont', path))
                return 'CyrillicFont'
            except:
                continue
    
    # Если ни один системный шрифт не найден, скачиваем DejaVuSans из интернета
    try:
        url = 'https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf'
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ttf') as tmp:
            urllib.request.urlretrieve(url, tmp.name)
            pdfmetrics.registerFont(TTFont('CyrillicFont', tmp.name))
            return 'CyrillicFont'
    except:
        # Если скачать не удалось, используем встроенный Times-Roman (но кириллица не будет работать)
        st.warning("⚠️ Не удалось загрузить шрифт для кириллицы. Буквы могут отображаться квадратами.")
        return 'Times-Roman'

# Регистрируем шрифт один раз при старте
FONT_NAME = get_cyrillic_font()

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
    st.header("🏢 Реквизиты поставщика")
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
    buyer_email = st.text_input("Email для отправки КП")

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
    # Приводим названия колонок к нижнему регистру и чистим
    df.columns = [str(col).lower().strip().replace(' ', '').replace('_', '').replace('.', '').replace('№', 'n') for col in df.columns]
    
    synonyms = {
        'Наименование': ['наименование', 'наимен', 'товар', 'название', 'номенклатура', 'описание', 'продукт', 'материал', 'name', 'product', 'description', 'item'],
        'Количество': ['количество', 'колво', 'кол', 'к-во', 'количество', 'qty', 'quantity', 'count', 'number'],
        'Цена': ['цена', 'цен', 'стоимость', 'price', 'cost', 'value'],
        'Сумма': ['сумма', 'итого', 'всего', 'total', 'amount', 'sum'],
        'Ед. изм.': ['единица', 'ед', 'ед.изм', 'измерение', 'unit', 'uom', 'measure']
    }
    
    col_map = {}
    for target, variants in synonyms.items():
        for col in df.columns:
            if any(variant in col for variant in variants):
                col_map[target] = col
                break
    
    required = ['Наименование', 'Количество', 'Цена', 'Сумма']
    missing = [r for r in required if r not in col_map]
    
    if missing:
        # Пробуем найти по типу данных
        for col in df.columns:
            if col in col_map.values():
                continue
            if col not in col_map and 'Наименование' in missing:
                if df[col].dtype == 'object' and df[col].astype(str).str.len().mean() > 5:
                    col_map['Наименование'] = col
                    missing.remove('Наименование')
                    continue
            if col not in col_map:
                try:
                    numeric = pd.to_numeric(df[col], errors='coerce')
                    if numeric.notna().sum() > 0:
                        if numeric.nunique() > 10:
                            if 'Цена' in missing:
                                col_map['Цена'] = col
                                missing.remove('Цена')
                            elif 'Сумма' in missing:
                                col_map['Сумма'] = col
                                missing.remove('Сумма')
                        else:
                            if 'Количество' in missing:
                                col_map['Количество'] = col
                                missing.remove('Количество')
                except:
                    pass
    
    if missing:
        text_cols = [col for col in df.columns if df[col].dtype == 'object']
        num_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col]) or pd.to_numeric(df[col], errors='coerce').notna().any()]
        
        if 'Наименование' in missing and text_cols:
            col_map['Наименование'] = text_cols[0]
            missing.remove('Наименование')
        if 'Количество' in missing and num_cols:
            col_map['Количество'] = num_cols[0] if len(num_cols) > 0 else None
            missing.remove('Количество')
        if 'Цена' in missing and len(num_cols) > 1:
            col_map['Цена'] = num_cols[1]
            missing.remove('Цена')
        elif 'Цена' in missing and num_cols:
            col_map['Цена'] = num_cols[-1]
            missing.remove('Цена')
        if 'Сумма' in missing and len(num_cols) > 2:
            col_map['Сумма'] = num_cols[2]
            missing.remove('Сумма')
        elif 'Сумма' in missing and num_cols:
            col_map['Сумма'] = num_cols[-1]
            missing.remove('Сумма')
    
    if missing:
        st.error(f"❌ Не удалось автоматически определить колонки: {', '.join(missing)}. "
                 f"Пожалуйста, переименуйте колонки в файле: "
                 f"Наименование, Количество, Цена, Сумма (и, опционально, Ед. изм.).")
        return None
    
    rename_dict = {v: k for k, v in col_map.items() if k in required + ['Ед. изм.']}
    df = df.rename(columns=rename_dict)
    keep_cols = ['Наименование', 'Количество', 'Цена', 'Сумма']
    if 'Ед. изм.' in rename_dict.values():
        keep_cols.append('Ед. изм.')
    df = df[keep_cols]
    
    for col in ['Количество', 'Цена', 'Сумма']:
        df[col] = df[col].astype(str).str.replace(',', '.').str.replace(' ', '')
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['Количество', 'Цена', 'Сумма'])
    
    if 'Ед. изм.' not in df.columns:
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

    # Используем зарегистрированный шрифт с поддержкой кириллицы
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, spaceAfter=6, fontName=FONT_NAME)
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=9, textColor=colors.grey, fontName=FONT_NAME)
    company_style = ParagraphStyle('Company', parent=styles['Normal'], fontSize=10, leading=12, fontName=FONT_NAME)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, fontName=FONT_NAME)

    logo_img = None
    if logo_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(logo_bytes)
            tmp_path = tmp.name
        logo_img = RLImage(tmp_path, width=25*mm, height=20*mm, hAlign='RIGHT')
        os.unlink(tmp_path)

    supplier_text = f"<b>{supplier['name']}</b><br/>"
    if supplier['address']:
        supplier_text += f"{supplier['address']}<br/>"
    if supplier['inn']:
        supplier_text += f"ИНН {supplier['inn']}"
    if supplier['kpp']:
        supplier_text += f" / КПП {supplier['kpp']}"
    if supplier['phone']:
        supplier_text += f" / {supplier['phone']}"
    if supplier['bank']:
        supplier_text += f"<br/>{supplier['bank']}"
    left_part = Paragraph(supplier_text, company_style)

    header_data = [[left_part, logo_img if logo_img else '']]
    header_table = Table(header_data, colWidths=[130*mm, 40*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME)
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 3*mm))

    buyer_text = f"<b>Покупатель:</b> {buyer_name}" if buyer_name else ""
    if buyer_inn:
        buyer_text += f", ИНН {buyer_inn}"
    if buyer_text:
        elements.append(Paragraph(buyer_text, company_style))
        elements.append(Spacer(1, 2*mm))

    title_text = "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ"
    if kp_number:
        title_text += f" № {kp_number}"
    elements.append(Paragraph(title_text, title_style))
    if kp_date:
        elements.append(Paragraph(f"от {kp_date}", header_style))
    elements.append(Spacer(1, 5*mm))

    data = []
    headers = ['№', 'Наименование', 'Ед. изм.', 'Количество', 'Цена', 'Сумма']
    data.append([Paragraph(h, cell_style) for h in headers])

    for idx, row in df.iterrows():
        new_price = row['Цена'] * (1 + markup/100)
        new_sum = row['Сумма'] * (1 + markup/100)
        row_data = [
            Paragraph(str(row.get('№', idx+1)), cell_style),
            Paragraph(str(row['Наименование']), cell_style),
            Paragraph(str(row.get('Ед. изм.', 'шт')), cell_style),
            Paragraph(str(int(row['Количество'])) if row['Количество']==int(row['Количество']) else str(row['Количество']), cell_style),
            Paragraph(f"{new_price:,.2f}".replace(',', ' '), cell_style),
            Paragraph(f"{new_sum:,.2f}".replace(',', ' '), cell_style)
        ]
        data.append(row_data)

    data.append([
        Paragraph('<b>Итого:</b>', cell_style), '', '', '',
        '', Paragraph(f"<b>{new_total:,.2f}</b>".replace(',', ' '), cell_style)
    ])
    data.append([
        Paragraph('Без налога (НДС):', cell_style), '', '', '',
        '', Paragraph('—', cell_style)
    ])
    data.append([
        Paragraph('<b>Всего:</b>', cell_style), '', '', '',
        '', Paragraph(f"<b>{new_total:,.2f}</b>".replace(',', ' '), cell_style)
    ])

    table = Table(data, colWidths=[10*mm, 70*mm, 15*mm, 20*mm, 30*mm, 30*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (1,0), (1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,-3), (-1,-1), colors.HexColor('#f8f9fa')),
        ('FONTNAME', (0,-3), (-1,-1), FONT_NAME),
        ('GRID', (0,0), (-1,-4), 0.5, colors.grey),
        ('BOX', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 3*mm))

    total_words = f"Всего наименований {len(df)}, на сумму {int(new_total)} рублей 00 копеек"
    elements.append(Paragraph(total_words, header_style))
    elements.append(Spacer(1, 5*mm))

    if payment_terms:
        elements.append(Paragraph(f"<b>Условия оплаты и доставки:</b>", header_style))
        elements.append(Paragraph(payment_terms.replace('\n', '<br/>'), header_style))
        elements.append(Spacer(1, 3*mm))

    elements.append(Spacer(1, 8*mm))
    sig_img = None
    if signature_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(signature_bytes)
            tmp_path = tmp.name
        sig_img = RLImage(tmp_path, width=30*mm, height=15*mm)
        os.unlink(tmp_path)

    left_sig = []
    if sig_img:
        left_sig.append(sig_img)
    if left_sig:
        sig_table = Table([[left_sig[0]]])
        sig_table.setStyle(TableStyle([
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('FONTNAME', (0,0), (-1,-1), FONT_NAME)
        ]))
        left_part = sig_table
    else:
        left_part = Paragraph("(подпись)", header_style)

    right_text = f"<b>{sign_position}</b><br/>{sign_name}"
    right_part = Paragraph(right_text, company_style)

    sig_data = [[left_part, right_part]]
    sig_table = Table(sig_data, colWidths=[80*mm, 50*mm])
    sig_table.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'BOTTOM'),
        ('ALIGN',(0,0),(0,0),'CENTER'),
        ('ALIGN',(1,0),(1,0),'RIGHT'),
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME)
    ]))
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
                st.error("❌ Не удалось автоматически определить колонки. Убедитесь, что в файле есть колонки: "
                         "Наименование, Количество, Цена, Сумма (можно с другими названиями, но они должны быть понятны).")
                st.stop()
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
            col3.metric("Наценка", f"{new_total - old_total:,.2f} ₽")

            if not st.session_state.supplier['name']:
                st.warning("⚠️ Заполните реквизиты поставщика в боковой панели.")
            if not buyer_name:
                st.warning("⚠️ Укажите название покупателя.")

            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("📥 Download KP", type="primary"):
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
                        label="📥 Download PDF",
                        data=pdf_buffer,
                        file_name=f"KP_{kp_number if kp_number else 'без_номера'}.pdf",
                        mime="application/pdf"
                    )
            with col_btn2:
                if st.button("📧 Send by email"):
                    if not buyer_email:
                        st.warning("Укажите email покупателя.")
                    elif not st.session_state.supplier['name']:
                        st.warning("Заполните реквизиты поставщика.")
                    else:
                        st.info(f"📧 Отправка на {buyer_email} ... (в реальном приложении добавьте SMTP)")
            with col_btn3:
                if st.button("🔗 Get link"):
                    st.info("🔗 Демо-ссылка: https://disk.yandex.ru/d/example (в реальном приложении загрузите на Яндекс Диск)")

    except Exception as e:
        st.error(f"Ошибка: {e}")
else:
    st.session_state.normalized_df = None
    st.info("Загрузите накладную (Excel или PDF), и приложение автоматически определит колонки.")