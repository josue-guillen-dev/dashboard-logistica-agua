import sqlite3
import pandas as pd

print("⏳ Iniciando clonación segura de la base de datos...")

# 1. Nos conectamos a tu base de datos REAL
conn_real = sqlite3.connect("planta_agua3.db")

# Leemos todas las tablas
df_ventas = pd.read_sql("SELECT * FROM ventas_diarias", conn_real)
df_gastos = pd.read_sql("SELECT * FROM gastos", conn_real)
df_rutas = pd.read_sql("SELECT * FROM ruta", conn_real)
df_adicionales = pd.read_sql("SELECT * FROM adicionales", conn_real)
df_pendientes = pd.read_sql("SELECT * FROM pendientes", conn_real)
df_recargas = pd.read_sql("SELECT * FROM recargas", conn_real)

# 2. APLICAMOS EL BORRADO DE MEMORIA PERMANENTE (Data Masking)
print("🎭 Enmascarando identidades...")

if 'CLIENTE' in df_ventas.columns: df_ventas['CLIENTE'] = 'Cliente ' + (df_ventas.groupby('CLIENTE').ngroup() + 1).astype(str)
if 'CLIENTE' in df_recargas.columns: df_recargas['CLIENTE'] = 'Cliente ' + (df_recargas.groupby('CLIENTE').ngroup() + 1).astype(str)
if 'PRODUCTOS' in df_recargas.columns: df_recargas['PRODUCTOS'] = 'Producto ' + (df_recargas.groupby('PRODUCTOS').ngroup() + 1).astype(str)
if 'TIPO_PRODUCTO' in df_ventas.columns: df_ventas['TIPO_PRODUCTO'] = 'Producto ' + (df_ventas.groupby('TIPO_PRODUCTO').ngroup() + 1).astype(str)
if 'CLIENTE' in df_adicionales.columns: df_adicionales['CLIENTE'] = 'Cliente ' + (df_adicionales.groupby('CLIENTE').ngroup() + 1).astype(str)
if 'CLIENTE' in df_pendientes.columns: df_pendientes['CLIENTE'] = 'Cliente ' + (df_pendientes.groupby('CLIENTE').ngroup() + 1).astype(str)

if 'PRODUCTO' in df_adicionales.columns: df_adicionales['PRODUCTO'] = 'Producto ' + (df_adicionales.groupby('PRODUCTO').ngroup() + 1).astype(str)
if 'DIRECCION' in df_rutas.columns: df_rutas['DIRECCION'] = 'Sector ' + (df_rutas.groupby('DIRECCION').ngroup() + 1).astype(str)
if 'COMUNA' in df_rutas.columns: df_rutas['COMUNA'] = 'Zona ' + (df_rutas.groupby('COMUNA').ngroup() + 1).astype(str)
if 'CATEGORIA' in df_gastos.columns: df_gastos['CATEGORIA'] = 'Categoría ' + (df_gastos.groupby('CATEGORIA').ngroup() + 1).astype(str)
if 'DESCRIPCION' in df_gastos.columns: df_gastos['DESCRIPCION'] = 'Detalle ' + (df_gastos.groupby('DESCRIPCION').ngroup() + 1).astype(str)

# 3. CREAMOS LA BASE DE DATOS FALSA (Para GitHub)
print("💾 Guardando la nueva base de datos de portafolio...")
conn_falsa = sqlite3.connect("db_portafolio.db")

df_ventas.to_sql("ventas_diarias", conn_falsa, if_exists="replace", index=False)
df_gastos.to_sql("gastos", conn_falsa, if_exists="replace", index=False)
df_rutas.to_sql("ruta", conn_falsa, if_exists="replace", index=False)
df_adicionales.to_sql("adicionales", conn_falsa, if_exists="replace", index=False)
df_pendientes.to_sql("pendientes", conn_falsa, if_exists="replace", index=False)
df_recargas.to_sql("recargas", conn_falsa, if_exists="replace", index=False)

# Cerramos las puertas
conn_real.close()
conn_falsa.close()

print("✅ ¡LISTO! Se ha creado 'db_portafolio.db'. Esta es la que debes subir a GitHub.")                                                                