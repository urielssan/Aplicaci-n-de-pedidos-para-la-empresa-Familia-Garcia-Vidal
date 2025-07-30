from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, make_response
import pandas as pd
from modules.utils import  init_excel
from modules.pdf_generator import generar_pdf, generar_pdf_detalles_pedido
from modules.sheets import conectar_sheets, guardar_en_sheets, obtener_o_crear_hoja
from functools import wraps
from datetime import datetime
import json
from pathlib import Path
import os
import zipfile
from graphviz import Digraph
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests

from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

os.environ["PATH"] += os.pathsep + "C:/Program Files/Graphviz/bin"

app = Flask(__name__)
app.secret_key = "clave_secreta"


#Datos de autenticación
USUARIO_ADMIN = "admin"
CONTRASEÑA_ADMIN = "admin123"
USUARIO_VENDEDOR = "vendedor"
CONTRASEÑA_VENDEDOR = "vendedor123"
USUARIO_COCINERO = "cocinero"
CONTRASEÑA_COCINERO = "cocinero123"


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

            return dict(sorted(data.items(), key=lambda item: item[1]["nombre"]))
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo JSON en {JSON_PATH}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: El archivo JSON en {JSON_PATH} no es válido.")
        return {}

JSON_PATH_MPrima = Path("modules/materia_prima.json")

def cargar_materia_prima():
    """Carga los precios de los productos desde el archivo JSON."""
    try:
        with open(JSON_PATH_MPrima, 'r', encoding="utf-8") as f:
            data = json.load(f)

            return dict(sorted(data.items()))
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo JSON en {JSON_PATH_MPrima}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: El archivo JSON en {JSON_PATH_MPrima} no es válido.")
    return {}

@app.route('/ingresar_pedido')
def ingresar_pedido():
    precios = cargar_precios()
    
    return render_template('ingresar_pedido.html', precios_productos= precios)


@app.route('/clientes', methods=['GET'])
def obtener_clientes():
    with open('modules/clientes.json', 'r', encoding='utf-8') as file:
        clientes = json.load(file)
    return jsonify(clientes)

@app.route('/clientes', methods=['POST'])
def agregar_cliente():
    nuevo_cliente = request.get_json()

    with open('modules/clientes.json', 'r+', encoding='utf-8') as file:
        clientes = json.load(file)

        # Verifica si el DNI ya existe
        if any(c['dni'] == nuevo_cliente['dni'] for c in clientes):
            return jsonify({'mensaje': 'Cliente ya registrado'}), 409

        clientes.append(nuevo_cliente)
        file.seek(0)
        json.dump(clientes, file, indent=2, ensure_ascii=False)
        file.truncate()

    return jsonify({'mensaje': 'Cliente agregado correctamente'}), 201


@app.route('/clientes/<dni>', methods=['GET'])
def obtener_cliente(dni):
    with open('modules/clientes.json', 'r', encoding='utf-8') as file:
        clientes = json.load(file)
    
    cliente = next((c for c in clientes if c['dni'] == dni), None)
    if cliente:
        return jsonify(cliente)
    else:
        return jsonify({'mensaje': 'Cliente no encontrado'}), 404

@app.route('/registrar-cliente')
def registrar_cliente_form():
    return render_template('registrar_cliente.html')

@app.route('/registrar_json', methods=['POST'])
def registrar_json():
    try:
        nuevos_clientes = request.get_json()

        # Leer clientes existentes
        if os.path.exists('clientes.json'):
            with open('clientes.json', 'r', encoding='utf-8') as f:
                clientes_existentes = json.load(f)
        else:
            clientes_existentes = []

        # Agregar nuevos clientes
        clientes_existentes.extend(nuevos_clientes)

        # Guardar todo de nuevo
        with open('clientes.json', 'w', encoding='utf-8') as f:
            json.dump(clientes_existentes, f, indent=2, ensure_ascii=False)

        return jsonify({"estado": "ok", "mensaje": f"{len(nuevos_clientes)} clientes registrados"}), 200

    except Exception as e:
        return jsonify({"estado": "error", "mensaje": str(e)}), 500

@app.route('/limpiar_json', methods=['GET', 'POST'])   
def limpiar_json():
    try:
        ruta_json = "modules/clientes.json"
        if not os.path.exists(ruta_json):
            return jsonify({"error": "clientes.json no existe"}), 404

        with open(ruta_json, "r", encoding="utf-8") as f:
            clientes = json.load(f)

        # Usamos un set para registrar combinaciones únicas
        vistos = set()
        clientes_limpios = []

        for c in clientes:
            clave = (
                str(c.get("dni", "")).strip(),
                str(c.get("nombre", "")).strip().lower(),
                str(c.get("apellido", "")).strip().lower()
            )
            if clave not in vistos:
                vistos.add(clave)
                clientes_limpios.append(c)

        # Guardamos la lista limpia
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(clientes_limpios, f, indent=2, ensure_ascii=False)

        return jsonify({"mensaje": "JSON limpiado correctamente", "total": len(clientes_limpios)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        contraseña = request.form["contraseña"]

       # Según el usuario, asignamos un rol
        if usuario == USUARIO_ADMIN and contraseña == CONTRASEÑA_ADMIN:
            session["rol"] = "admin"
            session["usuario"] = usuario
            next_page = request.args.get("next")  # 🔹 Ver si había una página previa
            return redirect(next_page or url_for("index"))  # 🔹 Ir a la página previa o index
        elif usuario == USUARIO_VENDEDOR and contraseña == CONTRASEÑA_VENDEDOR:
            session["rol"] = "vendedor"
            session["usuario"] = usuario
            next_page = request.args.get("next")  # 🔹 Ver si había una página previa
            return redirect(next_page or url_for("index"))  # 🔹 Ir a la página previa o index
        elif usuario == USUARIO_COCINERO and contraseña == CONTRASEÑA_COCINERO:
            session["rol"] = "cocinero"
            session["usuario"] = usuario
            next_page = request.args.get("next")  # 🔹 Ver si había una página previa
            return redirect(next_page or url_for("ingresar_materia_prima"))  # 🔹 Ir a la página previa o index
        else:
            return render_template("login.html", error="Usuario o contraseña incorrectos")

    return render_template("login.html")



# 🔹 Decorador para proteger rutas

def rol_requerido(*roles):
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if "usuario" not in session:
                flash("Tenés que iniciar sesión primero.", "error")
                return redirect(url_for("login"))
            if session.get("rol") not in roles:
                flash("No tenés permisos para acceder a esta página.", "error")
                return redirect(url_for("index"))
            return func(*args, **kwargs)
        return wrapper
    return decorador


@app.route('/logout')
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))

@app.errorhandler(500)
def error_servidor(e):
    return "error 500"


@app.route('/')
@rol_requerido("admin", "vendedor")
def index():
    precios = cargar_precios()
    return render_template("index.html",precios_productos=precios)

@app.route('/ver_pedidos')
@rol_requerido("admin", "vendedor")
def ver_pedidos():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Pedidos Ordenados")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    pedidos = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not pedidos:
        return render_template("ver_pedidos.html", pedidos=[])

    # Convertimos los datos en una lista de diccionarios
    headers = pedidos[0]  # La primera fila son los encabezados
    datos_pedidos = [dict(zip(headers, row)) for row in pedidos[1:]]  # Excluimos la primera fila

    pedidos_procesados = []
    for pedido in datos_pedidos:
        productos_str = pedido.get("Productos", "")
        cantidades_str = pedido.get("Cantidades", "")
        productos = [p.strip() for p in productos_str.split(',')] if productos_str else []
        cantidades_raw = [c.strip() for c in cantidades_str.split(',')] if cantidades_str else []
        cantidades = []
        for cant_str in cantidades_raw:
            try:
                cant_float = float(cant_str)
                cant_int = int(cant_float)
                if cant_float == cant_int:
                    cantidades.append(cant_int)
                else:
                    cantidades.append(cant_float)
            except ValueError:
                cantidades.append(cant_str)  # Si no se puede convertir a float, mantener el string original

        productos_con_cantidad = []
        if len(productos) == len(cantidades):
            for i in range(len(productos)):
                productos_con_cantidad.append(f"{productos[i]} : {cantidades[i]}")
            pedido["Productos"] = "; / ".join(productos_con_cantidad)
        else:
            # Manejar el caso en que la cantidad de productos y cantidades no coincidan
            print(f"Advertencia: Desajuste de productos/cantidades para el ID: {pedido.get('ID')}")
            pedido["Productos"] = productos_str  # Mantener el valor original

        pedidos_procesados.append(pedido)
    return render_template("ver_pedidos.html", pedidos=datos_pedidos)


@app.route('/ver_delivery')
@rol_requerido("admin", "vendedor")
def ver_delivery():
    """Trae los pedidos de Google Sheets y los muestra en una tabla,
    formateando la columna de Productos con sus cantidades (int si es entero, sino float)."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Delivery Semana")

    pedidos_raw = hoja_pedidos.get_all_values()

    if not pedidos_raw or len(pedidos_raw) < 2:
        return render_template("vista_delivery.html", pedidos=[])

    headers = pedidos_raw[0]
    datos_pedidos = [dict(zip(headers, row)) for row in pedidos_raw[1:]]

    pedidos_procesados = []
    for pedido in datos_pedidos:
        productos_str = pedido.get("Productos", "")
        cantidades_str = pedido.get("Cantidades", "")
        productos = [p.strip() for p in productos_str.split(',')] if productos_str else []
        cantidades_raw = [c.strip() for c in cantidades_str.split(',')] if cantidades_str else []
        cantidades = []
        for cant_str in cantidades_raw:
            try:
                cant_float = float(cant_str)
                cant_int = int(cant_float)
                if cant_float == cant_int:
                    cantidades.append(cant_int)
                else:
                    cantidades.append(cant_float)
            except ValueError:
                cantidades.append(cant_str)  # Si no se puede convertir a float, mantener el string original

        productos_con_cantidad = []
        if len(productos) == len(cantidades):
            for i in range(len(productos)):
                productos_con_cantidad.append(f"{productos[i]} : {cantidades[i]}")
            pedido["Productos"] = "; / ".join(productos_con_cantidad)
        else:
            # Manejar el caso en que la cantidad de productos y cantidades no coincidan
            print(f"Advertencia: Desajuste de productos/cantidades para el ID: {pedido.get('ID')}")
            pedido["Productos"] = productos_str  # Mantener el valor original

        pedidos_procesados.append(pedido)

    return render_template("vista_delivery.html", pedidos=pedidos_procesados)


@app.route('/ver_delivery_hoy')
@rol_requerido("admin", "vendedor")
def ver_delivery_hoy():
    """Trae los pedidos de Google Sheets y los muestra en una tabla,
    formateando la columna de Productos con sus cantidades (int si es entero, sino float)."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Delivery Hoy")

    pedidos_raw = hoja_pedidos.get_all_values()

    if not pedidos_raw or len(pedidos_raw) < 2:
        return render_template("vista_delivery_hoy.html", pedidos=[])

    headers = pedidos_raw[0]
    datos_pedidos = [dict(zip(headers, row)) for row in pedidos_raw[1:]]

    pedidos_procesados = []
    for pedido in datos_pedidos:
        productos_str = pedido.get("Productos", "")
        cantidades_str = pedido.get("Cantidades", "")
        productos = [p.strip() for p in productos_str.split(',')] if productos_str else []
        cantidades_raw = [c.strip() for c in cantidades_str.split(',')] if cantidades_str else []
        cantidades = []
        for cant_str in cantidades_raw:
            try:
                cant_float = float(cant_str)
                cant_int = int(cant_float)
                if cant_float == cant_int:
                    cantidades.append(cant_int)
                else:
                    cantidades.append(cant_float)
            except ValueError:
                cantidades.append(cant_str)  # Si no se puede convertir a float, mantener el string original

        productos_con_cantidad = []
        if len(productos) == len(cantidades):
            for i in range(len(productos)):
                productos_con_cantidad.append(f"{productos[i]} : {cantidades[i]}")
            pedido["Productos"] = "; / ".join(productos_con_cantidad)
        else:
            # Manejar el caso en que la cantidad de productos y cantidades no coincidan
            print(f"Advertencia: Desajuste de productos/cantidades para el ID: {pedido.get('ID')}")
            pedido["Productos"] = productos_str  # Mantener el valor original

        pedidos_procesados.append(pedido)

    return render_template("vista_delivery_hoy.html", pedidos=pedidos_procesados)


@app.route('/ver_retiro_en_local')
@rol_requerido("admin", "vendedor")
def ver_retiro_en_local():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Retiro por Local Semana")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    pedidos = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not pedidos:
        return render_template("vista_retiro_en_local.html", pedidos=[])

    # Convertimos los datos en una lista de diccionarios
    headers = pedidos[0]  # La primera fila son los encabezados
    datos_pedidos = [dict(zip(headers, row)) for row in pedidos[1:]]  # Excluimos la primera fila

    return render_template("vista_retiro_en_local.html", pedidos=datos_pedidos)


@app.route('/ver_retiro_en_local_hoy')
@rol_requerido("admin", "vendedor")
def ver_retiro_en_local_hoy():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Retiro por Local Hoy")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    pedidos = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not pedidos:
        return render_template("vista_retiro_en_local_hoy.html", pedidos=[])

    # Convertimos los datos en una lista de diccionarios
    headers = pedidos[0]  # La primera fila son los encabezados
    datos_pedidos = [dict(zip(headers, row)) for row in pedidos[1:]]  # Excluimos la primera fila

    return render_template("vista_retiro_en_local_hoy.html", pedidos=datos_pedidos)





@app.route("/obtener_productos_pedido/<pedido_id>")
def obtener_productos_pedido(pedido_id):
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Pedidos")
    pedidos = hoja_pedidos.get_all_values()
    datos_pedido = {}

    headers = pedidos[0]
    for row in pedidos[1:]:
        if row[0].strip() == pedido_id:
            datos_pedido = dict(zip(headers, row))
            break

    productos = datos_pedido.get('Productos', '').split(',')
    cantidades = datos_pedido.get('Cantidades', '').split(',')
    return {
        "productos": [{"nombre": p.strip(), "cantidad": float(c.strip())} for p, c in zip(productos, cantidades)],
        "datos_pedido": datos_pedido
    }


@app.route('/enviar_pedido', methods=["POST"])
@rol_requerido("admin", "vendedor")
def enviar_pedido():
    df_pedidos = pd.read_excel(FILE_PATH, sheet_name="Pedidos", engine="openpyxl")
    try:
        df_productos = pd.read_excel(FILE_PATH, sheet_name="Productos Vendidos", engine="openpyxl")
    except ValueError:
        df_productos = pd.DataFrame(columns=["ID Venta", "Producto", "Cantidad"])

    pedido_id = len(df_pedidos) + 1

    vendedor = request.form["vendedor"]
    dni = request.form["dni"]
    cliente = request.form["cliente"]
    local = request.form["local"]
    direccion = request.form["direccion"]
    telefono = request.form["telefono"]
    email = request.form.get("email", "")
    fecha_nacimiento = request.form.get("fecha_nacimiento", "")
    sexo = request.form.get("sexo", "")
    

    
    fecha_entrega = request.form["fecha_entrega"]  # mantenelo como str directamente
    
    horario_entrega = request.form["horario_entrega"]
    metodo_pago = request.form["metodo_pago"]
    descuento = int(request.form["descuentoOn"]) # 1 para descuento, 0 para sin descuento
    envio = request.form.get("envio") #Si o No
    zona_envio = request.form.get("zona_envio") if envio == "Sí" else "Sin envío"
    monto = float(request.form["monto"])
    pagado = request.form["pagado"] #Si o No
    productos = request.form.getlist("productos[]")
    cantidades = [float(c) for c in request.form.getlist("cantidades[]")]#convierte todas las cantidades a float
    observaciones = request.form["observaciones"]
    estado = request.form["estado"]
    fecha_ingreso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    banco = request.form["banco"]
    medio = request.form["pidio"]
    precios_productos = cargar_precios()

    precios = [precios_productos.get(p, {}).get("precio", 0) for p in productos]
    nombres = [precios_productos.get(p, {}).get("nombre", 0) for p in productos]

    nuevo_pedido = pd.DataFrame([{
        "ID": pedido_id,
        "DNI": dni,
        "Vendedor": vendedor,
        "Cliente": cliente,
        "Dirección": direccion,
        "Teléfono": telefono,
        "Email": email,
        "Fecha de Nacimiento": fecha_nacimiento,
        "Sexo": sexo,
        "Fecha de Entrega": fecha_entrega,
        "Horario de Entrega": horario_entrega,
        "Método de Pago": metodo_pago,
        "Descuento": descuento,
        "Envío": envio,
        "Zona de Envío": zona_envio,
        "Monto": monto,
        "Pagado": pagado,
        "Productos": ", ".join([f"{p} (x{c})" for p, c in zip(productos, cantidades)]),
        "Observaciones": observaciones,
        "Estado": estado,
        "Fecha de Ingreso": fecha_ingreso,
        "Banco": banco,
        "Medio": medio,
        "Local": local
    }])

    df_pedidos = pd.concat([df_pedidos, nuevo_pedido], ignore_index=True) #Concatena el pedido nuevo a los pedidos anteriores

    productos_vendidos = pd.DataFrame([
        {"ID Venta": pedido_id, "Producto": p, "Cantidad": c}
        for p, c in zip(productos, cantidades) if c > 0 and p.strip()
    ])

    df_productos = pd.concat([df_productos, productos_vendidos], ignore_index=True)

    with pd.ExcelWriter(FILE_PATH, engine="openpyxl") as writer:
        df_pedidos.to_excel(writer, sheet_name="Pedidos", index=False)
        df_productos.to_excel(writer, sheet_name="Productos Vendidos", index=False)

    datos_pedido = {
        "ID": pedido_id,
        "DNI": dni,
        "Vendedor": vendedor,
        "Cliente": cliente,
        "Dirección": direccion,
        "Teléfono": telefono,
        "Email": email,
        "Fecha de Nacimiento": fecha_nacimiento,
        "Sexo": sexo,
        "Fecha de Entrega": fecha_entrega,
        "Horario de Entrega": horario_entrega,
        "Método de Pago": metodo_pago,
        "Descuento": descuento,
        "Envio": envio,
        "Zona de Envio": zona_envio,
        "Monto": monto,
        "Pagado": pagado,
        "Observaciones": observaciones,
        "Estado": estado,
        "Descuento": descuento,
        "Fecha de Ingreso": fecha_ingreso,
        "Banco": banco,
        "Local": local,
        "Medio": medio
    }

    guardar_en_sheets(datos_pedido, nombres, cantidades)

    return generar_pdf(pedido_id, cliente, fecha_entrega, horario_entrega, metodo_pago, zona_envio, monto, descuento, monto, pagado, productos, cantidades, precios, direccion, telefono, observaciones,estado,medio)
 
@app.route("/editar_pedidos")
def editar_pedidos():
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Pedidos")
    pedidos = hoja_pedidos.get_all_records()
    precios = cargar_precios()
    return render_template("editar_pedidos.html", pedidos=pedidos,precios_productos=precios)


@app.route("/actualizar_pedido", methods=["POST"])
def actualizar_pedido():
    pedido_id = request.form["id"].strip() #trae el pedido id sin espacios gracias a la funcion strip
    sheet = conectar_sheets() #Conecta al libro de google
    hoja_pedidos = sheet.worksheet("Pedidos") #En este caso la hoja se llama "Pedidos"
    pedidos = hoja_pedidos.get_all_values() #Obtiene todos los pedidos en forma de lista de listas
    precios = cargar_precios()
    fila_pedido = None
    for i, row in enumerate(pedidos):
        if row[0].strip() == pedido_id:
            fila_pedido = i + 1
            break

    if not fila_pedido:
        return "Pedido no encontrado", 404
    
    monto_raw = request.form["monto"]
    print("MONTO RECIBIDO:", monto_raw)
    try:
        monto_float = float(monto_raw)
        monto_formateado = "{:,.2f}".format(monto_float).replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        monto_formateado = monto_raw  # Si falla, dejar el valor original

    from datetime import datetime

    # Convertir fecha_entrega de YYYY-MM-DD a DD/MM/YYYY
    try:
        fecha_raw = request.form["fecha_entrega"]
        fecha_formateada = datetime.strptime(fecha_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except:
        fecha_formateada = request.form["fecha_entrega"]  # Si falla, lo deja como vino

    fecha_real = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updates = [
        {"range": f"B{fila_pedido}", "values": [[request.form["dni"]]]},
        {"range": f"C{fila_pedido}", "values": [[request.form["vendedor"]]]},
        {"range": f"D{fila_pedido}", "values": [[request.form["cliente"]]]},
        {"range": f"E{fila_pedido}", "values": [[request.form["direccion"]]]},
        {"range": f"F{fila_pedido}", "values": [[request.form["telefono"]]]},
        {"range": f"G{fila_pedido}", "values": [[request.form["email"]]]},
        {"range": f"H{fila_pedido}", "values": [[request.form["fecha_nacimiento"]]]},
        {"range": f"I{fila_pedido}", "values": [[request.form["sexo_cliente"]]]},
        {"range": f"J{fila_pedido}", "values": [[request.form["fecha_entrega"]]]},
        {"range": f"K{fila_pedido}", "values": [[request.form["horario_entrega"]]]},
        {"range": f"L{fila_pedido}", "values": [[request.form["metodo_pago"]]]},
        {"range": f"M{fila_pedido}", "values": [[monto_formateado]]},  # Monto formateado
        {"range": f"N{fila_pedido}", "values": [[request.form["pagado"]]]},
        {"range": f"Q{fila_pedido}", "values": [[request.form["estado"]]]},
        {"range": f"S{fila_pedido}", "values": [[request.form["zona_envio"]]]},
        {"range": f"T{fila_pedido}", "values": [[request.form["observaciones"]]]},
        {"range": f"U{fila_pedido}", "values": [[request.form["descuentoOn"]]]},  # Descuento como string
        {"range": f"V{fila_pedido}", "values": [[fecha_formateada]]},  # Fecha de ingreso formateada
        {"range": f"W{fila_pedido}", "values": [[request.form["banco"]]]},
        {"range": f"X{fila_pedido}", "values": [[request.form["local"]]]},
        {"range": f"Y{fila_pedido}", "values": [[request.form["pidio"]]]}
        ]

    if "productos[]" in request.form:
        productos = request.form.getlist("productos[]")
        nombres = [precios.get(p, {}).get("nombre", 0) for p in productos]
        cantidades = [str(float(cantidad)) for cantidad in request.form.getlist("cantidades[]")] # Conversion a float y luego a string
        updates.append({"range": f"O{fila_pedido}", "values": [[",".join(nombres)]]})
        updates.append({"range": f"P{fila_pedido}", "values": [[",".join(cantidades)]]})

    hoja_pedidos.batch_update(updates)

    return redirect(url_for("editar_pedidos"))

@app.route("/eliminar_pedido/<pedido_id>", methods=["POST"])
def eliminar_pedido(pedido_id):
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Pedidos")
    pedidos = hoja_pedidos.get_all_values()

    try:
        fila_a_eliminar = None
        for i, row in enumerate(pedidos):
            if str(row[0]).strip() == str(pedido_id).strip():
                fila_a_eliminar = i + 1
                break

        if fila_a_eliminar:
            hoja_pedidos.delete_rows(fila_a_eliminar)
            return '', 204
        else:
            return f"No se encontró pedido {pedido_id}", 404

    except Exception as e:
        print(f"Error interno al eliminar: {e}")
        return f"Error interno del servidor: {e}", 500

@app.route('/ingresar_stock', methods=["GET", "POST"])
@rol_requerido("admin", "vendedor")
def ingresar_stock():
    precios = cargar_precios()

    if request.method == "POST":
        sheet = conectar_sheets()
        hoja_stock = sheet.worksheet("Stock")
        valores = hoja_stock.get_all_values()
        ultima_fila = valores[-1]
        encabezados = valores[0]
        index_id = encabezados.index("ID_lote")
        id_stock = int(ultima_fila[index_id]) + 1

        vendedor = request.form["vendedor"]
        productos = request.form.getlist("productos[]")  # es el ID
        cantidades = [float(c) for c in request.form.getlist("cantidades[]")]
        observaciones = request.form.get("observaciones", "")
        fecha_str = request.form["fecha"]

        try:
            fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d")

        fecha_formateada = fecha_obj.strftime("%Y-%m-%d")
        ingreso_fecha_hora = datetime.now().strftime("%Y-%m-%d")

        jsonProductos = cargar_precios()

        for producto, cantidad in zip(productos, cantidades):
            nombre = str(jsonProductos[producto]["nombre"])
            hoja_stock.append_row(
                [fecha_formateada, vendedor, nombre, cantidad, observaciones, ingreso_fecha_hora, producto, str(id_stock)],
                value_input_option="USER_ENTERED"
            )

        # Ajustar materia prima
        with open("modules/materia_prima.json", "r", encoding="utf-8") as f:
            materia_prima = json.load(f)

        with open("modules/recetas_materias.json", "r", encoding="utf-8") as f:
            recetas_materias = json.load(f)

        materia_prima_necesaria = {}
        for producto, cantidad in zip(productos, cantidades):
            recetas = [r for r in recetas_materias if str(r["ID_receta"]) == str(producto)]
            for receta in recetas:
                materia = receta["Materia"]
                cantidad_necesaria = receta["Cantidad"] * cantidad
                materia_prima_necesaria[materia] = materia_prima_necesaria.get(materia, 0) + cantidad_necesaria

        for materia, cantidad in materia_prima_necesaria.items():
            if materia in materia_prima:
                materia_prima[materia]["Cantidad"] -= cantidad

        with open("modules/materia_prima.json", "w", encoding="utf-8") as f:
            json.dump(materia_prima, f, indent=4, ensure_ascii=False)

        hoja_materia = sheet.worksheet("Materia prima ingresos")
        for materia, cantidad in materia_prima_necesaria.items():
            unidad = materia_prima.get(materia, {}).get("Unidad", "sin unidad")
            hoja_materia.append_row(
                [fecha_formateada, vendedor, materia, unidad, -cantidad, f"Ajuste de materia prima por lote {id_stock}", ingreso_fecha_hora, id_stock, "-"],
                value_input_option="USER_ENTERED"
            )

        flash("Stock guardado correctamente.", "success")
        return redirect(url_for("ingresar_stock"))

    # GET: mostrar formulario
    return render_template("ingresar_stock.html", precios_productos=precios)


@app.route('/ingresar_materia_prima')
@rol_requerido("admin", "cocinero")
def ingresar_materia_prima():
    materia_prima = cargar_materia_prima()
    return render_template("ingresar_materia_prima.html", materia_prima=materia_prima)

@app.route('/ingresar_desposte', methods=["GET"])
@rol_requerido("admin", "cocinero")
def ingresar_desposte():
    with open("modules/materia_prima.json", "r", encoding="utf-8") as f:
        materias_primas = json.load(f)
    return render_template("ingresar_desposte.html", materias_primas=materias_primas)

@app.route('/crear_receta')
@rol_requerido("admin", "cocinero")
def crear_receta():
    with open("modules/precios_productos.json", "r", encoding="utf-8") as f:
        productos = json.load(f)
    with open("modules/materia_prima.json", "r", encoding="utf-8") as f:
        materias_primas = json.load(f)
    return render_template("crear_receta.html", productos=productos, materias_primas=materias_primas)


@app.route('/guardar_materia_prima', methods=["POST"])
@rol_requerido("admin", "cocinero")
def guardar_materia_prima():
    sheet = conectar_sheets()
    hoja_materia = sheet.worksheet("Materia prima ingresos")  # ✅ hoja específica
    
    vendedor = request.form["vendedor"]
    productos = request.form.getlist("productos[]")
    cantidades = [float(c) for c in request.form.getlist("cantidades[]")]
    observaciones = request.form.get("observaciones", "")

    with open("modules/materia_prima.json", encoding="utf-8") as f:
        materia_prima_info = json.load(f)

    for prod, cant in zip(productos, cantidades):
        cant = float(cant)
        if prod in materia_prima_info:
            materia_prima_info[prod]["Cantidad"] = float(materia_prima_info[prod]["Cantidad"]) + cant
        else:
            print(f"⚠ Producto no encontrado en JSON: {prod}")

    with open("modules/materia_prima.json", "w", encoding="utf-8") as f:
        json.dump(materia_prima_info, f, indent=4, ensure_ascii=False)

    fecha_str = request.form["fecha"]
    try:
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d")

    fecha_formateada = fecha_obj.strftime("%Y-%m-%d")
    ingreso_fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for producto, cantidad in zip(productos, cantidades):
        unidad = materia_prima_info.get(producto, {}).get("Unidad", "sin unidad")

        hoja_materia.append_row(
            [fecha_formateada, vendedor, producto, unidad, cantidad, observaciones, ingreso_fecha_hora],
            value_input_option="USER_ENTERED"
        )

    return redirect(url_for("ingresar_materia_prima"))

@app.route('/guardar_desposte', methods=['POST'])
def guardar_desposte():
    sheet = conectar_sheets()
    hoja_materia = sheet.worksheet("Materia prima ingresos")  # ✅ hoja específica

    tipo = request.form['tipo_animal']
    peso_animal = float(request.form['peso_animal'])
    nombres = request.form.getlist('nombres_partes[]')
    pesos = list(map(float, request.form.getlist('pesos_partes[]')))
    observaciones = request.form.get("observaciones", "")

    partes = {}
    for nombre, peso in zip(nombres, pesos):
        partes[nombre] = partes.get(nombre, 0) + peso

    peso_aprovechado = sum(partes.values())

    # Cargar archivo actual
    with open("modules/desposte.json", "r", encoding="utf-8") as f:
        historial = json.load(f)

    next_id = str(max([int(x["id"]) for x in historial], default=0) + 1)

    nuevo_registro = {
        "id": next_id,
        "animal": tipo,
        "peso_total": peso_animal,
        "peso_aprovechado": peso_aprovechado,
        "porcentaje_aprovechado": round((peso_aprovechado/peso_animal *100),2),
        "partes": partes
    }

    historial.append(nuevo_registro)

    with open("modules/desposte.json", "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=2, ensure_ascii=False)

    # ACTUALIZAR JSON DE MATERIAS PRIMAS
    with open("modules/materia_prima.json", "r", encoding="utf-8") as f:
        stock = json.load(f)

    for nombre, peso in partes.items():
        if nombre in stock:
            stock[nombre]["Cantidad"] = float(stock[nombre]["Cantidad"]) + float(peso)
        else:
            print(f"⚠ La parte '{nombre}' no está en el JSON de materias primas.")

    with open("modules/materia_prima.json", "w", encoding="utf-8") as f:
        json.dump(stock, f, indent=2, ensure_ascii=False)

    fecha_str = request.form["fecha"]
    try:
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d")

    fecha_formateada = fecha_obj.strftime("%Y-%m-%d")
    ingreso_fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for producto, cantidad in partes.items():
        unidad = stock.get(producto, {}).get("Unidad", "sin unidad")

        hoja_materia.append_row(
            [fecha_formateada, "desposte", producto, unidad, cantidad, observaciones, ingreso_fecha_hora, "-", next_id],
            value_input_option="USER_ENTERED"
        )
    return redirect(url_for("ver_desposte"))


@app.route('/guardar_receta', methods=["POST"])
def guardar_receta():
    producto_id = request.form.get("producto_id")
    materias = request.form.getlist("materias[]")
    cantidades = list(map(float, request.form.getlist("cantidades[]")))

    with open("modules/materia_prima.json", "r", encoding="utf-8") as f:
        stock_info = json.load(f)

    with open("modules/recetas_materias.json", "r", encoding="utf-8") as f:
        recetas = json.load(f)

    # Eliminar recetas existentes con ese ID_receta
    recetas = [r for r in recetas if str(r["ID_receta"]) != str(producto_id)]

    # Agregar nuevas entradas
    for materia, cantidad in zip(materias, cantidades):
        if materia not in stock_info:
            print(f"⚠ No existe la materia prima: {materia}")
            continue
        entry = {
            "ID_receta": int(producto_id),
            "ID_materia_prima": stock_info[materia]["ID"],
            "Materia": materia,
            "Unidad": stock_info[materia]["Unidad"],
            "Categoria": stock_info[materia]["Categoria"],
            "Cantidad": cantidad
        }
        recetas.append(entry)

    with open("modules/recetas_materias.json", "w", encoding="utf-8") as f:
        json.dump(recetas, f, indent=4, ensure_ascii=False)

    return redirect(url_for("ver_recetas"))


@app.route('/ver_salida')
@rol_requerido("admin", "vendedor")
def ver_caja_salida():
    
    return render_template("caja_salida.html")


from datetime import datetime

@app.route('/caja_salida', methods=["POST"])
@rol_requerido("admin", "vendedor")
def caja_salida():
    sheet = conectar_sheets()
    hoja_caja_salida = sheet.worksheet("Salida Caja")

    # Convertir string a objeto datetime
    fecha_str = request.form["fecha"]  # '2025-04-23'
    fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d")

    # 🔁 Convertir a string tipo fecha para Sheets
    fecha = fecha_obj.strftime("%Y-%m-%d")

    vendedor = request.form["vendedor"]
    detalle = request.form.get("detalle")
    monto = int(request.form["monto"])

    # Enviar a Sheets como string formateado
    hoja_caja_salida.append_row([fecha, vendedor, detalle, monto], value_input_option="USER_ENTERED")

    return redirect(url_for("ver_caja_salida"))


@app.route('/ver_salidas')
@rol_requerido("admin", "vendedor")
def ver_salidas():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Salida Caja")
    salidas = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas
    if not salidas:
        return render_template("ver_salidas.html", salidas=[])
    # Convertimos los datos en una lista de diccionarios
    headers = salidas[0]  # La primera fila son los encabezados
    datos_salidas = [dict(zip(headers, row)) for row in salidas[1:11]]  # Excluimos la primera fila

    return render_template("ver_salidas.html",datos_salidas=datos_salidas)



@app.route('/pedido/<pedido_id>')
@rol_requerido("admin", "vendedor")
def detalle_pedido(pedido_id):
    """Muestra la página de detalle de un pedido específico, uniendo productos y cantidades,
    enviándolos como listas."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Pedidos")  # Asegúrate del nombre de tu hoja

    pedidos_raw = hoja_pedidos.get_all_values()
    headers = pedidos_raw[0]
    pedidos = [dict(zip(headers, row)) for row in pedidos_raw[1:]]

    pedido_seleccionado = None
    for pedido in pedidos:
        if pedido["ID"] == pedido_id:
            pedido_seleccionado = pedido
            break

    if pedido_seleccionado:
        # Procesar la información de los productos y cantidades
        productos_str = pedido_seleccionado.get("Productos", "")
        cantidades_str = pedido_seleccionado.get("Cantidades", "")  # Asumiendo que las cantidades están en una columna "Cantidades"
        productos = [p.strip() for p in productos_str.split(',')] if productos_str else []
        cantidades_raw = [c.strip() for c in cantidades_str.split(',')] if cantidades_str else []

        cantidades = []
        for cant_str in cantidades_raw:
            try:
                cant_float = float(cant_str)
                cant_int = int(cant_float)
                if cant_float == cant_int:
                    cantidades.append(cant_int)
                else:
                    cantidades.append(cant_float)
            except ValueError:
                cantidades.append(cant_str)  # Si no se puede convertir, mantener el string original

        productos_con_cantidad = []
        if len(productos) == len(cantidades):
            for i in range(len(productos)):
                productos_con_cantidad.append([productos[i], cantidades[i]])  # Crear una lista con producto y cantidad
        else:
            print(f"Advertencia: Desajuste de productos/cantidades para el ID: {pedido_seleccionado.get('ID')}")
            productos_con_cantidad = [[p, 'N/A'] for p in productos]  # O alguna otra lógica para manejar el desajuste

        return render_template('detalle_pedido.html', pedido=pedido_seleccionado, productos=productos_con_cantidad)
    else:
        flash('Pedido no encontrado.', 'error')
        return redirect(url_for('ver_pedidos'))  # O la página donde está la tabla
    



@app.route("/generar_pdf/<int:pedido_id>")
def generar_pdf_pedido(pedido_id):
    sheet = conectar_sheets()
    hoja = sheet.worksheet("Pedidos")
    pedidos = hoja.get_all_records()
    precios_productos = cargar_precios()

    for pedido_individual in pedidos:
        try:
            if int(pedido_individual["ID"] == pedido_id):
                pedido = pedido_individual
        except: 
            print("Hay filas vacias, arreglar.")

    if not pedido:
        return "Pedido no encontrado", 404

    # Obtener productos y cantidades directamente del pedido
    productos = [item.strip() for item in pedido["Productos"].split(",")]  # Suponiendo que Productos es una cadena separada por comas
   # Manejo seguro de cantidades
    cantidades_raw = pedido["Cantidades"]

    if isinstance(cantidades_raw, (int, float)):
        cantidades = [float(cantidades_raw)]  # una sola cantidad como float
    elif isinstance(cantidades_raw, str):
        if ',' in cantidades_raw:
            cantidades = [float(c.strip()) for c in cantidades_raw.split(",")]
        else:
            cantidades = [float(cantidades_raw.strip())]  # una sola cantidad como texto
    else:
        print("Formato inesperado para Cantidades:", cantidades_raw)
        return "Error en el formato de Cantidades", 500

    # Verificar que las listas tengan la misma longitud
    if len(productos) != len(cantidades):
        print("Error: La cantidad de productos no coincide con la cantidad de cantidades.")
        return "Error en los datos del pedido", 500  # O manejar el error como prefieras

    precios = [precios_productos.get(p.strip(), {}).get("precio", 0) for p in productos]


    # Asegúrate de que monto sea float (manejo de errores adicional)
    try:
        monto = float(pedido["Monto"].replace("$", "").replace(",", "")) if isinstance(pedido["Monto"], str) else float(pedido["Monto"])
    except (ValueError, AttributeError, TypeError):
        print(f"Error al convertir monto: {pedido['Monto']}")
        monto = 0.0  # Valor por defecto para monto
    # Convertir costo de envío a número, tratando "Sin envío" como 0
    costo_envio_raw = pedido.get("Costo Envio a Domicilio", "")
    try:
        zona_envio = float(str(costo_envio_raw).replace("$", "").replace(",", "").strip()) if "sin" not in str(costo_envio_raw).lower() else 0.0
    except (ValueError, TypeError):
        print(f"Error al interpretar costo de envío: {costo_envio_raw}")
        zona_envio = 0.0
 
    return generar_pdf_detalles_pedido(
        pedido_id=pedido["ID"],
        cliente=pedido["Cliente"],
        fecha_entrega=pedido["Fecha de Entrega"],
        horario_entrega=pedido["Horario de Entrega"],
        metodo_pago=pedido["Método de Pago"],
        monto=monto,
        descuento=pedido["Descuento"],
        pagado=pedido["Pagado"],
        productos=productos,  # Reutilizamos la lista 'productos'
        cantidades=cantidades,  # Reutilizamos la lista 'cantidades'
        precios=precios,
        direccion=pedido["Dirección"],
        telefono=pedido["Teléfono"],
        observaciones=pedido["Observaciones"],
        zona_envio=zona_envio,  # Usamos la variable zona_envio ya convertida
    )



@app.route('/editar_pedido/pedido_id')
@rol_requerido("admin", "vendedor")
def detalle_editar_pedido(pedido_id):
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Pedidos")  # Asegúrate del nombre de tu hoja

    pedidos_raw = hoja_pedidos.get_all_values()
    headers = pedidos_raw[0]
    pedidos = [dict(zip(headers, row)) for row in pedidos_raw[1:]]

    pedido_seleccionado = None
    for pedido in pedidos:
        if pedido["ID"] == pedido_id:
            pedido_seleccionado = pedido
            break

    if pedido_seleccionado:
        # Procesar la información de los productos y cantidades
        productos_str = pedido_seleccionado.get("Productos", "")
        cantidades_str = pedido_seleccionado.get("Cantidades", "")  # Asumiendo que las cantidades están en una columna "Cantidades"
        productos = [p.strip() for p in productos_str.split(',')] if productos_str else []
        cantidades_raw = [c.strip() for c in cantidades_str.split(',')] if cantidades_str else []

        cantidades = []
        for cant_str in cantidades_raw:
            try:
                cant_float = float(cant_str)
                cant_int = int(cant_float)
                if cant_float == cant_int:
                    cantidades.append(cant_int)
                else:
                    cantidades.append(cant_float)
            except ValueError:
                cantidades.append(cant_str)  # Si no se puede convertir, mantener el string original

        productos_con_cantidad = []
        if len(productos) == len(cantidades):
            for i in range(len(productos)):
                productos_con_cantidad.append([productos[i], cantidades[i]])  # Crear una lista con producto y cantidad
        else:
            print(f"Advertencia: Desajuste de productos/cantidades para el ID: {pedido_seleccionado.get('ID')}")
            productos_con_cantidad = [[p, 'N/A'] for p in productos]  # O alguna otra lógica para manejar el desajuste

        return render_template('detalle_pedido_editar.html', pedido=pedido_seleccionado, productos=productos_con_cantidad)
    else:
        flash('Pedido no encontrado.', 'error')
        return redirect(url_for('editar_pedidos'))  # O la página donde está la tabla



@app.route("/ver_precios", methods=["GET", "POST"])
@rol_requerido("admin", "vendedor")
def ver_precios():
    json_path = os.path.join("modules", "precios_productos.json")

    if request.method == "POST":
        nuevos_precios = {}
        total = int(request.form.get("total_productos", 0))

        # Obtener IDs existentes si estamos editando productos existentes
        for i in range(1, total + 1):
            id_existente = request.form.get(f"id_existente_{i}")
            nombre = request.form.get(f"nombre_existente_{i}", "").strip()
            precio = request.form.get(f"precio_existente_{i}")
            eliminar = request.form.get(f"eliminar_{i}")

            if nombre and precio and not eliminar:
                nuevos_precios[id_existente] = {
                    "nombre": nombre,
                    "precio": int(precio)
                }


        # Agregar producto nuevo si fue completado
        nuevo_nombre = request.form.get("nuevo_nombre", "").strip()
        nuevo_precio = request.form.get("nuevo_precio", "").strip()
        nuevo_id = request.form.get("nuevo_id", "").strip()
        if nuevo_nombre and nuevo_precio:
            nuevos_precios[str(nuevo_id)] = {
                "nombre": nuevo_nombre,
                "precio": int(nuevo_precio)
            }

        # Guardar en el archivo JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(nuevos_precios, f, indent=4, ensure_ascii=False)

        flash("Lista de precios actualizada con éxito")
        return redirect(url_for("ver_precios"))

    # GET: leer y ordenar productos por nombre
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Ordenar por nombre
    precios_ordenados = dict(sorted(data.items(), key=lambda x: x[1]["nombre"]))

    return render_template("ver_precios.html", precios=precios_ordenados)





@app.route('/ver_stock')
@rol_requerido("admin", "vendedor")
def ver_stock():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Nuevo Stock")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("stock_nuevo.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("stock_nuevo.html", stock=datos_stock)

@app.route("/ver_materia_prima", methods=["GET", "POST"])
@rol_requerido("admin", "cocinero")
def ver_materia_prima():
    json_path = os.path.join("modules", "materia_prima.json")

    if request.method == "POST":
        nueva_materia = {}
        total = int(request.form.get("total_productos", 0))

        for i in range(1, total + 1):
            nombre = request.form.get(f"nombre_existente_{i}", "").strip()
            id_ = request.form.get(f"id_existente_{i}")
            unidad = request.form.get(f"unidad_existente_{i}", "").strip()
            categoria = request.form.get(f"categoria_existente_{i}", "").strip()
            cantidad = float(request.form.get(f"cantidad_existente_{i}", "").strip())
            eliminar = request.form.get(f"eliminar_{i}")

            if nombre and id_ and unidad and categoria and not eliminar:
                nueva_materia[nombre] = {
                    "ID": int(id_),
                    "Unidad": unidad,
                    "Categoria": categoria,
                    "Cantidad": cantidad
                }

        # Evitar duplicados
        nuevo_nombre = request.form.get("nuevo_nombre", "").strip()
        nuevo_id = request.form.get("nuevo_id", "").strip()
        nuevo_unidad = request.form.get("nuevo_unidad", "").strip()
        nuevo_categoria = request.form.get("nuevo_categoria", "").strip()

        if nuevo_nombre and nuevo_id and nuevo_unidad and nuevo_categoria:
            if nuevo_nombre not in nueva_materia:
                nueva_materia[nuevo_nombre] = {
                    "ID": int(nuevo_id),
                    "Unidad": nuevo_unidad,
                    "Categoria": nuevo_categoria,
                    "Cantidad": cantidad
                }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(nueva_materia.items(), key=lambda x: x[1]["ID"])), f, indent=4, ensure_ascii=False)

        flash("Lista de materia prima actualizada con éxito")
        return redirect(url_for("ver_materia_prima"))

    with open(json_path, "r", encoding="utf-8") as f:
        materia = json.load(f)
    materia_ordenada = dict(sorted(materia.items(), key=lambda item: item[1]["ID"]))
    # Calcular siguiente ID incremental
    siguiente_id = max([v["ID"] for v in materia.values()] + [0]) + 1

    return render_template("ver_materia_prima.html", materia=materia_ordenada, siguiente_id=siguiente_id)

@app.route('/ver_desposte')
def ver_desposte():
    try:
        with open("modules/desposte.json", "r", encoding="utf-8") as f:
            historial = json.load(f)
    except FileNotFoundError:
        historial = []

    return render_template("ver_desposte.html", historial=historial)

@app.route('/ver_recetas')
def ver_recetas():
    try:
        with open("modules/recetas_materias.json", "r", encoding="utf-8") as f:
            recetas_raw = json.load(f)
    except FileNotFoundError:
        recetas_raw = []

    with open("modules/precios_productos.json", "r", encoding="utf-8") as f:
        productos_info = json.load(f)

    recetas = {}

    for r in recetas_raw:
        prod_id = str(r["ID_receta"])
        if prod_id not in recetas:
            nombre = productos_info.get(prod_id, {}).get("nombre", "Sin nombre")
            recetas[prod_id] = {"nombre": nombre, "ingredientes": []}
        recetas[prod_id]["ingredientes"].append(r)

    return render_template("ver_recetas.html", recetas=recetas)


@app.route('/ver_stock_entrada')
@rol_requerido("admin", "vendedor")
def ver_stock_entrada():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Stock")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("entrada_stock.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[-25:]]  # Excluimos la primera fila

    return render_template("entrada_stock.html", stock=datos_stock)

@app.route('/ver_stock_entrada_total')
@rol_requerido("admin", "vendedor")
def ver_stock_entrada_total():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Stock")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("entrada_stock_total.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("entrada_stock_total.html", stock=datos_stock)


@app.route('/ver_stock/milanesas')
@rol_requerido("admin", "vendedor")
def ver_stock_milanesas():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Milanesas")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("vista_stock_milanesas.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("vista_stock_milanesas.html", stock=datos_stock)

@app.route('/ver_stock/frescos')
@rol_requerido("admin", "vendedor")
def ver_stock_frescos():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Frescos")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("vista_stock_frescos.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("vista_stock_frescos.html", stock=datos_stock)

@app.route('/ver_stock/bebidas')
@rol_requerido("admin", "vendedor")
def ver_stock_bebidas():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Bebidas")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("vista_stock_bebidas.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("vista_stock_bebidas.html", stock=datos_stock)

@app.route('/ver_stock/desmechados')
@rol_requerido("admin", "vendedor")
def ver_stock_desmechados():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Otros")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("vista_stock_desmechados.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("vista_stock_desmechados.html", stock=datos_stock)

@app.route('/ver_stock/empanadas')
@rol_requerido("admin", "vendedor")
def ver_stock_empanadas():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Empanadas")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("vista_stock_empanadas.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("vista_stock_empanadas.html", stock=datos_stock)

@app.route('/ver_stock/hamburguesas')
@rol_requerido("admin", "vendedor")
def ver_stock_carnes():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Carnes")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("vista_stock_carnes.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("vista_stock_carnes.html", stock=datos_stock)

@app.route('/ver_stock/nuevo')
@rol_requerido("admin", "vendedor")
def ver_stock_nuevo():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Nuevo Stock")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("stock_nuevo.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("stock_nuevo.html", stock=datos_stock)

@app.route('/ver_stock/pizzas')
@rol_requerido("admin", "vendedor")
def ver_stock_pizzas():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Pizzas")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("vista_stock_pizzas.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("vista_stock_pizzas.html", stock=datos_stock)

@app.route('/ver_stock/etiquetas')
@rol_requerido("admin", "vendedor")
def ver_stock_etiquetas():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Etiquetas")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("vista_stock_etiquetas.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("vista_stock_etiquetas.html", stock=datos_stock)

@app.route('/ver_stock/promos')
@rol_requerido("admin", "vendedor")
def ver_stock_promos():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Promos")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    stock = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not stock:
        return render_template("vista_stock_promos.html", stock=[])

    # Convertimos los datos en una lista de diccionarios
    headers = stock[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in stock[1:]]  # Excluimos la primera fila

    return render_template("vista_stock_promos.html", stock=datos_stock)

@app.route('/caja_diaria')
@rol_requerido("admin", "vendedor")
def ver_caja_diaria():
    """Trae los pedidos de Google Sheets y los muestra en una tabla."""
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("CAJA HOY")  # Asegurate de que el nombre coincida con el de la hoja en Google Sheets

    pedidos = hoja_pedidos.get_all_values()  # Obtiene todos los pedidos en forma de lista de listas

    if not pedidos:
        return render_template("vista_caja.html", pedidos=[])

    # Convertimos los datos en una lista de diccionarios
    headers = pedidos[0]  # La primera fila son los encabezados
    datos_stock = [dict(zip(headers, row)) for row in pedidos[1:]]  # Excluimos la primera fila

    return render_template("vista_caja.html", pedidos=datos_stock)


@app.route("/editar_pedido_form/<pedido_id>")
@rol_requerido("admin", "vendedor")
def editar_pedido_form(pedido_id):
    sheet = conectar_sheets()
    hoja = sheet.worksheet("Pedidos")
    pedidos = hoja.get_all_values()
    headers = pedidos[0]
    pedido = next((dict(zip(headers, row)) for row in pedidos[1:] if row[0] == pedido_id), None)
    # Convertir fechas al formato YYYY-MM-DD para los inputs HTML
    for campo_fecha in ["Fecha de Entrega", "Fecha de Nacimiento"]:
        valor = pedido.get(campo_fecha, "")
        try:
            if "/" in valor:
                pedido[campo_fecha] = datetime.strptime(valor, "%d/%m/%Y").strftime("%Y-%m-%d")
        except:
            pass  # Si falla, lo deja como estaba
    if not pedido:
        flash("Pedido no encontrado", "error")
        return redirect(url_for("editar_pedidos"))
    # Procesar productos y cantidades en forma de lista
    productos_raw = pedido.get("Productos", "").split(",")
    cantidades_raw = pedido.get("Cantidades", "").split(",")

    # Limpiar y normalizar
    productos = [p.strip() for p in productos_raw if p.strip()]
    cantidades = [c.strip().replace("u", "").replace(",", ".") for c in cantidades_raw if c.strip()]

    # Emparejar (por si vienen desfasados)
    while len(cantidades) < len(productos):
        cantidades.append("1")
    while len(productos) < len(cantidades):
        productos.append("Producto desconocido")

    precios = cargar_precios()  # esto devuelve un dict de ID → {nombre, precio}

    # Invertir precios para buscar ID a partir del nombre
    nombre_a_id = {v["nombre"]: k for k, v in precios.items()}

    productos_con_ids = []
    for nombre, cantidad in zip(productos, cantidades):
        producto_id = nombre_a_id.get(nombre, None)
        if producto_id:
            productos_con_ids.append((producto_id, cantidad))
        else:
            productos_con_ids.append(("0", cantidad))  # "0" si no se encontró, para que no falle

    pedido["__productos"] = productos_con_ids
    return render_template("form_editar_pedido.html", pedido=pedido, precios_productos=precios)



@app.route('/exportar_montos_clientes')
@rol_requerido("admin", "vendedor")
def exportar_montos_clientes():
    import pandas as pd
    from datetime import datetime, timedelta

    # Cargar clientes
    with open('modules/clientes.json', 'r', encoding='utf-8') as f:
        clientes = json.load(f)
    for cliente in clientes:
        cliente["nombre_completo"] = (cliente["nombre"] + " " + cliente["apellido"]).strip().lower()
    nombres_clientes = [c["nombre_completo"] for c in clientes]

    # Cargar pedidos desde Google Sheets
    sheet = conectar_sheets()
    hoja_pedidos = sheet.worksheet("Pedidos")
    pedidos = hoja_pedidos.get_all_records()
    df_pedidos = pd.DataFrame(pedidos)

    # Filtrar pedidos por clientes existentes (comparando en minúsculas)
    df_pedidos["Cliente_lower"] = df_pedidos["Cliente"].astype(str).str.strip().str.lower()
    pedidos_filtrados = df_pedidos[df_pedidos['Cliente_lower'].isin(nombres_clientes)].copy()

    # Convertir la columna de fecha a datetime (maneja ambos formatos)
    def parse_fecha(fecha):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(str(fecha), fmt)
            except Exception:
                continue
        return None

    pedidos_filtrados["Fecha_dt"] = pedidos_filtrados["Fecha de Entrega"].apply(parse_fecha)
    fecha_limite = datetime.now() - timedelta(days=28)
    pedidos_filtrados = pedidos_filtrados[pedidos_filtrados["Fecha_dt"] >= fecha_limite]

    # Limpiar y convertir el monto
    pedidos_filtrados['Monto'] = (
        pedidos_filtrados['Monto']
        .astype(str)
        .str.replace('$', '', regex=False)
        .str.replace(',', '', regex=False)
        .astype(float)
    )

    # Agrupar por cliente y sumar el monto
    resultado = (
        pedidos_filtrados[["Cliente", "Monto"]]
        .groupby("Cliente")["Monto"]
        .sum()
        .sort_values(ascending=False)
    )

    # Crear lista de tickets
    tickets = []
    for cliente, monto in resultado.items():
        cantidad_tickets = int(monto)
        for i in range(1, cantidad_tickets + 1):
            tickets.append({"Cliente": f"{cliente}{i}", "Ticket": i})

    df_tickets = pd.DataFrame(tickets)
    df_tickets.to_excel("resultado.xlsx", index=False)

    # Calcular porcentajes
    total_tickets = df_tickets.shape[0]
    if total_tickets > 0:
        df_porcentajes = df_tickets.groupby(df_tickets['Cliente'].str.replace(r'\d+$', '', regex=True)).size().reset_index(name='Tickets')
        df_porcentajes['Porcentaje'] = (df_porcentajes['Tickets'] / total_tickets * 100).round(2)
        df_porcentajes = df_porcentajes.rename(columns={'Cliente': 'Nombre'})
        df_porcentajes.to_excel("porcentajes.xlsx", index=False)
    else:
        df_porcentajes = pd.DataFrame(columns=['Nombre', 'Tickets', 'Porcentaje'])
        df_porcentajes.to_excel("porcentajes.xlsx", index=False)

    flash("Archivos resultado.xlsx y porcentajes.xlsx generados correctamente", "success")
    return redirect(url_for("index"))



@app.route('/sorteo_ruleta')
@rol_requerido("admin")
def sorteo_ruleta():
    import pandas as pd
    try:
        df = pd.read_excel("porcentajes.xlsx")
        participantes = df.to_dict(orient="records")
    except Exception:
        participantes = []
    return render_template("ruleta.html", participantes=participantes)



@app.route('/sorteo_ruleta_todos')
@rol_requerido("admin")
def sorteo_ruleta_todos():
    with open('modules/clientes.json', 'r', encoding='utf-8') as f:
        clientes = json.load(f)
    participantes = []
    if clientes:
        porcentaje = round(100 / len(clientes), 2)
        for c in clientes:
            nombre = f"{c.get('nombre','').strip()} {c.get('apellido','').strip()}".strip()
            participantes.append({"Nombre": nombre, "Porcentaje": porcentaje})
    return render_template("ruleta_todos.html", participantes=participantes)

# http://localhost:5000/exportar_montos_clientes

@app.route('/editar_clientes')
@rol_requerido("admin", "vendedor")
def editar_clientes():
    with open('modules/clientes.json', 'r', encoding='utf-8') as f:
        clientes = json.load(f)
    return render_template('editar_clientes.html', clientes=clientes)

@app.route('/editar_cliente/<dni>', methods=['GET', 'POST'])
@rol_requerido("admin", "vendedor")
def editar_cliente(dni):
    with open('modules/clientes.json', 'r', encoding='utf-8') as f:
        clientes = json.load(f)
    cliente = next((c for c in clientes if str(c['dni']) == str(dni)), None)
    if not cliente:
        flash('Cliente no encontrado', 'error')
        return redirect(url_for('editar_clientes'))

    if request.method == 'POST':
        # Actualizar datos
        cliente['nombre'] = request.form['nombre'].strip()
        cliente['apellido'] = request.form['apellido'].strip()
        cliente['direccion'] = request.form['direccion'].strip()
        cliente['telefono'] = request.form['telefono'].strip()
        cliente['email'] = request.form['email'].strip()
        cliente['fecha_nacimiento'] = request.form['fecha_nacimiento'].strip()
        cliente['sexo'] = request.form['sexo'].strip()
        # Guardar cambios
        with open('modules/clientes.json', 'w', encoding='utf-8') as f:
            json.dump(clientes, f, indent=2, ensure_ascii=False)
        flash('Cliente actualizado correctamente', 'success')
        return redirect(url_for('editar_clientes'))

    return render_template('form_editar_cliente.html', cliente=cliente)



@app.route('/generar_flujo')
def generar_flujo():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credenciales.json", scope)
    
    client = gspread.authorize(creds)
    sheet = client.open("flujo_produccion").worksheet("flujo_produccion.csv")
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    output_folder = "diagramas_api"
    os.makedirs(output_folder, exist_ok=True)

    imagenes = []
    for idx, row in df.iterrows():
        producto = row['Producto']
        pasos = row.dropna()[1:]

        # Armar el código DOT
        dot_code = "digraph G {\n"
        dot_code += '  rankdir=LR;\n'
        dot_code += '  node [shape=box, style=filled, fillcolor=lightgrey, fontname="Helvetica"];\n'

        for i, paso in enumerate(pasos):
            if paso and len(paso) > 1:
                dot_code += f'  n{i} [label="{paso}"];\n'
                if i > 0:
                    dot_code += f'  n{i-1} -> n{i};\n'
        dot_code += "}"

        # Llamar a la API de QuickChart
        api_url = 'https://quickchart.io/graphviz'
        params = {'graph': dot_code, 'format': 'png'}
        response = requests.get(api_url, params=params)

        # Guardar imagen
        safe_name = producto.replace(" ", "_").replace("/", "_")
        image_path = os.path.join(output_folder, f"{safe_name}.png")
        with open(image_path, "wb") as f:
            f.write(response.content)
        imagenes.append((image_path, producto))

    # Crear PDF con las imágenes (horizontal)
    pdf_path = "diagramas_flujo.pdf"
    c = canvas.Canvas(pdf_path, pagesize=landscape(letter))
    width, height = landscape(letter)

    for image_path, producto in imagenes:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, height - 50, f"Producto: {producto}")
        img = ImageReader(image_path)
        img_width, img_height = img.getSize()
        max_width = width - 80
        max_height = height - 120
        scale = min(max_width / img_width, max_height / img_height, 1.0)
        draw_width = img_width * scale
        draw_height = img_height * scale
        x = (width - draw_width) / 2
        y = (height - draw_height) / 2 - 30
        c.drawImage(img, x, y, draw_width, draw_height)
        c.showPage()

    c.save()

    response = make_response(send_file(pdf_path, as_attachment=True))
    response.headers["Content-Type"] = "application/pdf"
    return response

@app.route('/generar_flujos')
@rol_requerido("admin")
def generar_flujos():
    return render_template('generar_flujo.html')


@app.route('/verificacion_pagos')
@rol_requerido("admin", "vendedor")
def verificacion_pagos():
    sheet = conectar_sheets()
    hoja = sheet.worksheet("Pedidos")
    pedidos = hoja.get_all_records()

    pedidos_no_pagados = [p for p in pedidos if p.get("Pagado", "").strip().lower() == "no"]

    return render_template("verificacion_pagos.html", pedidos=pedidos_no_pagados)

@app.route('/verificar_pago/<int:pedido_id>')
def editar_pago(pedido_id):
    sheet = conectar_sheets()
    hoja = sheet.worksheet("Pedidos")
    pedidos = hoja.get_all_records()

    pedido = next((p for p in pedidos if int(p["ID"]) == pedido_id), None)
    if not pedido:
        return "Pedido no encontrado", 404
    
    productos_raw = str(pedido["Productos"])
    cantidades_raw = str(pedido["Cantidades"])

    productos = [p.strip() for p in productos_raw.split(",")]
    cantidades = [c.strip() for c in cantidades_raw.split(",")]

    productos_y_cantidades = list(zip(productos, cantidades))
    return render_template("form_verificar_pago.html", pedido=pedido, productos_y_cantidades=productos_y_cantidades)


@app.route('/actualizar_pago', methods=['POST'])
def actualizar_pago():
    pedido_id = int(request.form['id'])
    nuevo_estado = request.form['pagado']

    sheet = conectar_sheets()
    hoja = sheet.worksheet("Pedidos")
    pedidos = hoja.get_all_records()

    fila = next((i for i, p in enumerate(pedidos, start=2) if int(p["ID"]) == pedido_id), None)

    if fila:
        hoja.update_cell(fila, 14, nuevo_estado)  # Columna N
        flash("✅ Estado de pago actualizado correctamente", "success")
    else:
        flash("❌ Pedido no encontrado", "error")

    return redirect(url_for('verificacion_pagos'))

if __name__ == '__main__':
    app.run(debug=True)
