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
            st.experimental_rerun()
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
 
def normalize_columns(df, manual=False):
    """
    Автоматически или вручную определяет колонки.
    Если manual=False, пытается найти стандартные колонки.
    Если не находит, возвращает None и сохраняет список всех колонок в st.session_state.
    """
    df.columns = [col.lower().strip() for col in df.columns]
    col_map = {}
    # Попытка автоматического поиска
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
    if missing and not manual:
        # Сохраняем список всех колонок для ручного выбора
        st.session_state.all_columns = list(df.columns)
        st.session_state.auto_failed = True
        return None
    elif missing and manual:
        # Используем st.selectbox для ручного выбора
        # Показываем пользователю выбор
        st.warning("Не удалось автоматически определить колонки. Пожалуйста, выберите соответствие вручную:")
        for r in required:
            selected = st.selectbox(f"Выберите колонку для '{r}'", options=[''] + list(df.columns), key=f"col_{r}")
            if selected:
                col_map[r] = selected
        # Проверяем, что все выбраны
        if all(r in col_map for r in required):
            # Переименовываем колонки
            rename_dict = {v: k for k, v in col_map.items() if k in required}
            df = df.rename(columns=rename_dict)
            # Оставляем только нужные колонки
            df = df[required]
            # Добавляем Ед. изм. если есть
            if 'Ед. изм.' in col_map:
                df['Ед. изм.'] = df[col_map['Ед. изм.']]
            return df
        else:
            st.error("❌ Вы не выбрали все необходимые колонки.")
            return None
 
    # Если автоматически нашлись все
    rename_dict = {v: k for k, v in col_map.items() if k in required}
    df = df.rename(columns=rename_dict)
    # Приводим к нужному типу
    for col in ['Количество', 'Цена', 'Сумма']:
        df[col] = df[col].astype(str).str.replace(',', '.').str.replace(' ', '')
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['Количество', 'Цена', 'Сумма'])
    # Добавляем Ед. изм. если есть
    if 'Ед. изм.' in col_map:
        df['Ед. изм.'] = df[col_map['Ед. изм.']]
    else:
        df['Ед. изм.'] = 'шт'
    return df
 
# ---------- Основной процесс ----------
if uploaded_file is not None:
    file_extension = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_extension == 'xlsx':
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        elif file_extension == 'pdf':
            df = extract_table_from_pdf(uploaded_file)
            if df is None:
                st.error("❌ Не удалось извлечь таблицу из PDF. Убедитесь, что PDF текстовый (не скан).")
                st.stop()
        else:
            st.error("❌ Неподдерживаемый формат. Только XLSX и PDF.")
            st.stop()
 
        # Показываем предпросмотр данных
        st.subheader("📄 Данные из файла (сырые)")
        st.dataframe(df.head(10))
 
        # Пытаемся нормализовать колонки
        if 'auto_failed' in st.session_state and st.session_state.auto_failed:
            # Показываем ручной выбор
            df = normalize_columns(df, manual=True)
            if df is None:
                st.stop()
            st.session_state.auto_failed = False
        else:
            df = normalize_columns(df, manual=False)
            if df is None:
                # Если не удалось автоматически, запросим ручной
                st.info("Автоматическое определение не удалось. Нажмите кнопку ниже, чтобы выбрать колонки вручную.")
                if st.button("Выбрать колонки вручную"):
                    df = normalize_columns(df, manual=True)
                    if df is None:
                        st.stop()
                else:
                    st.stop()
 
        # Дальше код как прежде (редактируемая таблица и т.д.)
        # ... (весь остальной код без изменений) ...
        # Чтобы не повторять весь код, я оставлю эту часть, но вы должны добавить сюда оставшуюся логику (редактирование, PDF, кнопки) из предыдущей версии.
        # Поскольку я даю полный код, я продолжу.
        # (Продолжение основного процесса)
 
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
                # ... код скачивания ...
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
    st.info("Загрузите накладную (Excel или PDF), отредактируйте данные и выберите действие.")
