from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Definir los permisos (alcances) para Google Sheets y Google Drive
SCOPES = [
    "https://spreadsheets.google.com/feeds", 
    "https://www.googleapis.com/auth/drive"
]

# Archivo JSON con credenciales de la cuenta de servicio
CREDENTIALS_FILE = "app-ventas-fgv-eaa46cb9da87.json"

def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPES)
    cliente = gspread.authorize(creds)
    sheet_id = "1hi-XTGV1Asu1KAvw-hE7UKWgY6nJq3IakaR2OykrA8c"
    return cliente.open_by_key(sheet_id)

COLUMNS_PEDIDOS = ["ID", "Vendedor", "Cliente", "Dirección", "Teléfono", "Fecha de Entrega",
                   "Horario de Entrega", "Método de Pago", "Monto", "Pagado", "Productos", 
                   "Cantidades"]

COLUMNS_PRODUCTOS = ["ID Venta", "Fecha de Entrega", "Monto", "Vendedor", "Método de Pago", 
                     "Cliente", "Producto", "Cantidad"]

def obtener_o_crear_hoja(sheet, nombre_hoja, columnas=None):
    try:
        hoja = sheet.worksheet(nombre_hoja)
    except gspread.exceptions.WorksheetNotFound:
        hoja = sheet.add_worksheet(title=nombre_hoja, rows="1000", cols="20")
        if columnas:
            hoja.append_row(columnas)
    return hoja

def guardar_en_sheets(datos, productos, cantidades):
    sheet = conectar_sheets()
    hoja_pedidos = obtener_o_crear_hoja(sheet, "Pedidos", COLUMNS_PEDIDOS)
    hoja_productos = obtener_o_crear_hoja(sheet, "Productos Vendidos", COLUMNS_PRODUCTOS)

    productos_str = ", ".join(productos)
    cantidades_str = ", ".join(map(str, cantidades))

    # 🔑 Convierte fecha a datetime compatible con Sheets
    fecha_entrega = datetime.strptime(datos["Fecha de Entrega"], "%Y-%m-%d")

    fila = [
        datos["ID"], datos["Vendedor"], datos["Cliente"], datos["Dirección"], 
        datos["Teléfono"], fecha_entrega.strftime("%Y-%m-%d"), datos["Horario de Entrega"], 
        datos["Método de Pago"], datos["Monto"], datos["Pagado"], productos_str, cantidades_str
    ]

    hoja_pedidos.append_row(fila, value_input_option='USER_ENTERED')

    for producto, cantidad in zip(productos, cantidades):
        hoja_productos.append_row([
            datos["ID"], fecha_entrega.strftime("%Y-%m-%d"), datos["Monto"], 
            datos["Vendedor"], datos["Método de Pago"], datos["Cliente"], producto, int(cantidad)
        ], value_input_option='USER_ENTERED')

    print("✅ Pedido guardado en Google Sheets")
