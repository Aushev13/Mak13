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
from datetime import datetime
from fpdf import FPDF

# --- Функция гарантированной загрузки шрифта с поддержкой кириллицы ---
def get_cyrillic_font_path():
    """
    Возвращает путь к шрифту с поддержкой кириллицы.
    Сначала проверяет системные пути, затем скачивает из интернета.
    """
    # Список возможных системных путей
    system_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
        '/usr/share/fonts/truetype/arial/arial.ttf',
    ]
    for path in system_paths:
        if os.path.exists(path):
            return path
    
    # Если системных нет, скачиваем во временную папку
    font_dir = tempfile.gettempdir()
    font_path = os.path.join(font_dir, 'DejaVuSans.ttf')
    if not os.path.exists(font_path):
        try:
            urllib.request.urlretrieve(
                'https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf',
                font_path
            )
        except:
            font_path = None
    
    return font_path if font_path and os.path.exists(font_path) else None

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

# ---------- Генерация PDF с принудительной загрузкой шрифта ----------
def generate_pdf(df, markup, old_total, new_total, supplier, buyer_name, buyer_inn,
                 logo_bytes, signature_bytes, stamp_bytes, sign_position, sign_name,
                 kp_number, kp_date, payment_terms):
    # Получаем путь к шрифту с кириллицей
    font_path = get_cyrillic_font_path()
    
    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    if font_path:
        # Регистрируем шрифт
        pdf.add_font('Cyrillic', '', font_path, uni=True)
        # Для жирного стиля используем тот же шрифт (fpdf автоматически делает жирным)
        pdf.add_font('Cyrillic', 'B', font_path, uni=True)
        font_name = 'Cyrillic'
    else:
        st.warning("⚠️ Шрифт для кириллицы не загружен. Буквы могут отображаться квадратами.")
        font_name = 'Helvetica'
    
    # --- Шапка ---
    if logo_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(logo_bytes)
            tmp_path = tmp.name
        pdf.image(tmp_path, x=170, y=10, w=30)
        os.unlink(tmp_path)
    
    pdf.set_font(font_name, 'B', 12)
    pdf.set_xy(10, 10)
    pdf.cell(0, 6, supplier['name'], ln=True)
    pdf.set_font(font_name, '', 10)
    if supplier['address']:
        pdf.cell(0, 5, supplier['address'], ln=True)
    if supplier['inn']:
        pdf.cell(0, 5, f"ИНН {supplier['inn']}", ln=True)
    if supplier['kpp']:
        pdf.cell(0, 5, f"КПП {supplier['kpp']}", ln=True)
    if supplier['phone']:
        pdf.cell(0, 5, f"тел. {supplier['phone']}", ln=True)
    if supplier['bank']:
        pdf.cell(0, 5, supplier['bank'], ln=True)
    
    pdf.ln(3)
    if buyer_name:
        pdf.set_font(font_name, 'B', 10)
        pdf.cell(0, 5, f"Покупатель: {buyer_name}", ln=True)
        if buyer_inn:
            pdf.set_font(font_name, '', 10)
            pdf.cell(0, 5, f"ИНН {buyer_inn}", ln=True)
    
    pdf.ln(4)
    pdf.set_font(font_name, 'B', 16)
    title_text = "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ"
    if kp_number:
        title_text += f" № {kp_number}"
    pdf.cell(0, 8, title_text, ln=True, align='C')
    if kp_date:
        pdf.set_font(font_name, '', 10)
        pdf.cell(0, 5, f"от {kp_date}", ln=True, align='C')
    pdf.ln(4)
    
    # --- Таблица ---
    headers = ['№', 'Наименование', 'Ед. изм.', 'Количество', 'Цена', 'Сумма']
    col_widths = [10, 70, 15, 20, 30, 30]
    
    pdf.set_font(font_name, 'B', 9)
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 7, header, border=1, align='C')
    pdf.ln()
    
    pdf.set_font(font_name, '', 9)
    for idx, row in df.iterrows():
        new_price = row['Цена'] * (1 + markup/100)
        new_sum = row['Сумма'] * (1 + markup/100)
        data_row = [
            str(row.get('№', idx+1)),
            str(row['Наименование']),
            str(row.get('Ед. изм.', 'шт')),
            str(int(row['Количество'])) if row['Количество']==int(row['Количество']) else str(row['Количество']),
            f"{new_price:,.2f}".replace(',', ' '),
            f"{new_sum:,.2f}".replace(',', ' ')
        ]
        for i, cell in enumerate(data_row):
            pdf.cell(col_widths[i], 6, cell, border=1, align='C')
        pdf.ln()
    
    pdf.set_font(font_name, 'B', 9)
    pdf.cell(col_widths[0], 7, '', border=1)
    pdf.cell(col_widths[1], 7, '', border=1)
    pdf.cell(col_widths[2], 7, '', border=1)
    pdf.cell(col_widths[3], 7, '', border=1)
    pdf.cell(col_widths[4], 7, 'Итого:', border=1, align='R')
    pdf.cell(col_widths[5], 7, f"{new_total:,.2f}".replace(',', ' '), border=1, align='R')
    pdf.ln()
    
    pdf.cell(col_widths[0], 7, '', border=1)
    pdf.cell(col_widths[1], 7, '', border=1)
    pdf.cell(col_widths[2], 7, '', border=1)
    pdf.cell(col_widths[3], 7, '', border=1)
    pdf.cell(col_widths[4], 7, 'Без налога (НДС):', border=1, align='R')
    pdf.cell(col_widths[5], 7, '—', border=1, align='R')
    pdf.ln()
    
    pdf.cell(col_widths[0], 7, '', border=1)
    pdf.cell(col_widths[1], 7, '', border=1)
    pdf.cell(col_widths[2], 7, '', border=1)
    pdf.cell(col_widths[3], 7, '', border=1)
    pdf.cell(col_widths[4], 7, 'Всего:', border=1, align='R')
    pdf.cell(col_widths[5], 7, f"{new_total:,.2f}".replace(',', ' '), border=1, align='R')
    pdf.ln()
    
    pdf.ln(3)
    pdf.set_font(font_name, '', 10)
    total_words = f"Всего наименований {len(df)}, на сумму {int(new_total)} рублей 00 копеек"
    pdf.cell(0, 6, total_words, ln=True)
    
    if payment_terms:
        pdf.ln(2)
        pdf.set_font(font_name, 'B', 10)
        pdf.cell(0, 6, "Условия оплаты и доставки:", ln=True)
        pdf.set_font(font_name, '', 10)
        pdf.multi_cell(0, 5, payment_terms)
    
    pdf.ln(6)
    if signature_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(signature_bytes)
            tmp_path = tmp.name
        pdf.image(tmp_path, x=120, y=pdf.get_y(), w=30)
        os.unlink(tmp_path)
        pdf.ln(8)
    pdf.set_font(font_name, 'B', 10)
    pdf.cell(0, 6, sign_position, ln=True, align='R')
    pdf.cell(0, 6, sign_name, ln=True, align='R')
    
    pdf_output = pdf.output(dest='S').encode('latin1')
    return io.BytesIO(pdf_output)

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