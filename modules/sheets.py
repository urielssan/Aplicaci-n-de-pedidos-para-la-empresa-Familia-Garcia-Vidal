import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from pathlib import Path

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

# Definir los permisos (alcances) para Google Sheets y Google Drive
SCOPES = [
    "https://spreadsheets.google.com/feeds", 
    "https://www.googleapis.com/auth/drive"
]


# Archivo JSON con credenciales de la cuenta de servicio
CREDENTIALS_FILE = "app-ventas-fgv-eaa46cb9da87.json"  # Reemplaza con tu archivo JSON

def conectar_sheets():
    """Autentica con Google Sheets y Drive"""
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPES)
    cliente = gspread.authorize(creds)
    
    # Abrimos la hoja correctamente
    sheet_id = "1hi-XTGV1Asu1KAvw-hE7UKWgY6nJq3IakaR2OykrA8c"  # El ID de tu Google Sheet
    sheet = cliente.open_by_key(sheet_id)
 # Asegura que el nombre es correcto
    return sheet

# Columnas ordenadas en la hoja "Pedidos"
COLUMNS_PEDIDOS = [
    "ID","DNI", "Vendedor", "Cliente", "Dirección", "Teléfono",
    "Email", "Fecha de Nacimiento", "Sexo",
    "Fecha de Entrega", "Horario de Entrega", "Método de Pago", "Monto",
    "Pagado", "Productos", "Cantidades", "Estado", "Envio", "Zona de Envio",
    "Observaciones", "Descuento", "Fecha de Ingreso", "Banco", "Local", "Medio"
]


COLUMNS_PRODUCTOS = ["ID Venta", "Fecha de Entrega", "Monto", "Vendedor", "Método de Pago", "Cliente", "Producto", "Cantidad"]

def obtener_o_crear_hoja(sheet, nombre_hoja, columnas=None):
    """Obtiene la hoja si existe, o la crea con encabezados"""
    try:
        hoja = sheet.worksheet(nombre_hoja)  # Intenta obtener la hoja
    except gspread.exceptions.WorksheetNotFound:
        hoja = sheet.add_worksheet(title=nombre_hoja, rows="1000", cols="20")  # Crea la hoja si no existe
        if columnas:
            hoja.append_row(columnas)  # Agregar encabezados
    return hoja

def guardar_en_sheets(datos, productos, cantidades, ids):
    """Guarda los datos en las hojas de Google Sheets"""
    sheet = conectar_sheets()
    # Obtener o crear hojas
    hoja_pedidos = obtener_o_crear_hoja(sheet, "Pedidos", COLUMNS_PEDIDOS)
    hoja_productos = obtener_o_crear_hoja(sheet, "Productos Vendidos", COLUMNS_PRODUCTOS)

    # Concatenamos productos y cantidades en un solo string
    productos_str = ", ".join(productos)
    cantidades_str = ", ".join(map(str, cantidades))
    productos_json = cargar_precios()
    nombre_a_id = {datos["nombre"]: id_producto for id_producto, datos in productos_json.items()}
    # Crear fila de datos ordenada
    fila = [
        datos["ID"],datos["DNI"], datos["Vendedor"], datos["Cliente"], datos["Dirección"], datos["Teléfono"],datos.get("Email", ""), datos.get("Fecha de Nacimiento", ""),datos.get("Sexo", ""), datos["Fecha de Entrega"], datos["Horario de Entrega"], datos["Método de Pago"], datos["Monto"], datos["Pagado"], productos_str, cantidades_str, datos["Estado"], datos["Envio"],datos["Zona de Envio"], datos["Observaciones"], datos["Descuento"], datos["Fecha de Ingreso"], datos["Banco"], datos["Local"], datos["Medio"]
    ]

    # 🔹 Agregar la fila en la hoja "Pedidos"
    hoja_pedidos.append_row(fila)

    # 🔹 Agregar cada producto vendido en la hoja "Productos Vendidos"
    for producto, cantidad, id_producto in zip(productos, cantidades, ids):
        hoja_productos.append_row([
            datos["ID"], datos["Fecha de Entrega"], datos["Monto"], 
            datos["Método de Pago"], datos["Vendedor"], datos["Cliente"], producto, int(cantidad), nombre_a_id.get(producto)
        ])

    print("✅ Pedido guardado en Google Sheets")
