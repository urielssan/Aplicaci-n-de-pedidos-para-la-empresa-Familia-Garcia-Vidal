import os
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from modules.config import Config  # Importamos la configuración
from pathlib import Path
import json
JSON_PATH = Path("modules/precios_productos.json")

def cargar_precios():
    """Carga los precios de los productos desde el archivo JSON."""
    try:
        with open(JSON_PATH, 'r') as f:
            data = json.load(f)

            return dict(sorted(data.items(), key=lambda item: item[1]["nombre"]))
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo JSON en {JSON_PATH}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: El archivo JSON en {JSON_PATH} no es válido.")
        return {}
def cargar_precios_por_nombre():
    precios = cargar_precios()
    return {v["nombre"]: v["precio"] for v in precios.values()}

def generar_pdf(pedido_id, cliente, fecha_entrega, horario_entrega, metodo_pago, zona_envio, monto, descuento, total_final, pagado, productos, cantidades, precios, direccion, telefono, observaciones, estado, medio):
    pdf_path = f"orden_pedido_{pedido_id}.pdf"
    LOGO_PATH = Config.LOGO_PATH

    productosJSON = cargar_precios()
    doc = SimpleDocTemplate(pdf_path, pagesize=(150 * mm, 250 * mm), leftMargin=5 * mm, rightMargin=5 * mm, topMargin=10 * mm, bottomMargin=5 * mm)
    elements = []
    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = 10

    # Logo
    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=92, height=60)
        elements.append(logo)
    elements.append(Spacer(1, 10))

    # Sección 2: Número de Orden
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>ORDEN DE PEDIDO #{pedido_id}</b>", styles["Heading3"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>TIPO DE PEDIDO: {estado}</b>", styles["Heading2"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>FUE PEDIDO POR: {medio}</b>", styles["Heading4"]))
    elements.append(Paragraph("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", styles["Normal"]))

    # Sección 3: Tabla de Productos Minimalista
    total_precio = 0
    table_data = [["Producto", "Cant.", "P. Unit", "Total"]]
    for producto, cantidad, precio in zip(productos, cantidades, precios):
        total_precio = total_precio + precio * float(cantidad)
        table_data.append([productosJSON[producto]["nombre"], f"{cantidad}x", f"${precio:,.2f}", f"${total_precio:,.2f}"])

    table = Table(table_data, colWidths=[40 * mm, 25 * mm, 25 * mm, 25 * mm], hAlign='CENTER')
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 10))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", styles["Normal"]))

    # Sección 4: Subtotal, Descuento y Total
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Subtotal: ${total_precio:,.2f}", styles["Normal"]))
    if descuento == 1:
        elements.append(Spacer(1, 10))
        descuento =  total_precio * 0.05
    elif descuento == 2:
        elements.append(Spacer(1, 10))
        descuento =  total_precio * 0.1
    elif descuento == 3:
        elements.append(Spacer(1, 10))
        descuento =  total_precio * 0.15  
    else:descuento =  total_final * 0
    if zona_envio == "Sin envío":
        precio_envio = 0
    else:        
        precio_envio = int(zona_envio)
    elements.append(Paragraph(f"Descuento: -${descuento:,.2f}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Envio: +${precio_envio:,.2f}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Total: ${total_final:,.2f}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", styles["Normal"]))

    # Sección 5: Método de Pago y Envío
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Método de Pago: {metodo_pago}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Pagado: {pagado}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    fecha_formateada = fecha_entrega[-2:] + "-" + fecha_entrega[5:7]
    elements.append(Paragraph(f"Fecha de Envío: {fecha_formateada}", styles["Normal"]))

    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Horario de Envío: {horario_entrega}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", styles["Normal"]))

    # Sección 6: Datos del Cliente
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Cliente: {cliente}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Teléfono: {telefono}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Dirección: {direccion}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", styles["Normal"]))

    # Sección 7: Observaciones
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Observaciones: {observaciones}", styles["Normal"]))

    # Aplicamos alineación centrada a los textos desde la sección 3 en adelante
    centered_style = styles["Normal"].clone('Centered')
    centered_style.alignment = TA_CENTER

    for i in range(3, len(elements)):  # Empezamos desde la tercera sección
        if isinstance(elements[i], Paragraph):  # Solo centramos los párrafos, no los Spacer ni Tablas
            elements[i].style = centered_style

    # Construimos el documento después de aplicar los estilos
    doc.build(elements)

    return send_file(pdf_path, as_attachment=True)


def generar_pdf_detalles_pedido(pedido_id, cliente, fecha_entrega, horario_entrega, metodo_pago, monto, zona_envio, descuento, pagado, productos, cantidades, precios, direccion, telefono, observaciones):
    precios_por_nombre = cargar_precios_por_nombre()
    pdf_path = f"orden_pedido_{pedido_id}.pdf"
    LOGO_PATH = Config.LOGO_PATH
    total_final = 0
    for precio in precios:
        print(precio)
        total_final += precio
    doc = SimpleDocTemplate(pdf_path, pagesize=(250 * mm, 250 * mm), leftMargin=5 * mm, rightMargin=5 * mm, topMargin=10 * mm, bottomMargin=5 * mm)
    elements = []
    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = 10

    # Logo
    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=92, height=60)
        elements.append(logo)
    elements.append(Spacer(1, 10))

    # Sección 2: Número de Orden
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>ORDEN DE PEDIDO #{pedido_id}</b>", styles["Heading3"]))
    elements.append(Spacer(1, 10))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", styles["Normal"]))

    # Sección 3: Tabla de Productos Minimalista
    total_precio = 0
    table_data = [["Producto", "Cant.", "P. Unit", "Total"]]

    for producto, cantidad in zip(productos, cantidades):
        precio_unit = precios_por_nombre.get(producto, 0)
        total_item = precio_unit * float(cantidad)
        total_precio += total_item
        table_data.append([
            producto, f"{cantidad}x", f"${precio_unit:,.2f}", f"${total_item:,.2f}"
        ])
    table = Table(table_data, colWidths=[80 * mm, 25 * mm, 25 * mm, 25 * mm], hAlign='CENTER')
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 10))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", styles["Normal"]))

    # Sección 4: Subtotal, Descuento y Total
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Subtotal: ${total_precio:,.2f}", styles["Normal"]))
    if descuento > 0:
        elements.append(Spacer(1, 10))
        descuento =  total_precio * 0.05
    else: descuento =  0

    total_final = total_precio - descuento + zona_envio
    elements.append(Paragraph(f"Descuento: -${descuento:,.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Costo de envio: ${zona_envio:,.2f}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Total: ${total_final:,.2f}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", styles["Normal"]))

    # Sección 5: Método de Pago y Envío
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Método de Pago: {metodo_pago}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Pagado: {pagado}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Fecha de Envío: {fecha_entrega}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Horario de Envío: {horario_entrega}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", styles["Normal"]))

    # Sección 6: Datos del Cliente
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Cliente: {cliente}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Teléfono: {telefono}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Dirección: {direccion}", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -", styles["Normal"]))

    # Sección 7: Observaciones
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Observaciones: {observaciones}", styles["Normal"]))

    # Aplicamos alineación centrada a los textos desde la sección 3 en adelante
    centered_style = styles["Normal"].clone('Centered')
    centered_style.alignment = TA_CENTER

    for i in range(3, len(elements)):  # Empezamos desde la tercera sección
        if isinstance(elements[i], Paragraph):  # Solo centramos los párrafos, no los Spacer ni Tablas
            elements[i].style = centered_style

    # Construimos el documento después de aplicar los estilos
    doc.build(elements)

    return send_file(pdf_path, as_attachment=True)