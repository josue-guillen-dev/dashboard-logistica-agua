import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build  # <--- NUEVO IMPORT NECESARIO
import time
import sqlite3

# ==========================================================
# 1. FUNCIONES DE LIMPIEZA (Tus herramientas)
# ==========================================================

#---------------- FUNCION LIMPIAR MONEDA --------------------#
def limpiar_moneda(valor):
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, str):
        # Quita $, puntos de miles, y cambia coma por punto si es necesario
        valor = valor.replace("$", "").replace(".", "").replace(",", "").strip()
        try:
            return float(valor)
        except ValueError:
            return 0.0
    return float(valor)


#---------------- FUNCION PARA CAMBIO DE FECHA --------------#
def limpiar_fecha_sql(fecha_texto):
    """
    Convierte fechas raras como 'viernes, 1 de septiembre de 2023' o '14/05'
    al formato perfecto para SQL: YYYY-MM-DD.
    """
    texto = str(fecha_texto).lower().strip()
    
    if not texto:
        return ""
        
    # Si la secretaria lo escribió bien con barritas (Ej. 14/05/2023)
    if "/" in texto:
        partes = texto.split("/")
        if len(partes) == 3:
            # Asumimos que viene como Día/Mes/Año
            return f"{partes[2]}-{partes[1].zfill(2)}-{partes[0].zfill(2)}"
        return texto # Si es algo raro, lo devuelve como está
        
    # Diccionario traductor de meses a números
    meses = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
    }
    
    # 1. Borramos la basura (días de la semana, comas y palabras conectoras)
    basura = ["lunes", "martes", "miercoles", "miércoles", "jueves", "viernes", "sabado", "sábado", "domingo", ",", " del ", " de "]
    for palabra in basura:
        texto = texto.replace(palabra, " ")
        
    # 2. Ahora el texto quedó limpio, tipo: "1 septiembre 2023". Lo separamos.
    partes = texto.split()
    
    dia = "01"
    mes = "01"
    anio = "2024" # Año por defecto por si acaso
    
    # 3. El robot revisa cada pedazo para armar el rompecabezas
    for p in partes:
        if p.isdigit():
            if len(p) <= 2:
                dia = p.zfill(2) # zfill(2) le pone un cero a la izquierda si es un 1 -> "01"
            elif len(p) == 4:
                anio = p
        elif p in meses:
            mes = meses[p]
            
    # 4. Armamos la fecha como le gusta a SQL
    return f"{anio}-{mes}-{dia}"


# ==========================================================
# 2. FUNCIONES DE EXTRACCIÓN (Tus operarios)
# ==========================================================

#---------------- FUNCION VENTAS CUADRE DIARIO --------------#
def extraer_ventas(datos, fecha_db):
    ventas_hoy = []
    
    # BUSCAR LAS COLUMNAS DINÁMICAMENTE ---
    f5 = datos[5]
    f6 = datos[6]
    # RECORRER LAS FILAS DE DATOS ---
    titulos_combinados = []

    # buscar en qué número de columna está cada palabra
    for i in range(len(f5)):
        # Sumamos el texto de la fila 5 y la fila 6 en una sola palabra
        # Usamos .strip() para limpiar espacios
        union = (f5[i] + " " + f6[i]).upper().strip()
        # 2. BORRAMOS LOS PUNTOS: reemplaza el "." por nada ""
        union_limpia = union.replace(".", "")
        titulos_combinados.append(union_limpia)

    # Ahora buscamos en nuestra "Súper Fila"
    try:
        # Buscamos la columna que CONTENGA la palabra
        cliente = titulos_combinados.index("CLIENTES")
        cantidad = titulos_combinados.index("CANT")
        precio = titulos_combinados.index("PRECIO UNIDAD")
        total = titulos_combinados.index("TOTAL A PAGAR")
        efectivo = titulos_combinados.index("FORMAS DE PAGO  EFEC")
        transferencia = titulos_combinados.index("TRF")
        tarjeta = titulos_combinados.index("TARJ")
        pendiente = titulos_combinados.index("PAGO PENDIENTE")
    except StopIteration:
        print(f"❌ No encontré alguna columna en el bloque de títulos.")
        print(f"Mira cómo quedó la fusión: {titulos_combinados}")
        exit()

    # Empezamos en la fila 7 de Excel (índice 6 en Python)
    for fila in datos[7:]:
        nombre_cliente = fila[cliente]

        # Si el nombre del cliente está vacío o dice "TOTAL", paramos de leer
        if nombre_cliente == "" or "TOTAL" in nombre_cliente.upper():
            break  # Esto detiene el bucle y ya no lee nada más hacia abajo

        # Si llegamos aquí, es un cliente real. Guardamos sus datos.
        registro = {
            "FECHA": fecha_db,
            "CLIENTE": nombre_cliente,
            "CANTIDAD": limpiar_moneda(fila[cantidad]),
            "PRECIO": limpiar_moneda(fila[precio]),
            "TOTAL-PAGAR": limpiar_moneda(fila[total]),
            "EFECTIVO": limpiar_moneda(fila[efectivo]),
            "TRANSFERENCIA": limpiar_moneda(fila[transferencia]),
            "TARJETA": limpiar_moneda(fila[tarjeta]),
            "PENDIENTE": limpiar_moneda(fila[pendiente]),
        }

        ventas_hoy.append(registro)
    return ventas_hoy


#---------------- FUNCION RECARGAS 10LTS --------------------#
def recargas_10lts(hoja, datos, indice_titulo, lista_destino, fecha_db):
    """
    Función inteligente que busca columnas y extrae datos de Recargas o Adicionales.
    - hoja: El objeto de la hoja actual (para sacar el título/fecha).
    - datos: Todos los datos de la hoja.
    - indice_titulo: El número de fila 'i' donde se encontró el título (ej. "RECARGAS").
    - lista_destino: La lista donde guardaremos los datos (df_recargas o df_adicionales).
    """

    # 1. LEEMOS LA FILA DE ENCABEZADOS (i + 1)
    try:
        fila_titulos = [str(x).upper().strip() for x in datos[indice_titulo + 1]]
    except IndexError:
        return  # Si no hay fila abajo, salimos

    # 2. DEFINIMOS VALORES POR DEFECTO (Ajusta estos si tus tablas varían)
    idx_cliente = 2
    idx_prod = 3
    idx_cantidad = 8
    idx_precio = 9
    idx_total = 10
    idx_efectivo = 11
    idx_transf = 12
    idx_tarjeta = 13
    idx_pendiente = 14

    # 3. DETECTAMOS COLUMNAS AUTOMÁTICAMENTE
    # (Corregí tus variables aquí, fíjate que ahora coinciden con lo que buscan)
    for n, titulo in enumerate(fila_titulos):
        if "CLIENTE" in titulo:
            idx_cliente = n
        elif "PRODUCTO" in titulo:
            idx_prod = n
        elif "CANT" in titulo:
            idx_cantidad = n
        elif "PRECIO" in titulo:
            idx_precio = n
        elif "TOTAL" in titulo:
            idx_total = n
        elif "EFEC" in titulo:
            idx_efectivo = n
        elif "TRF" in titulo:
            idx_transf = n
        elif "TARJ" in titulo or "DEBITO" in titulo:
            idx_tarjeta = n
        elif "PENDIENTE" in titulo or "SALDO" in titulo:
            idx_pendiente = n

    # 4. BUCLE DE EXTRACCIÓN
    paso = 2
    while True:
        # Seguridad por si se acaba la hoja
        if (indice_titulo + paso) >= len(datos):
            break

        fila_datos = datos[indice_titulo + paso]

        # Obtenemos el nombre usando el índice detectado
        try:
            nombre = str(fila_datos[idx_cliente]).strip()
        except IndexError:
            break
        # Criterio de parada
        if nombre == "" or "TOTAL" in nombre.upper() or "VIENE" in nombre.upper():
            break

        # Creamos el registro genérico
        registro = {
            "FECHA": fecha_db,
            "CLIENTE": nombre,
            "PRODUCTOS": fila_datos[idx_prod] if len(fila_datos) > idx_prod else "",
            "CANTIDAD": limpiar_moneda(fila_datos[idx_cantidad] if len(fila_datos) > idx_cantidad else ""),
            "PRECIO": limpiar_moneda(fila_datos[idx_precio])if len(fila_datos) > idx_precio else "",
            "TOTAL-PAGAR": limpiar_moneda(fila_datos[idx_total])if len(fila_datos) > idx_total else "",
            "EFECTIVO": limpiar_moneda(fila_datos[idx_efectivo])if len(fila_datos) > idx_efectivo else "",
            "TRANSFERENCIA": limpiar_moneda(fila_datos[idx_transf])if len(fila_datos) > idx_transf else "",
            "TARJETA": limpiar_moneda(fila_datos[idx_tarjeta])if len(fila_datos) > idx_tarjeta else "",
            "PENDIENTE": limpiar_moneda(fila_datos[idx_pendiente])if len(fila_datos) > idx_pendiente else "",
        }
        # Solo guardamos si hay cantidad o total (para evitar filas vacías)
        if registro["TOTAL-PAGAR"] != 0.0 or registro["CANTIDAD"] != 0.0:
            lista_destino.append(registro)
        paso += 1


#---------------- FUNCION EXTRAER PAGOS PENDIENTES ----------#
def pagos_pendientes(hoja, datos, i, df_pendientes, fecha_db):
    pagos_pendiente = []
    # 1. LEEMOS LA FILA DE TÍTULOS (La que está justo debajo de "PAGOS PENDIENTE")
    # Convertimos todo a mayúsculas para no fallar
    fila_titulos = [str(x).upper().strip() for x in datos[i + 1]]
    
    # 2. DEFINIMOS VALORES POR DEFECTO (Por si acaso no encuentra el título)
    # Estos son tus índices "normales" de casi todos los días
    idx_cliente = 2
    idx_prod = 3
    idx_fecha = 8   # Normal
    idx_monto = 10   # Normal
    idx_efectivo = 11
    idx_transf = 12
    idx_tarjeta = 13
    idx_saldo_final = 14

    # 3. EL ROBOT BUSCA DÓNDE CAYÓ CADA COSA HOY
    for n, titulo in enumerate(fila_titulos):
        if "CLIENTE" in titulo: idx_cliente = n
        elif "PRODUCTO" in titulo or "DETALLE" in titulo: idx_prod = n
        elif "FECHA" in titulo: idx_fecha = n
        elif "DEUDA" in titulo: idx_deuda = n  # La deuda inicial
        elif "EFECTIVO" in titulo: idx_efectivo = n
        elif "TRANSFERENCIA" in titulo: idx_transf = n
        elif "TARJETA" in titulo or "DEBITO" in titulo: idx_tarjeta = n
        elif "PENDIENTE" in titulo or "SALDO" in titulo: idx_saldo_final = n
    
    paso = 2
    while True:
        if (i + paso) >= len(datos): # Seguridad por si se acaba la hoja
            break
        fila_datos_extra2 = datos[i + paso]
        nombre_p = str(fila_datos_extra2[idx_cliente]).strip()
    # SI EL NOMBRE ESTÁ VACÍO O ES UN TÍTULO DE OTRA TABLA, PARAMOS
        if nombre_p == "" or "TOTAL" in str(nombre_p).upper():
            break
        
        pago_pendiente = {
            "FECHA": fecha_db,
            "CLIENTE": fila_datos_extra2[idx_cliente], 
            "PRODUCTOS": fila_datos_extra2[idx_prod],
            "FECHA-DEUDA": fila_datos_extra2[idx_fecha],
            "DEUDA-MONTO": limpiar_moneda(fila_datos_extra2[idx_deuda]),
            "EFECTIVO": limpiar_moneda(fila_datos_extra2[idx_efectivo]),
            "TRANSFERENCIA": limpiar_moneda(fila_datos_extra2[idx_transf]),
            "TARJETA": limpiar_moneda(fila_datos_extra2[idx_tarjeta]),
            "PENDIENTE": limpiar_moneda(fila_datos_extra2[idx_saldo_final])
            # Reutilizamos el índice de pendiente
        }
        # Solo guardamos si realmente hay una deuda anotada
        if pago_pendiente["PENDIENTE"] != "" and pago_pendiente["PENDIENTE"] != "0":
            df_pendientes.append(pago_pendiente)
        paso += 1


#---------------- FUNCION EXTRAER ADICIONALES ---------------#
def extraer_adicionales(datos):
    df_adicionales_local = []
    
    # 1. El robot empieza a bajar fila por fila
    for i, fila in enumerate(datos):
        texto_fila = " ".join(fila).upper()
        # 2. BUSCAR EL ANCLA: Detectamos dónde empieza la tabla
        # Ajusta esta palabra si en tu Excel dice diferente

        if "REGISTRO DE PRODUCTO" in texto_fila or "ADICIONALES" in texto_fila:
            # 3. MAPEAR COLUMNAS: Leemos la fila de títulos (la que está justo debajo, i + 1)
            try:
                fila_titulos = [str(x).upper().strip() for x in datos[i +1]]
            except IndexError:
                break
            
            #VALORES POR DEFECTO
            idx_fecha = -1
            idx_cliente = -1
            idx_prod = -1
            idx_cant = -1
            idx_precio = -1
            idx_monto = -1
            
            # El robot detecta la posición real de cada columna
            for n, titulo in enumerate(fila_titulos):
                if "FECHA" in titulo: idx_fecha = n
                elif "CLIENTE" in titulo: idx_cliente = n
                elif "PRODUCTO" in titulo or "DETALLE" in titulo: idx_prod = n
                elif "CANT" in titulo: idx_cant = n
                elif "PRECIO" in titulo: idx_precio = n
                elif "MONTO" in titulo or "TOTAL" in titulo: idx_monto = n
                
                # 4. EXTRAER LOS DATOS (Bajamos desde la fila de títulos en adelante)
            paso = 2
            while True:
                # Seguridad por si se acaba la hoja de Excel
                if (i + paso) >= len(datos): 
                    break
                
                fila_datos = datos[i + paso]
                
                # ESCUDO: Si la fila es más corta que donde debería estar el cliente, paramos
                if len(fila_datos) <= idx_cliente:
                    break
                
                nombre_cliente = str(fila_datos[idx_cliente]).strip().upper()
                
                # 5. EL FRENO DE MANO: ¿Cuándo dejamos de leer?
                # Si está vacío, dice TOTAL, o si invadimos la tabla de RUTA
                if nombre_cliente == "" or "TOTAL" in nombre_cliente or "RUTA" in nombre_cliente:
                    break
                
                # Armamos el paquete de datos del cliente
                registro = {
                    # "Si el índice no es -1 y la fila es suficientemente larga, saca el dato. Si no, pon vacío o cero."
                    "FECHA": limpiar_fecha_sql(fila_datos[idx_fecha]) if idx_fecha != -1 and len(fila_datos) > idx_fecha else "",
                    "CLIENTE": fila_datos[idx_cliente], # El cliente asumimos que siempre existe
                    "PRODUCTO": fila_datos[idx_prod] if idx_prod != -1 and len(fila_datos) > idx_prod else "",
                    "CANTIDAD": limpiar_moneda(fila_datos[idx_cant] if idx_cant != -1 and len(fila_datos) > idx_cant else ""),
                    # MAGIA AQUÍ: Si idx_precio es -1 (no existe), automáticamente pone 0.0
                    "PRECIO": limpiar_moneda(fila_datos[idx_precio]) if idx_precio != -1 and len(fila_datos) > idx_precio else 0.0,
                    "MONTO": limpiar_moneda(fila_datos[idx_monto]) if idx_monto != -1 and len(fila_datos) > idx_monto else 0.0
                }
                
                # Solo guardamos si realmente hay un monto o un producto
                if registro["MONTO"] != 0.0 or registro["PRODUCTO"] != "":
                    df_adicionales_local.append(registro)
                paso += 1 # Pasamos a la siguiente fila
            # Como ya encontramos y leímos la tabla de adicionales, rompemos el bucle principal
            break 
    return df_adicionales_local


#---------------- FUNCION EXTRAER RUTA ----------------------#
def extraer_ruta(datos):
    df_ruta_local = []
    
    # 1. El robot empieza a bajar fila por fila
    for i, fila in enumerate(datos):
        texto_fila = " ".join(fila).upper()
    
        # 2. BUSCAR EL ANCLA: Detectamos dónde empieza la tabla
        # Ajusta esta palabra si en tu Excel dice diferente

        if "RUTA DE CLIENTE" in texto_fila or "RUTA" in texto_fila:
            
            # 3. MAPEAR COLUMNAS: Leemos la fila de títulos (la que está justo debajo, i + 1)
            try:
                fila_titulos = [str(x).upper().strip() for x in datos[i +1]]
            except IndexError:
                break
            
            #VALORES POR DEFECTO
            idx_fecha = -1
            idx_detalle = -1
            idx_direccion = -1
            idx_comuna = -1
            idx_cant = -1
            idx_valor = -1
            idx_total = -1
            idx_extra = -1
            
            # El robot detecta la posición real de cada columna
            for n, titulo in enumerate(fila_titulos):
                if "FECHA" in titulo: idx_fecha = n
                elif "DETALLE" in titulo: idx_detalle = n
                elif "DIRECCION" in titulo: idx_direccion = n
                elif "COMUNA" in titulo: idx_comuna = n
                elif "CANTIDAD" in titulo or "DETALLE" in titulo: idx_cant = n
                elif "VALOR" in titulo: idx_valor = n
                elif "TOTAL" in titulo: idx_total = n
                elif "EXTRA" in titulo: idx_extra = n
                
                # 4. EXTRAER LOS DATOS (Bajamos desde la fila de títulos en adelante)
            paso = 2
            while True:
                # Seguridad por si se acaba la hoja de Excel
                if (i + paso) >= len(datos): 
                    break
                
                fila_datos = datos[i + paso]
                
                # ESCUDO: Si la fila es más corta que donde debería estar el cliente, paramos
                if len(fila_datos) <= idx_direccion:
                    break
                
                direccion = str(fila_datos[idx_direccion]).strip().upper()
                
                # 5. EL FRENO DE MANO: ¿Cuándo dejamos de leer?
                # Si está vacío, dice TOTAL, o si invadimos la tabla de RUTA
                if direccion == "" or "TOTAL" in direccion or "RUTA" in direccion:
                    break
                
                # Armamos el paquete de datos del cliente
                registro = {
                    # "Si el índice no es -1 y la fila es suficientemente larga, saca el dato. Si no, pon vacío o cero."
                    "FECHA": limpiar_fecha_sql(fila_datos[idx_fecha]) if idx_fecha != -1 and len(fila_datos) > idx_fecha else "",
                    "DETALLE": fila_datos[idx_detalle] if idx_detalle != -1 and len(fila_datos) > idx_detalle else "",
                    "DIRECCION": fila_datos[idx_direccion], 
                    "COMUNA": fila_datos[idx_comuna], 
                    "CANTIDAD": limpiar_moneda(fila_datos[idx_cant] if idx_cant != -1 and len(fila_datos) > idx_cant else ""),
                    "VALOR": limpiar_moneda(fila_datos[idx_valor] if idx_valor != -1 and len(fila_datos) > idx_valor else ""),
                    # MAGIA AQUÍ: Si idx monto o moneda es -1 (no existe), automáticamente pone 0.0
                    "TOTAL": limpiar_moneda(fila_datos[idx_total]) if idx_total != -1 and len(fila_datos) > idx_total else 0.0,
                    "EXTRA": limpiar_moneda(fila_datos[idx_extra]) if idx_extra != -1 and len(fila_datos) > idx_extra else 0.0
                }
                
                # Solo guardamos si realmente hay un monto o un producto
                if registro["TOTAL"] != 0.0 or registro["DIRECCION"] != "":
                    df_ruta_local.append(registro)
                
                paso += 1 # Pasamos a la siguiente fila
            
            # Como ya encontramos y leímos la tabla de adicionales, rompemos el bucle principal
            break 
            
    return df_ruta_local


#---------------- FUNCION EXTRAER GASTOS --------------------#
def extraer_gastos(datos):
    lista_resultados = []
    categorias = [
        "COSTOS FIJOS", "COSTOS VARIABLES", "GASTOS ADMINISTRATIVOS", 
        "TRANSPORTE Y ESTACIONAMIENTO", "INSUMOS PARA LOCAL", 
        "MATERIALES CONSTRUCCION", "PROFESIONALES", "INVERSIONES", "OTROS GASTOS EXTRAS"
    ]
    
    categoria_actual = "SIN CATEGORIA"
    
    for fila in datos:
        # Si la fila está muy vacía, la saltamos
        if len(fila) < 8: continue
        
        texto_columna_b = str(fila[1]).strip().upper()
        
        # AHORA (Busca si alguna de tus categorías vive dentro de la celda del Excel):
        for cat in categorias:
            if cat.upper() in texto_columna_b:
                categoria_actual = cat
                break # Ya encontramos la categoría, no hace falta seguir buscando en la lista
        if texto_columna_b == "" or "TOTAL" in texto_columna_b.upper():
            continue
        
        # 2. ¿Tiene una fecha y un monto? (Si no, no es un gasto válido)
        # Columna C (2) tiene la fecha y Columna H (7) el monto
        monto_crudo = str(fila[7]).strip()
        if monto_crudo == "" or monto_crudo == "0" or "$" not in monto_crudo:
            continue
        
        # 3. Si pasó los filtros, limpiamos y guardamos
        try:
            lista_resultados.append({
                "FECHA": limpiar_fecha_sql(fila[2]),
                "CATEGORIA": categoria_actual,
                "DESCRIPCION": fila[1],
                "OBSERVACION": fila[6],
                "MONTO": limpiar_moneda(fila[7])
            })
        except:
            continue
            
    return lista_resultados

# ==========================================================
# 3. CONEXIÓN Y EXPLORACIÓN
# ==========================================================

# --- 2. CONEXIÓN MODERNA  ---
scope = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive",]
# Esta es la forma nueva de conectarse que no falla con OpenSSL
creds = Credentials.from_service_account_file("credenciales.json", scopes=scope)
client = gspread.authorize(creds)

# ==========================================================
# 4. EJECUCIÓN MAESTRA 
# ==========================================================
#----------- BUSCAR ARCHIVOS ------------#

# --- NUEVA FUNCIÓN: EL EXPLORADOR DE DRIVE ---
def buscar_hojas_en_arbol(carpeta_id_maestra):
    """
    Entra a la carpeta maestra, busca subcarpetas y saca todos los Sheets.
    Devuelve una lista de IDs de archivos para abrir.
    """
    service = build("drive", "v3", credentials=creds)
    archivos_para_procesar = []

    print(f"📂 Explorando carpeta maestra ID: {carpeta_id_maestra}...")

    # 1. Buscamos las SUBCARPETAS (Ej. "CUADRE DIARIO 2024") dentro de la maestra
    # La consulta dice: "Busca carpetas que estén DENTRO de la maestra y que no estén borradas"
    query_subcarpetas = f"'{carpeta_id_maestra}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results_sub = (service.files().list(q=query_subcarpetas, fields="files(id, name)").execute())
    subcarpetas = results_sub.get("files", [])
    # Agregamos también la propia carpeta maestra por si hay archivos sueltos ahí
    subcarpetas.append({"id": carpeta_id_maestra, "name": "Raíz"})

    for carpeta in subcarpetas:
        print(f"   ↳ 🔎 Mirando dentro de: {carpeta['name']}")
        # 2. Buscamos los SHEETS dentro de cada subcarpeta
        # mimeType de Google Sheets es: application/vnd.google-apps.spreadsheet
        query_sheets = f"'{carpeta['id']}' in parents and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
        results_sheets = (service.files().list(q=query_sheets, fields="files(id, name)").execute())
        sheets = results_sheets.get("files", [])
        for sheet in sheets:
            print(f"      ✅ Encontrado: {sheet['name']}")
            archivos_para_procesar.append(sheet)

    return archivos_para_procesar


#---- BUSCAR ARCHIVO NEW BALANCE ----#
def buscar_hoja(client, file_id, nombre_pestana):
    """
    Entra a un archivo por su ID, revisa TODAS las pestañas y extrae 
    los datos solo de las que contienen la palabra clave (ej. "GASTO").
    """
    historial_datos = []
    
    try:
        # 1. Abre el "Libro" completo directamente por su ID
        archivo = client.open_by_key(file_id)
        
        # 2. Descarga la lista de TODAS las pestañas que existen en ese archivo
        todas_pestanas = archivo.worksheets()
        
        # 3. El Filtro Inteligente (El bucle)
        for hoja in todas_pestanas:
            titulo = hoja.title.upper().strip() # Sacamos el título y lo ponemos en mayúsculas
            
            # 4. La gran pregunta: ¿La palabra clave está en el título?
            if file_id in titulo:
                print(f"✅ ¡Bingo! Encontré la pestaña: {titulo}")
                
                # Descargamos los datos de esta hoja específica
                datos = hoja.get_all_values()
                
                # Guardamos los datos y también el título (para saber de qué mes son)
                historial_datos.append({
                    "titulo_mes": titulo,
                    "datos": datos
                })
        # Cuando termina de revisar todas las pestañas, nos devuelve la lista llena
        return historial_datos
                
    except Exception as e:
        print(f"❌ Error al abrir el archivo maestro: {e}")
        return []


# ------------------- EJECUCIÓN PRINCIPAL ------------------#

# --- 3. LISTAS VACÍAS ---
df_ventas = []
df_recargas = []
df_pendientes = []
df_gastos = []
df_adicionales = []
df_ruta = []

# 1. PEGA AQUÍ EL ID QUE COPIASTE DEL NAVEGADOR
ID_CARPETA_HISTORICOS = "1WzzntS2Ncss6vDrEaJ4EiwONfA5RYqaI"
ID_HOJA = "1DWxlJAwKRStoskjK1UgSwmDqU9ObN55NGmSQLUgPKl4"

# 2. El robot sale a buscar
lista_de_archivos = buscar_hojas_en_arbol(ID_CARPETA_HISTORICOS)
# 2. AGREGAMOS LOS ARCHIVOS AISLADOS (Los que tienes por ID)


print(f"\n🤖 Total de archivos encontrados: {len(lista_de_archivos)}")

# 3. AHORA SÍ, TU BUCLE DE SIEMPRE 
for archivo_info in lista_de_archivos:
    try:
        print(f"📖 Abriendo: {archivo_info['name']}...")

        # OJO: Aquí usamos open_by_key porque tenemos el ID, no el nombre
        sheet = client.open_by_key(archivo_info["id"])

        # --- LOGICA DE SIEMPRE ---
        for hoja in sheet.worksheets():
            time.sleep(1.2)
            titulo = hoja.title.strip()
            partes = titulo.split()
            fecha_texto = partes[-1]
            d, m, a = fecha_texto.split("/")
            fecha_db = f"20{a}-{m}-{d}"
            print(f"⏳ Procesando: {hoja.title}")
            
            # 3. Descargamos los datos de ESA hoja en específico
            datos = hoja.get_all_values()
            if not datos: continue
            
            nombre_actual = archivo_info['name'].upper()+ " " + titulo
            # 🚦 RUTA 1: Si es un archivo de Cuadre Diario
            if "CUADRE" in nombre_actual:
# ---------------------------------------------------------------------------------------------#
            #-----A LOGICA DE VENTAS CUADRE DIARIO-----------#
                df_ventas.extend(extraer_ventas(datos, fecha_db))
            
# ----------------------------------------------------------------------------------------------#
            # --- B. LÓGICA DE RECARGAS 10LTS(Empezamos a buscar más abajo) ---
                for i, fila in enumerate(datos):
                    texto_fila = " ".join(fila).upper().strip()

                    if "RECARGAS DE 10 LTS" in texto_fila:
                    # ¡Magia! Solo una línea llama a toda la lógica
                        recargas_10lts(hoja, datos, i, df_recargas, fecha_db)
# -----------------------------------------------------------------------------------------------#
                # C. LOGICA TABLA DE PENDIENTES
                    if "PAGOS PENDIENTE" in texto_fila:
                        pagos_pendientes(hoja, datos, i, df_pendientes, fecha_db)
#----------------------------------------------------------------------------------------------------#
    except Exception as e:
        print(f"❌ Error abriendo {archivo_info['name']}: {e}")
        
        
        
# ----------------------------------------------------------
# MUNDO 2: EL ARCHIVO AISLADO (BÚSQUEDA ESPECÍFICA)
# ----------------------------------------------------------
print("\n🚀 MUNDO 2: Modo Francotirador (Buscando pestaña específica)...")

# 👉 PON AQUÍ EL NOMBRE DE LA PESTAÑA QUE QUIERES PROBAR (Ej: "ENERO", "SEMANA 1", etc.)
PESTANA_BUSCADA = ["ADICIONAL","GASTO"] # <--- ¡CÁMBIALO POR EL NOMBRE QUE ESTÁS BUSCANDO!

try:
    sheet_especial = client.open_by_key(ID_HOJA) 
    todas_las_hojas = sheet_especial.worksheets()
    
    pestañas_procesadas = 0
    
    for hoja in todas_las_hojas:
        titulo_mayus = hoja.title.upper()
        time.sleep(0.3)
        
        # 🌟 LA MAGIA: ¿Alguna de nuestras palabras clave está en el título?
        if any(palabra in titulo_mayus for palabra in PESTANA_BUSCADA):
            print(f"  ✅ ¡Atrapada! Procesando pestaña: {hoja.title}")
            
            datos_especiales = hoja.get_all_values()
            
            if datos_especiales:
                if "GASTO" in titulo_mayus:
                    # 🚦 EL SEMÁFORO DE MUNDO 2 🚦
                    # 1. Si el título tiene la palabra GASTO, aplicamos solo la función de gastos
                    df_gastos.extend(extraer_gastos(datos_especiales))
                
                # 2. Si el título dice ADICIONAL o RUTA, aplicamos las otras dos
                # (Como tu pestaña se llama "ADICIONAL+ RUTA", aplicará ambas y cada una buscará su ancla)
                if "ADICIONAL" in titulo_mayus or "RUTA" in titulo_mayus:
                    df_adicionales.extend(extraer_adicionales(datos_especiales))
                    df_ruta.extend(extraer_ruta(datos_especiales))
                pestañas_procesadas += 1
            else:
                print(f"  ⚠️ La pestaña {hoja.title} está vacía.")
            
            # 🛑 ¡QUITAMOS EL BREAK! 
            # Así el robot termina con esta hoja y pasa a revisar la siguiente.
            
            
except Exception as e:
    print(f"❌ Error al abrir el archivo especial: {e}")
# ==========================================================
# 5. GUARDADO FINAL Y REVISIÓN
# ==========================================================


# --- 6. MOSTRAR EL RESULTADO ---
final_ventas = pd.DataFrame(df_ventas).fillna(0)
final_10lts = pd.DataFrame(df_recargas).fillna(0)
final_pendientes = pd.DataFrame(df_pendientes).fillna(0)
final_adicionales = pd.DataFrame(df_adicionales).fillna(0)
final_ruta = pd.DataFrame(df_ruta).fillna(0)
final_gastos = pd.DataFrame(df_gastos).fillna(0)

# Configuramos para ver todas las filas sin recortes

print("\n✅ DATOS EXTRAÍDOS CON ÉXITO:")
#pd.set_option('display.max_rows', None)
print(final_ventas)
print(final_10lts)
print(final_pendientes)
print(final_adicionales)
print(final_ruta)
print(final_gastos)

# Esto te dirá cuántas ventas hubo por cada día
print("\n📅 VENTAS POR DÍA:")
print(final_ventas["FECHA"].value_counts())


# ==========================================================
# 6. CREACIÓN Y EXPORTACIÓN A SQLITE (planta_agua.db)
# ==========================================================
print("\n💾 CONECTANDO CON SQLITE (planta_agua.db)...")

try:
    # 1. Creamos la conexión (Si el archivo no existe, Python lo crea por ti)
    conexion = sqlite3.connect("planta_agua3.db")
    
    # 2. Guardamos cada DataFrame en su respectiva tabla
    # Nota: Usamos 'replace' para pruebas. 
    # En el futuro, lo cambiaremos a 'append'.
    
    if not final_ventas.empty:
        final_ventas.to_sql("ventas_diarias", conexion, if_exists="replace", index=False)
        
    if not final_10lts.empty:
        final_10lts.to_sql("recargas", conexion, if_exists="replace", index=False)
        
    if not final_pendientes.empty:
        final_pendientes.to_sql("pendientes", conexion, if_exists="replace", index=False)
        
    if not final_adicionales.empty:
        final_adicionales.to_sql("adicionales", conexion, if_exists="replace", index=False)
        
    if not final_ruta.empty:
        final_ruta.to_sql("ruta", conexion, if_exists="replace", index=False)
        
    if not final_gastos.empty:
        final_gastos.to_sql("gastos", conexion, if_exists="replace", index=False)

    # 3. Cerramos la puerta
    conexion.close()
    print("✅ ¡ÉXITO! Todos los datos fueron guardados en la base de datos planta_agua.db")

except Exception as e:
    print(f"❌ Error crítico al guardar en SQLite: {e}")