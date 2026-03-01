import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
import datetime
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dashboard Agua Purificada",page_icon="💧", layout="wide")

st.markdown("""
    <style>
        .block-container {
                padding-top: 1rem; /* Cambia este número si lo quieres más pegado (ej: 0.5rem) */
                padding-bottom: 1rem;
            }
    </style>
    """, unsafe_allow_html=True)

# Función rápida para darle formato de dinero chileno ($ 1.500.000)
def formato_peso(numero):
    return f"${numero:,.0f}".replace(",", ".")


# --- 1. FUNCIÓN DE CARGA DE DATOS OPTIMIZADA (CACHÉ) ---
@st.cache_data(ttl=3600) # Se actualiza cada 1 hora automáticamente
def cargar_datos():
    # 1. Abrimos la conexión
    conn = sqlite3.connect("db_portafolio.db")
    
    # 2. Hacemos consultas separadas para no mezclar los datos
    df_ventas = pd.read_sql("SELECT * FROM ventas_diarias", conn)
    df_gastos = pd.read_sql("SELECT * FROM gastos", conn)
    df_rutas = pd.read_sql("SELECT * FROM ruta", conn)
    df_adicionales = pd.read_sql("SELECT * FROM adicionales", conn)
    df_pendientes = pd.read_sql("SELECT * FROM pendientes", conn)
    df_recargas = pd.read_sql("SELECT * FROM recargas", conn)
    # 3. Cerramos la conexión
    conn.close()

    
    # 1. Eliminamos las filas donde la celda de CANTIDAD está vacía (Nulos / NaN)
    df_ventas = df_ventas.dropna(subset=['CANTIDAD'])

    # 2. (Filtro extra recomendado) Por si la secretaria no la dejó vacía, sino que escribió un "0"
    df_ventas = df_ventas[df_ventas['CANTIDAD'] > 0]
    # Eliminamos filas basura o subtítulos donde el gasto sea 0 o esté vacío
    df_gastos = df_gastos[df_gastos["MONTO"] > 0]
    
    # 1. LIMPIEZA DE TEXTO (El jabón mágico)
    df_rutas["COMUNA"] = df_rutas["COMUNA"].astype(str).str.strip().str.upper()
    df_rutas['DIRECCION'] = df_rutas['DIRECCION'].str.strip()
    # 4. TRUCO DE ANALISTA: Convertir la columna FECHA a formato 'datetime' de Pandas
    for df in [df_ventas, df_gastos, df_rutas, df_adicionales, df_pendientes, df_recargas]:
        if "FECHA" in df.columns:
            # 1. Convertimos a fecha real de Pandas
            fecha_temp = pd.to_datetime(df["FECHA"], errors='coerce')
            
            # 2. NUEVO: Creamos una columna mágica llamada 'MES' (Formato Año-Mes: "2026-02")
            df["MES"] = fecha_temp.dt.strftime('%Y-%m')
            
            # 3. Le quitamos la hora a la fecha original (como ya lo tenías)
            df["FECHA"] = fecha_temp.dt.date
    # Unificamos a todos los 'Crisangel' en la tabla de Ventas
    #df_ventas.loc[df_ventas['CLIENTE'].str.contains('crisange', case=False, na=False), 'CLIENTE'] = 'CRISANGEL'
    
    # 4. TRUCO DE ANALISTA: Convertir la columna FECHA a formato 'datetime' de Pandas
    # Esto nos permitirá agrupar por mes o año súper fácil en los gráficos
    for df in [df_ventas, df_gastos, df_rutas, df_adicionales, df_pendientes, df_recargas]:
        if "FECHA" in df.columns:
            df["FECHA"] = pd.to_datetime(df["FECHA"], errors='coerce').dt.date
            
    # --- LA CURA PARA LOS NÚMEROS NEGATIVOS DE LA SECRETARIA ---
    # Usamos .abs() para volver todo positivo en las columnas de dinero
    columnas_dinero = ["CANTIDAD","PRECIO", "TOTAL-PAGAR", "EFECTIVO", "TRANSFERENCIA", "TARJETA", "PENDIENTE"]
    
    for col in columnas_dinero:
        if col in df_ventas.columns:
            df_ventas[col] = df_ventas[col].abs()
            df_recargas[col] = df_recargas[col].abs()
            
    # 5. Empaquetamos todo en un diccionario y lo enviamos
    return {
        "ventas": df_ventas,
        "gastos": df_gastos,
        "rutas": df_rutas,
        "adicionales": df_adicionales,
        "pendientes": df_pendientes,
        "recargas": df_recargas
    }

# --- 2. INICIALIZACIÓN ---
# Ejecutamos la función y guardamos nuestro paquete de datos
datos = cargar_datos()

# Para sacar un dataframe específico, solo lo llamamos por su nombre:
df_ventas = datos["ventas"]
df_gastos = datos["gastos"]
df_rutas = datos['rutas']
df_adicionales = datos["adicionales"]
df_pendientes = datos["pendientes"]
df_recargas = datos["recargas"]

st.title("💧 AGUAS INTERNACIONALES")

# (Importante: Ahora en tu gráfico de abajo debes usar 'df_ventas_filtrado' en lugar de 'df_ventas')

df_ventas["TIPO_PRODUCTO"] = "RECARGA 20LTS"
df_recargas["TIPO_PRODUCTO"] = "RECARGA 10LTS"
df_ventas_maestra = pd.concat([df_ventas, df_recargas], ignore_index=True)
# Crear las pestañas al principio
tab1, tab2, tab3, tab4 = st.tabs(["📊 Resumen de Ventas", "🎯 Análisis de Ruta", "Adicionales","Gastos de Empresa"])

with tab1:
    st.header("💧 Panel de Control - Planta de Agua")
    
    col1,col2,col3= st.columns(3)

    with col1:
        # Un selector de clientes automático (agregamos "Todos" como primera opción)
        lista_clientes = ["Todos"] + list(df_ventas_maestra["CLIENTE"].dropna().unique())
        cliente_seleccionado = st.selectbox("👤 Buscar Cliente:", lista_clientes)
        
    with col2:
        #Mostrar desde un inicio los ultimos 7 dias
        #hoy = pd.to_datetime("today").date()
        #hace_siete_dias = hoy - datetime.timedelta(days=7)
        # Selector de fecha de inicio
        # 1. Forzamos a que todo en esa columna sea tratado como Fecha. 
        # errors='coerce' hace que cualquier celda vacía o texto mal escrito se convierta en 'NaT' (Not a Time)
        df_ventas_maestra["FECHA"] = pd.to_datetime(df_ventas_maestra["FECHA"], errors='coerce')

        # 2. Pasamos la escoba: Eliminamos cualquier fila donde la fecha sea nula (NaT)
        # Si no hay fecha, esa fila no nos sirve para el dashboard de todas formas
        df_ventas_maestra = df_ventas_maestra.dropna(subset=["FECHA"])

        # 3. Nos aseguramos de quedarnos solo con el día/mes/año (ignorando horas si las hubiera)
        df_ventas_maestra["FECHA"] = df_ventas_maestra["FECHA"].dt.date
        fecha_minima = df_ventas_maestra["FECHA"].min() if not df_ventas_maestra.empty else pd.to_datetime("today").date()
        fecha_inicio = st.date_input("📅 Desde:", value=fecha_minima)

    with col3:
        # Selector de fecha de fin
        fecha_maxima = df_ventas_maestra["FECHA"].max() if not df_ventas_maestra.empty else pd.to_datetime("today").date()
        fecha_fin = st.date_input("📅 Hasta:", value=fecha_maxima)
    # --- 🚀 APLICAR LOS FILTROS A LA TABLA ---
    # Le decimos a Pandas: "Filtra la tabla de ventas según las fechas que eligió el usuario"
    df_ventas_filtrado = df_ventas_maestra[
        (df_ventas_maestra["FECHA"] >= fecha_inicio) & 
        (df_ventas_maestra["FECHA"] <= fecha_fin)
    ]
    # Si el usuario no eligió "Todos", filtramos también por el cliente exacto
    if cliente_seleccionado != "Todos":
        df_ventas_filtrado = df_ventas_filtrado[df_ventas_filtrado["CLIENTE"] == cliente_seleccionado]
        

    # --- 3. CÁLCULOS RÁPIDOS PARA LOS KPIs ---
    # 1. Creamos las columnas
    kpi1, kpi2, kpi3 = st.columns([1, 1, 1])

    # 2. Lógica de cálculo segura (Solo se ejecuta si hay datos)
    if not df_ventas_filtrado.empty:
        # Cálculos de Ventas Totales
        total_ventas = df_ventas_filtrado["TOTAL-PAGAR"].sum()
        
        # Cálculos del Mejor Cliente
        ventas_cliente = df_ventas_filtrado.groupby("CLIENTE")["TOTAL-PAGAR"].sum()
        nombre_mejor_cliente = ventas_cliente.idxmax()
        
        # Cálculos del Mejor Mes
        ventas_mes = df_ventas_filtrado.groupby("MES")["TOTAL-PAGAR"].sum()
        nombre_mejor_mes = ventas_mes.idxmax()  # Esto saca "2026-02"
        monto_mejor_mes = ventas_mes.max()      # Esto saca el número de ganancias de ese mes
    else:
        # Valores por defecto para que la app no explote si la base de datos está vacía
        total_ventas = 0
        nombre_mejor_cliente = "Sin datos"
        nombre_mejor_mes = "Sin datos"
        monto_mejor_mes = 0

    # 3. Mostrar las métricas (Tarjetas)
    kpi1.metric("VENTAS TOTALES HISTORICOS", value=formato_peso(total_ventas))
    kpi2.metric("💧 MEJOR CLIENTE", value=nombre_mejor_cliente)
    
    # Aquí la magia: Mostramos el NOMBRE del mes como valor principal, 
    # y la GANANCIA de ese mes como 'delta' (en números más pequeños y con color verde)
    kpi3.metric("📅 MEJOR  MES", value=nombre_mejor_mes, delta=formato_peso(monto_mejor_mes))
    

        
    # --- 3. DISEÑO DE LA PANTALLA ---
    
    col_graf1, col_graf2 = st.columns(2)
    
    #GRAFICO DE VENTAS DIARIAS
    with col_graf1:
        st.subheader("📈 Monto de Ventas Diarias")
        
        # 1. PREPARACIÓN DE DATOS (El motor lógico)
        # Agrupamos por FECHA y sumamos el TOTAL-PAGAR. El reset_index() lo vuelve a convertir en una tabla plana.
        ventas_por_dia = df_ventas_filtrado.groupby("FECHA")["TOTAL-PAGAR"].sum().reset_index()
        
        # Ordenamos cronológicamente por si acaso los datos vienen desordenados
        ventas_por_dia = ventas_por_dia.sort_values("FECHA")
        # 🛠️ LA MAGIA VISUAL: Convertimos la fecha a texto solo para el gráfico
        # Así Streamlit hace barras anchas y repartidas en toda la pantalla
        ventas_por_dia["FECHA"] = ventas_por_dia["FECHA"].astype(str)
        
        # 2. EL GRÁFICO (La capa visual)
        # Usamos un gráfico de barras nativo de Streamlit, súper rápido y elegante
        st.bar_chart(data=ventas_por_dia, x="FECHA", y="TOTAL-PAGAR", color="#1f77b4")
        
        # 3. LA TABLA DE DETALLES (Opcional, pero útil)
        st.markdown("**Detalle de cada transacción:**")
        # Mostramos la tabla cruda pero ocultamos el índice para que se vea más limpia
        
    #GRAFICO DE MESES
    with col_graf2:
        st.subheader("📦 Venta Mensual de Recargas 20LTS")
                
        ventas_recargas = df_ventas_filtrado.groupby('MES')["CANTIDAD"].sum()
        
        
        st.bar_chart(ventas_recargas, color="#114553")
    with st.expander("🔎 Ver Datos Detallados (Click para desplegar)"):
        st.dataframe(df_ventas_filtrado[['FECHA','CLIENTE',"TIPO_PRODUCTO",'CANTIDAD','PRECIO','TOTAL-PAGAR','EFECTIVO','TRANSFERENCIA','TARJETA','PENDIENTE']], use_container_width=True, hide_index=True)
    
            
with tab2:
    st.title("🚚 Panel de Ruta")
    col1,col2,col3,col4 = st.columns(4)
    
    
    with col1:
        lista_comuna = ["Todos"] + list(df_rutas["COMUNA"].dropna().unique())
        comuna_select = st.selectbox("📍 Filtrar por Comunas:", lista_comuna)
    # 🛠️ LA MAGIA DE LA CASCADA 🛠️
    # Antes de pasar a la columna 2, creamos una tabla "temporal" solo con la comuna elegida
    if comuna_select == "Todos":
        df_ruta_temp = df_rutas  # Si eligió "Todos", la tabla queda intacta
    else:
        # Si eligió una comuna, filtramos la tabla
        df_ruta_temp = df_rutas[df_rutas['COMUNA'] == comuna_select]
        
    with col2:
        # 2. SEGUNDO FILTRO: La Dirección (¡Pero leyendo de la tabla temporal!)
        # Como df_rutas_temporal ya está filtrada, solo sacará las direcciones de esa comuna
        lista_cliente = ["Todos"] + list(df_ruta_temp["DIRECCION"].dropna().unique())
        direccion_select = st.selectbox("👤 Direccion Clientes:", lista_cliente)
        # Aplicamos filtro de Dirección inmediatamente
    if direccion_select != "Todos":
        df_ruta_temp = df_ruta_temp[df_ruta_temp["DIRECCION"] == direccion_select].copy()
    with col3:
        # Aprovechamos la columna 3 para poner un filtro de fecha para el repartidor
        # (Así puede ver solo la ruta de "hoy")
        mes = ["Todos"] + list(df_ruta_temp["MES"].dropna().unique())
        mes_select = st.selectbox("📅 Seleccione Mes:", mes)
    # Aplicamos filtro de Mes inmediatamente
    if mes_select != "Todos":
        df_ruta_temp = df_ruta_temp[df_ruta_temp["MES"] == mes_select].copy()
        
    with col4:
        fecha_ruta = ["Todos"] + list(df_ruta_temp["FECHA"].astype(str).unique())
        fecha_select = st.selectbox("📅 Seleccione Dia:", fecha_ruta)
    # --- 🚀 APLICAMOS TODOS LOS FILTROS AL DATAFRAME FINAL ---
    if fecha_select != "Todos":
        df_ruta_temp = df_ruta_temp[df_ruta_temp["FECHA"].astype(str) == fecha_select.copy()]

    df_rutas_filtrado = df_ruta_temp # Ya viene con el filtro de comuna aplicado
        
    kpi1, kpi2, kpi3 = st.columns([1, 2, 1])

    # 2. Lógica de cálculo segura (Solo se ejecuta si hay datos)
    if not df_rutas_filtrado.empty:
        # Cálculos de Ventas Totales
        total_ventas = df_rutas_filtrado["TOTAL"].sum()
        
        # Cálculos del Mejor Cliente
        ventas_cliente = df_rutas_filtrado.groupby("DIRECCION")["TOTAL"].sum()
        nombre_mejor_cliente = ventas_cliente.idxmax()
        
        # Cálculos del Mejor Mes
        ventas_mes = df_rutas_filtrado.groupby("MES")["TOTAL"].sum()
        extra = df_rutas_filtrado.groupby("MES")["EXTRA"].sum()
        suma_ruta = extra + ventas_mes
        nombre_mejor_mes = suma_ruta.idxmax()  # Esto saca "2026-02"
        monto_mejor_mes = suma_ruta.max()      # Esto saca el número de ganancias de ese mes
    else:
        # Valores por defecto para que la app no explote si la base de datos está vacía
        total_ventas = 0
        nombre_mejor_cliente = "Sin datos"
        nombre_mejor_mes = "Sin datos"
        monto_mejor_mes = 0

    # 3. Mostrar las métricas (Tarjetas)
    kpi1.metric("VENTAS TOTALES HISTORICOS", value=formato_peso(total_ventas))
    kpi2.metric("💧 MEJOR CLIENTE DE RUTA", value=nombre_mejor_cliente)
    
    # Aquí la magia: Mostramos el NOMBRE del mes como valor principal, 
    # y la GANANCIA de ese mes como 'delta' (en números más pequeños y con color verde)
    kpi3.metric("📅 MEJOR  MES", value=nombre_mejor_mes, delta=formato_peso(monto_mejor_mes))

    col_graf1, col_graf2 = st.columns(2)
    
    with col_graf1:
        st.subheader("📈 MEJORES COMUNAS")
        # 1. LIMPIEZA DE TEXTO (El jabón mágico)
        df_rutas_filtrado["COMUNA"] = df_rutas_filtrado["COMUNA"].astype(str).str.strip().str.upper()
        # 2. AHORA SÍ, AGRUPAMOS Y ORDENAMOS
        ventas_comunas = df_rutas_filtrado.groupby('COMUNA')["TOTAL"].sum().sort_values()
        ventas_comunas = ventas_comunas.tail(10)
        # 3. DIBUJAMOS EL GRÁFICO
        st.bar_chart(ventas_comunas)
    
    # --- MOSTRAR RESULTADOS ---
    st.subheader(f"📋 Clientes Visitados")
    st.dataframe(df_rutas_filtrado[['FECHA','DETALLE','DIRECCION','COMUNA','CANTIDAD','VALOR','TOTAL','EXTRA']], use_container_width=True, hide_index=True)
    with col_graf2:
        st.subheader("💧 VENTA DIARIA RUTA")
    
    # 1. Agrupamos por FECHA y sumamos la CANTIDAD (no el dinero, sino los botellones físicos)
        botellones_por_dia = df_rutas_filtrado.groupby("FECHA")["TOTAL"].sum()
    
    # 2. Dibujamos un gráfico de área o línea
        st.line_chart(botellones_por_dia)
        
        
with tab3:
    st.header("💧 Venta de ADICIONALES")
    
    col1,col2,col3= st.columns(3)

    with col1:
        # Un selector de clientes automático (agregamos "Todos" como primera opción)
        lista_cliente = ["Todos"] + list(df_adicionales["CLIENTE"].dropna().unique())
        cliente_seleccionado = st.selectbox("👤 Buscar Cliente:", lista_cliente)
    
    if cliente_seleccionado == "Todos":
        df_adicional_temp = df_adicionales  # Si eligió "Todos", la tabla queda intacta
    else:
        # Si eligió una comuna, filtramos la tabla
        df_adicional_temp = df_adicionales[df_adicionales['CLIENTE'] == cliente_seleccionado]
        
    with col2:
        #hoy = pd.to_datetime("today").date()
        #hace_siete_dias = hoy - datetime.timedelta(days=7)
        # Selector de Producto
        producto = ["Todos"] + list(df_adicional_temp["PRODUCTO"].dropna().unique())
        producto_select = st.selectbox("Filtrar Producto", producto)

    with col3:
        # Selector de fecha de fin
        fecha_adicionales = ["Todos"] + list(df_adicional_temp["FECHA"].astype(str).unique())
        fecha_select = st.selectbox("Selecciona Fecha", fecha_adicionales)

        
    # 1. Ya filtramos el Cliente arriba, ahora tomamos esa tabla y filtramos el Producto
    if producto_select != "Todos":
        df_adicional_temp = df_adicional_temp[df_adicional_temp["PRODUCTO"] == producto_select]
        
    # 2. Tomamos la tabla (ya filtrada por cliente y producto) y filtramos la Fecha
    if fecha_select != "Todos":
        # Convertimos la fecha de la tabla a texto para que coincida con el selectbox
        df_adicional_temp = df_adicional_temp[df_adicional_temp["FECHA"].astype(str) == fecha_select]

    # --- 3. CÁLCULOS RÁPIDOS PARA LOS KPIs ---
    # 1. Creamos las columnas
    kpi1, kpi2, kpi3 = st.columns([1, 2, 1])

    # 2. Lógica de cálculo segura (Solo se ejecuta si hay datos)
    if not df_adicional_temp.empty:
        # Cálculos de Ventas Totales
        total_ventas = df_adicional_temp["MONTO"].sum()
        
        # Cálculos del Mejor Cliente
        producto_mas_vendido = df_adicional_temp.groupby("PRODUCTO")["MONTO"].sum()
        mejor_producto = producto_mas_vendido.idxmax()
        
        # Cálculos del Mejor Mes
        ventas_mes = df_adicional_temp.groupby("MES")["MONTO"].sum()
        nombre_mejor_mes = ventas_mes.idxmax()  # Esto saca "2026-02"
        monto_mejor_mes = ventas_mes.max()      # Esto saca el número de ganancias de ese mes
    else:
        # Valores por defecto para que la app no explote si la base de datos está vacía
        total_ventas = 0
        mejor_producto = "Sin datos"
        nombre_mejor_mes = "Sin datos"
        monto_mejor_mes = 0

    # 3. Mostrar las métricas (Tarjetas)
    kpi1.metric("VENTAS TOTALES HISTORICOS", value=formato_peso(total_ventas))
    kpi2.metric("💧 MEJOR PRODUCTO", value=mejor_producto)
    
    # Aquí la magia: Mostramos el NOMBRE del mes como valor principal, 
    # y la GANANCIA de ese mes como 'delta' (en números más pequeños y con color verde)
    kpi3.metric("📅 MEJOR  MES", value=nombre_mejor_mes, delta=formato_peso(monto_mejor_mes))
    

        
    # --- 3. DISEÑO DE LA PANTALLA ---
    
    col_graf1, col_graf2 = st.columns(2)
    
    #GRAFICO DE VENTAS DIARIAS
    with col_graf1:
        st.subheader("📈 Ventas Diarias Adicionales")
        
        # 1. PREPARACIÓN DE DATOS (El motor lógico)
        # Agrupamos por FECHA y sumamos el TOTAL-PAGAR. El reset_index() lo vuelve a convertir en una tabla plana.
        ventas_por_dia = df_adicional_temp.groupby("FECHA")["MONTO"].sum().reset_index()
        
        # Ordenamos cronológicamente por si acaso los datos vienen desordenados
        ventas_por_dia = ventas_por_dia.sort_values("FECHA")
        
        # ✂️ LA MAGIA: Nos quedamos solo con los últimos 10 días
        ventas_por_dia = ventas_por_dia.tail(7)
        
        # 🛠️ LA MAGIA VISUAL: Convertimos la fecha a texto solo para el gráfico
        # Así Streamlit hace barras anchas y repartidas en toda la pantalla
        ventas_por_dia["FECHA"] = ventas_por_dia["FECHA"].astype(str)
        
        # 2. EL GRÁFICO (La capa visual)
        # Usamos un gráfico de barras nativo de Streamlit, súper rápido y elegante
        st.bar_chart(data=ventas_por_dia, x="FECHA", y="MONTO", color="#1f77b4")
        # 3. LA TABLA DE DETALLES (Opcional, pero útil)
        st.markdown("**Detalle de cada transacción:**")
        # Mostramos la tabla cruda pero ocultamos el índice para que se vea más limpia
        
    #GRAFICO DE MESES
    with col_graf2:
        st.subheader("📦 Venta Mensual Adicionales")
                
        ventas_recargas = df_adicional_temp.groupby('MES')["MONTO"].sum()
        
        
        st.bar_chart(ventas_recargas, color="#114553")
    with st.expander("🔎 Ver Datos Detallados (Click para desplegar)"):
        st.dataframe(df_adicional_temp[['FECHA','CLIENTE',"PRODUCTO",'CANTIDAD','PRECIO','MONTO']], use_container_width=True, hide_index=True)
    
    
with tab4:
    st.header("💸 Gastos de Empresa")
    
    col1,col2,col3= st.columns(3)

    with col1:
        # Un selector de clientes automático (agregamos "Todos" como primera opción)
        fecha = ["Todos"] + list(df_gastos["MES"].dropna().unique())
        fecha_mensual = st.selectbox("📅 Seleccione Mes:", fecha)
    
    if fecha_mensual == "Todos":
        df_gastos_temp = df_gastos  # Si eligió "Todos", la tabla queda intacta
    else:
        # Si eligió una comuna, filtramos la tabla
        df_gastos_temp =  df_gastos[df_gastos["MES"] == fecha_mensual].copy()
        
    with col2:
        #hoy = pd.to_datetime("today").date()
        #hace_siete_dias = hoy - datetime.timedelta(days=7)
        # Selector de Producto
        categoria = ["Todos"] + list(df_gastos_temp["CATEGORIA"].dropna().unique())
        categoria_select = st.selectbox("Filtrar Categoria", categoria)
    #filtramos categoria
    if categoria_select != "Todos":
        df_gastos_temp = df_gastos_temp[df_gastos_temp["CATEGORIA"] == categoria_select].copy()

    with col3:
        # Selector de fecha de fin
        descripcion = ["Todos"] + list(df_gastos_temp["DESCRIPCION"].astype(str).unique())
        descripcion_select = st.selectbox("Selecciona Descripcion", descripcion)
        
    # 2. Tomamos la tabla (ya filtrada por cliente y producto) y filtramos la Fecha
    if descripcion_select != "Todos":
        # Convertimos la fecha de la tabla a texto para que coincida con el selectbox
        df_gastos_temp = df_gastos_temp[df_gastos_temp["DESCRIPCION"] == descripcion_select].copy()
        
    df_gastos_filtrado = df_gastos_temp
        
    # --- 3. CÁLCULOS RÁPIDOS PARA LOS KPIs ---
    # 1. Creamos las columnas
    kpi1, kpi2, kpi3 = st.columns([1, 2, 1])

    # 2. Lógica de cálculo segura (Solo se ejecuta si hay datos)
    if not df_gastos_filtrado.empty:
        total_gastos = df_gastos_filtrado["MONTO"].sum()
        gasto_por_categoria = df_gastos_filtrado.groupby("CATEGORIA")["MONTO"].sum()
        peor_categoria = gasto_por_categoria.idxmax()
        gastos_mes = df_gastos_filtrado.groupby("MES")["MONTO"].sum()
        nombre_peor_mes = gastos_mes.idxmax()  
        monto_peor_mes = gastos_mes.max()      
    else:
        total_gastos = 0
        peor_categoria = "Sin datos"
        nombre_peor_mes = "Sin datos"
        monto_peor_mes = 0

    kpi1.metric("GASTOS TOTALES", value=formato_peso(total_gastos))
    kpi2.metric("🚨 MAYOR FUGA DE DINERO", value=peor_categoria)
    kpi3.metric("📅 MES DE MAYOR GASTO", value=nombre_peor_mes, delta=formato_peso(-monto_peor_mes)) 
    
        
    # --- 4. DISEÑO DE LA PANTALLA (MAGIA DE PLOTLY) ---
    col_graf1, col_graf2 = st.columns(2)
    
    # GRAFICO 1: EVOLUCIÓN DIARIA (Barras de Plotly)
    with col_graf1:
        st.subheader("📈 Evolución de Gastos Diarios")
        
        if not df_gastos_filtrado.empty:
            gastos_por_dia = df_gastos_filtrado.groupby("FECHA")["MONTO"].sum().reset_index()
            gastos_por_dia = gastos_por_dia.sort_values("FECHA").tail(15) # Últimos 15 días
            gastos_por_dia["FECHA"] = gastos_por_dia["FECHA"].astype(str)
            
            # ✨ Gráfico de barras interactivo de Plotly
            fig_gastos_dia = px.bar(
                gastos_por_dia, 
                x="FECHA", 
                y="MONTO", 
                color_discrete_sequence=["#f57878"], # Rojo alerta
                text_auto='.2s' # Muestra el monto resumido encima de la barra (ej: 15k)
            )
            # Limpiamos el fondo y los títulos para que se vea elegante
            fig_gastos_dia.update_layout(
                xaxis_title="", 
                yaxis_title="Dinero Gastado ($)", 
                margin=dict(t=10, b=10),
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_gastos_dia, use_container_width=True)
        else:
            st.info("No hay datos para graficar.")
            
    # GRAFICO 2: DISTRIBUCIÓN POR CATEGORÍA (Dona de Plotly)
    with col_graf2:
        st.subheader("📊 Distribución por Categoría")
                
        if not df_gastos_filtrado.empty:
            gastos_cat = df_gastos_filtrado.groupby('CATEGORIA')["MONTO"].sum().reset_index()
            
            # ✨ Gráfico de Dona interactivo
            fig_dona = px.pie(
                gastos_cat, 
                values='MONTO', 
                names='CATEGORIA', 
                hole=0.4, # Esto hace que sea una dona y no un pastel cerrado
                color_discrete_sequence=px.colors.sequential.Reds_r # Paleta de rojos elegantes
            )
            # Ponemos los porcentajes dentro del gráfico para que se lea rápido
            fig_dona.update_traces(textposition='inside', textinfo='percent+label')
            fig_dona.update_layout(margin=dict(t=10, b=10), showlegend=False)
            
            st.plotly_chart(fig_dona, use_container_width=True)
        else:
            st.info("No hay datos para graficar.")
            
    with st.expander("🔎 Ver Datos Detallados (Click para desplegar)"):
        st.dataframe(df_gastos_filtrado[['FECHA','CATEGORIA','DESCRIPCION','MONTO']], use_container_width=True, hide_index=True)