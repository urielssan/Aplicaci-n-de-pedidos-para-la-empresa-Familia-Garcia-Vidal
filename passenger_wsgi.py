import imp
import sys
import os

# Ruta al entorno virtual
venv_path = "/home/gvidal/aplicacion_pedidos/venv"

# Agregar el entorno virtual a sys.path
sys.path.insert(0, os.path.join(venv_path, "lib/python3.9/site-packages"))

# Importar la aplicación Flask
from app import app as application
