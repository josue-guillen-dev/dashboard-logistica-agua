### 💧 End-to-End Data Pipeline & BI Dashboard | Planta Purificadora de Agua

🔗 **Demo del Proyecto:** [Inserta el enlace a tu Streamlit aquí]

## 📌 Descripción General
Proyecto integral de Ingeniería de Datos y Business Intelligence desarrollado para automatizar la consolidación operativa y financiera de una planta purificadora de agua. 

La solución reemplaza un proceso manual y propenso a errores (basado en múltiples planillas desestructuradas enviadas por choferes) por un flujo automatizado (ETL) que extrae, limpia, estandariza y consolida los datos en una base relacional, alimentando un dashboard interactivo para el control gerencial.

## 🎯 Objetivo del Proyecto y Problema de Negocio
**Problemas detectados:**
* Falta de visibilidad diaria de ventas por ruta.
* Datos desordenados y no estandarizados (errores de tipeo, formatos inconsistentes).
* Dificultad para consolidar ingresos y gastos rápidamente.
* Ausencia de métricas claras para la toma de decisiones.

**Solución aportada:** Un sistema End-to-End que centraliza la información y proporciona KPIs financieros y operativos en tiempo real.

## 🏗️ Arquitectura del Sistema

```text
[Google Drive / Google Sheets] (Fuentes de Datos Desestructuradas)
            │
            ▼
[pipeline_etl.py] (Extracción, Limpieza y Transformación - Pandas/Google API)
            │
            ▼
[SQLite / db_portafolio.db] (Almacenamiento Relacional Estructurado)
            │
            ▼
[app.py] (Streamlit Dashboard - Visualización Interactiva)
⚙️ Componentes del Proyecto
1️⃣ Pipeline ETL (pipeline_etl.py)
Motor automatizado de extracción y limpieza que:
Se conecta a la API de Google Workspace.
Navega subcarpetas dinámicamente para buscar archivos históricos y diarios.
Extrae información desestructurada e identifica columnas mediante "anclas" lógicas.
Aplica limpieza avanzada: estandarización de fechas irregulares a formato SQL (YYYY-MM-DD), conversión de strings a formatos de moneda reales y normalización de categorías.

Consolida y carga los datos estructurados en una base de datos SQLite.

2️⃣ Dashboard Interactivo (app.py)
Aplicación web desarrollada con Streamlit que actúa como Panel de Control Gerencial:
Filtros Dinámicos: Búsqueda por fechas, clientes, productos y comunas.
Métricas Clave (KPIs): Ventas totales, mejor cliente, mes de mayor facturación y control de fugas de capital.
Visualizaciones: Gráficos interactivos de Plotly Express y herramientas nativas de Streamlit para analizar el rendimiento por chofer, ventas adicionales y gastos operativos.

Optimización: Uso de @st.cache_data para renderizado ultrarrápido sin saturar la base de datos.

🗂️ Estructura del Repositorio
Plaintext
├── pipeline_etl.py        # Script central de Extracción, Transformación y Carga (ETL)
├── app.py                 # Código fuente del Dashboard interactivo
├── db_portafolio.db       # Base de datos anonimizada (Data Masking)
├── requirements.txt       # Dependencias del entorno
└── README.md              # Documentación del proyecto

🛠️ Stack Tecnológico
Lenguaje: Python 3.x
Extracción y APIs: gspread, google-api-python-client, oauth2
Transformación y Modelado: pandas, sqlite3
Visualización de Datos: streamlit, plotly.express, altair

📊 Impacto en el Negocio
Ahorro de Tiempo: Reducción drástica de horas invertidas en la consolidación manual de planillas.
Integridad de Datos: Eliminación de errores humanos por digitación gracias a la limpieza automatizada.
Control Financiero: Mayor visibilidad del flujo de caja diario y monitoreo estricto de los gastos operativos de la planta y las rutas.

🔐 Gobernanza y Seguridad (Data Masking)
Por políticas de confidencialidad y ética profesional:
No se incluyen credenciales API (credenciales.json) en este repositorio.
La base de datos original fue sometida a un riguroso proceso de Data Masking (Anonimización) mediante un script personalizado en Pandas.
Los nombres de clientes, direcciones específicas y descripciones de gastos fueron ofuscados (Cliente 1, Sector A, etc.), manteniendo intactas las relaciones y la coherencia matemática del modelo para demostrar su funcionamiento sin exponer información sensible de la empresa.
```
### 🚀 Instalación y Uso Local
Clonar el repositorio:
```Bash
git clone https://github.com/josue-guillen-dev/dashboard-logistica-agua.git
cd dashboard-logistica-agua
Instalar dependencias:
pip install -r requirements.txt
Ejecutar el dashboard:
streamlit run app.py
```
### 📈 Roadmap y Mejoras Futuras
* Cargas Incrementales (Upsert): Transición de cargas completas (replace) a cargas incrementales (append) para optimizar recursos a medida que el volumen de datos escale.
* Migración de Base de Datos: Escalar de SQLite a PostgreSQL en un entorno Cloud.
* Automatización Serverless: Ejecutar el pipeline ETL mediante tareas programadas (Cron jobs o Apache Airflow).

``` text
👤 Autor: Josue Guillen
📊 Perfil: Data Analyst | Especialista en Python, SQL y Visualización de Datos.
📍 Ubicación: Santiago, Chile
```
🔗 Contacto: [LINKEDIN](https://www.linkedin.com/in/josue-guillen-data/)
