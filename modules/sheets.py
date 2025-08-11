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

def guardar_en_sheets(datos, productos, cantidades):
    """Guarda los datos en las hojas de Google Sheets en un solo batch"""
    sheet = conectar_sheets()  # Spreadsheet
    hoja_pedidos = obtener_o_crear_hoja(sheet, "Pedidos", COLUMNS_PEDIDOS)          # Worksheet
    hoja_productos = obtener_o_crear_hoja(sheet, "Productos Vendidos", COLUMNS_PRODUCTOS)

    # Normalizar cantidades a int
    cantidades_int = [int(c) for c in cantidades]

    # Strings combinados (por compatibilidad con tu esquema actual)
    productos_str = ", ".join(productos)
    cantidades_str = ", ".join(map(str, cantidades_int))

    # Mapeo nombre -> id producto
    productos_json = cargar_precios()
    nombre_a_id = {v["nombre"]: k for k, v in productos_json.items()}

    # Fila para "Pedidos" (mantenemos el orden de columnas actual)
    fila_pedido = [
        datos["ID"], datos["DNI"], datos["Vendedor"], datos["Cliente"], datos["Dirección"], datos["Teléfono"],
        datos.get("Email", ""), datos.get("Fecha de Nacimiento", ""), datos.get("Sexo", ""),
        datos["Fecha de Entrega"], datos["Horario de Entrega"], datos["Método de Pago"],
        datos["Monto"], datos["Pagado"], productos_str, cantidades_str, datos["Estado"],
        datos["Envio"], datos["Zona de Envio"], datos["Observaciones"], datos["Descuento"],
        datos["Fecha de Ingreso"], datos["Banco"], datos["Local"], datos["Medio"]
    ]

    # Filas para "Productos Vendidos"
    filas_productos = []
    for producto, cantidad in zip(productos, cantidades_int):
        filas_productos.append([
            datos["ID"],                   # A: ID Pedido
            datos["Fecha de Entrega"],     # B
            datos["Monto"],                # C
            datos["Vendedor"],             # D (tu orden original tenía Vendedor antes que Método)
            datos["Método de Pago"],       # E
            datos["Cliente"],              # F
            producto,                      # G
            cantidad,                      # H
            nombre_a_id.get(producto)      # I (ID producto si existe)
        ])

    # Calcular próxima fila libre de cada hoja (simple y efectivo)
    prox_fila_pedidos = len(hoja_pedidos.get_all_values()) + 1
    prox_fila_productos = len(hoja_productos.get_all_values()) + 1

    # Rango inicial (empieza en A{fila} y se expande según la cantidad de columnas provistas)
    rango_pedidos = f"{hoja_pedidos.title}!A{prox_fila_pedidos}"
    rango_productos = f"{hoja_productos.title}!A{prox_fila_productos}"

    # Un solo batch para escribir todo
    body = {
        "valueInputOption": "USER_ENTERED",
        "data": [
            {
                "range": rango_pedidos,
                "majorDimension": "ROWS",
                "values": [fila_pedido]
            },
            {
                "range": rango_productos,
                "majorDimension": "ROWS",
                "values": filas_productos
            }
        ]
    }

    # Importante: esto es sobre el Spreadsheet (no Worksheet)
    sheet.values_batch_update(body)
