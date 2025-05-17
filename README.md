# Proyecto de Procesamiento y Reporte Automático de Facturas

## Descripción del Proyecto

Este proyecto implementa 2 scripts de Python para gestionar el procesamiento automático de la facturación de una empresa. Permite automatizar la extracción de datos clave de facturas en formato PDF, manejando la variabilidad de sus formatos, y presentar la información recopilada de forma organizada y accesible a través de un reporte web local, interactivo y dinámico.

## Componentes del Proyecto

El proyecto se divide en dos scripts principales:

### 1. Procesamiento de Facturas (`procesar_facturas.py`)

Este script es el encargado de la ingesta y el análisis de los archivos PDF de facturas:

* Lee archivos PDF de facturas desde una carpeta específica.
* Utiliza técnicas avanzadas de extracción de texto, capaces de procesar tanto PDFs con texto nativo como PDFs escaneados (imágenes). Esto se logra mediante la combinación de bibliotecas de procesamiento de PDF y OCR.
* **Implementación de Inteligencia Artificial:** Envía el texto extraído a la API de un modelo de lenguaje grande (LLM) de OpenAI (específicamente `gpt-4o-mini`). El LLM analiza el contenido textual para identificar y extraer de forma inteligente datos clave como el número de factura, la fecha de emisión, el nombre del proveedor, el nombre del cliente y el monto total, adaptándose a diferentes layouts y formatos.
* Guarda la información estructurada y extraída en una base de datos local **SQLite**.

### 2. Generación de Reporte Visual (`generar_reporte_html.py`)

Este script se encarga de visualizar los datos almacenados:

* Se conecta a la base de datos SQLite generada por el script de procesamiento.
* Recupera todos los datos de las facturas almacenadas.
* Utiliza el motor de plantillas **Jinja2** para tomar un archivo de template HTML y generar un nuevo archivo HTML estático.
* El template HTML utiliza **JavaScript** y bibliotecas de frontend (DataTables.js, Bootstrap) para renderizar los datos recuperados en una tabla dinámica e interactiva en el navegador, con funcionalidades de ordenamiento, búsqueda, paginación y efectos visuales (como hover).

## Tecnologías Implementadas

El proyecto hace uso de diversas tecnologías y bibliotecas:

### Backend (Python)

* **Python:** Lenguaje de programación principal.
* **PyMuPDF (fitz) y pdfplumber:** Para la extracción de texto de PDFs (nativos y como soporte para OCR).
* **pytesseract y Pillow:** Para realizar OCR en PDFs escaneados (requiere el motor Tesseract instalado).
* **OpenAI Python library:** Para interactuar con la API de OpenAI.
* **sqlite3:** Para la gestión de la base de datos SQLite (integrada en Python).
* **python-dotenv:** Para la carga segura de variables de entorno (clave API).
* **Jinja2:** Motor de plantillas para la generación de HTML.
* **re:** Módulo de expresiones regulares para limpieza de texto.
* **io:** Módulo para manejar flujos de bytes en memoria.
* **sys:** Módulo para interactuar con el sistema (usado para salidas).

### Base de Datos

* **SQLite:** Base de datos ligera, integrada y basada en archivos.

### Frontend (HTML, CSS, JavaScript)

* **HTML5:** Estructura del reporte web.
* **CSS3:** Estilos visuales personalizados.
* **Bootstrap:** Framework CSS para estilos base y componentes modernos.
* **JavaScript:** Para la interactividad en el reporte web.
* **jQuery:** Biblioteca JavaScript (dependencia principal de DataTables.js).
* **DataTables.js:** Biblioteca JavaScript para crear tablas de datos dinámicas.

## Configuración e Instalación

Para poner en marcha este proyecto, sigue los siguientes pasos:

1.  **Clonar el Repositorio:**
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd <nombre_del_repositorio>
    ```
    *(Reemplaza `<URL_DEL_REPOSITORIO>` y `<nombre_del_repositorio>` con los datos reales de tu repositorio)*

2.  **Crear un Entorno Virtual (Recomendado):**
    ```bash
    python -m venv .venv
    # Activar en Windows:
    # .venv\Scripts\activate
    # Activar en macOS/Linux:
    # source .venv/bin/activate
    ```

3.  **Instalar Dependencias de Python:**
    ```bash
    pip install PyMuPDF Pillow pytesseract openai python-dotenv pdfplumber Jinja2
    ```

4.  **Instalar Tesseract OCR:**
    Si vas a procesar PDFs escaneados (imágenes), necesitarás instalar el motor Tesseract OCR en tu sistema operativo. Puedes encontrar instrucciones de instalación en la [documentación oficial de Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html). Si Tesseract no se instala en tu PATH, deberás configurar la variable `pytesseract.pytesseract.tesseract_cmd` en el script `procesar_facturas.py`.

5.  **Obtener API Key de OpenAI:**
    Necesitarás una API Key de OpenAI para utilizar el modelo `gpt-4o-mini`. Puedes obtenerla desde tu [cuenta de OpenAI](https://platform.openai.com/api-keys).

6.  **Configurar Variables de Entorno:**
    Crea un archivo llamado `.env` en la carpeta raíz del proyecto (donde están los scripts `.py`) con el siguiente contenido:
    ```dotenv
    OPENAI_API_KEY='tu_clave_api_de_openai_aqui'
    ```
    *(Reemplaza `'tu_clave_api_de_openai_aqui'` con tu clave real)*

7.  **Crear Carpeta de Entrada:**
    Dentro de la carpeta raíz del proyecto, crea una carpeta llamada `Facturas-comprobantes`. Aquí colocarás los archivos PDF de las facturas que deseas procesar.

8.  **Archivos de Template HTML:**
    Asegúrate de tener el archivo `reporte_facturas_template.html` en la carpeta raíz del proyecto.

## Uso

1.  **Coloca tus archivos PDF** de facturas en la carpeta `Facturas-comprobantes`.
2.  **Activa tu entorno virtual** (si no lo has hecho ya).
3.  **Ejecuta el script de procesamiento** para extraer datos y llenar la base de datos:
    ```bash
    python procesar_facturas.py
    ```
4.  **Ejecuta el script de reporte** para generar el archivo HTML:
    ```bash
    python generar_reporte_html.py
    ```
5.  Abre el archivo `reporte_facturas.html` generado en la carpeta raíz de tu proyecto con tu navegador web preferido para ver el reporte interactivo.

## Contribuciones

(Aquí puedes añadir información sobre cómo otras personas pueden contribuir al proyecto, si es relevante).

## Licencia

(Aquí puedes especificar la licencia bajo la cual se distribuye tu proyecto, por ejemplo, MIT).
