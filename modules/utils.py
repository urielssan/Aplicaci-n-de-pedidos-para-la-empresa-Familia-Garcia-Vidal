import os
import pandas as pd
from modules.config import Config  # Importamos la configuración
import json
from pathlib import Path


def init_excel():
    """Inicializa el archivo de Excel si no existe."""
    if not os.path.exists(Config.FILE_PATH):
        df = pd.DataFrame(columns=[
            "Vendedor", "Cliente", "Dirección", "Teléfono", "Fecha de Entrega",
            "Horario de Entrega", "Método de Pago", "Monto", "Pagado",
            "Productos", "Cantidad", "Observaciones", "Estado"
        ])
        df.to_excel(Config.FILE_PATH, index=False)




#Datos de autenticación
USUARIO_ADMIN = "admin"
CONTRASEÑA_ADMIN = "admin123"


# Configuraciones
FILE_PATH = os.path.join(os.getcwd(), "pedidos.xlsx")
LOGO_PATH = os.path.join(os.getcwd(), "static", "images", "logo.png")
# Inicializar configuraciones
init_excel()

# Ruta al archivo JSON (asegúrate de que la ruta sea correcta)
JSON_PATH = Path("modules/precios_productos.json")

def cargar_precios():
    """Carga los precios de los productos desde el archivo JSON."""
    try:
        with open(JSON_PATH, 'r') as f:
            data = json.load(f)

            return dict(sorted(data.items()))
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo JSON en {JSON_PATH}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: El archivo JSON en {JSON_PATH} no es válido.")
        return {}
