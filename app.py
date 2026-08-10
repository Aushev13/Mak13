def generate_pdf(df, markup, old_total, new_total, supplier, buyer_name, buyer_inn,
                 logo_bytes, signature_bytes, stamp_bytes, sign_position, sign_name,
                 kp_number, kp_date, payment_terms):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=20*mm, bottomMargin=15*mm)
    elements = []
    styles = getSampleStyleSheet()

    # Стили
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, spaceAfter=6)
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=9, textColor=colors.grey)
    company_style = ParagraphStyle('Company', parent=styles['Normal'], fontSize=10, leading=12)
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8)
    total_style = ParagraphStyle('Total', parent=styles['Normal'], fontSize=11, alignment=TA_RIGHT, spaceBefore=5)
    total_bold_style = ParagraphStyle('TotalBold', parent=styles['Normal'], fontSize=11, alignment=TA_RIGHT, spaceBefore=5, fontName='Helvetica-Bold')

    # Логотип (если есть)
    logo_img = None
    if logo_bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(logo_bytes)
            tmp_path = tmp.name
        logo_img = RLImage(tmp_path, width=25*mm, height=20*mm, hAlign='RIGHT')
        os.unlink(tmp_path)

    # Шапка: реквизиты поставщика
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
    elements.append(Spacer(1, 5*mm))

    # Таблица
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

    # Итоги
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
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,-3), (-1,-1), colors.HexColor('#f8f9fa')),
        ('FONTNAME', (0,-3), (-1,-1), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-4), 0.5, colors.grey),
        ('BOX', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 3*mm))

    # Пропись суммы
    total_words = f"Всего наименований {len(df)}, на сумму {int(new_total)} рублей 00 копеек"
    elements.append(Paragraph(total_words, header_style))
    elements.append(Spacer(1, 5*mm))

    # Условия оплаты
    if payment_terms:
        elements.append(Paragraph(f"<b>Условия оплаты и доставки:</b>", header_style))
        elements.append(Paragraph(payment_terms.replace('\n', '<br/>'), header_style))
        elements.append(Spacer(1, 3*mm))

    # Подпись
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
        sig_table.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'), ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
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
        ('ALIGN',(1,0),(1,0),'RIGHT')
    ]))
    elements.append(sig_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer