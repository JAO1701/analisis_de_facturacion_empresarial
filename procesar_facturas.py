import os
import sqlite3
import fitz  # PyMuPDF (se importa como fitz)
import pytesseract
from PIL import Image
import openai
import json
from dotenv import load_dotenv
import io
import pdfplumber
import re
import sys # Para salir limpiamente en caso de errores críticos


# --- Configuración de Variables ---

# Ruta a la carpeta que contiene las facturas
CARPETA_FACTURAS = r'./Facturas-comprobantes' 

# Nombre del archivo de la base de datos SQLite
NOMBRE_BD = 'facturas_analizadas.db'

# Configuración de OpenAI
MODELO_OPENAI = "gpt-4o-mini"
# OPENAI_API_KEY='tu_clave_api_de_openai'
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Validación de que la API Key se cargó correctamente
if not openai.api_key:
    print("Error Crítico: La variable de entorno OPENAI_API_KEY no está configurada.")
    print("Por favor, asegúrate de tener un archivo .env con tu clave o configurarla en tu sistema.")
    sys.exit(1) # Salir con código de error

# Configurar la ruta al ejecutable de Tesseract OCR si no está en el PATH
# Esto es necesario si usas pytesseract para OCR. Descomenta y ajusta la línea si es necesario.

# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' # Ejemplo para Windows
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' # Ejemplo para Linux (puede variar)

# Umbral para detección de texto escaso (para decidir si usar OCR)
UMBRAL_CARACTERES_POR_PAGINA = 100 # Ajusta este valor si es necesario


# Paso 2: Configuración de la Base de Datos

def configurar_base_datos(nombre_bd):
    """
    Configura la conexión a la base de datos SQLite y crea la tabla 'facturas' si no existe.
    Retorna el objeto de conexión y el cursor, o None si falla.
    """
    conn = None
    try:
        conn = sqlite3.connect(nombre_bd)
        cursor = conn.cursor()
        print(f"Conectado a la base de datos: {nombre_bd}")

        # Crea la tabla 'facturas' si no existe.
        # Define las columnas para almacenar la información extraída.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT, -- ID único para cada registro
                nombre_archivo TEXT UNIQUE, -- Nombre del archivo original, UNIQUE para evitar duplicados
                numero_factura TEXT,        -- Número de factura (texto, ya que puede contener letras/caracteres)
                fecha_emision TEXT,         -- Fecha de emisión (texto, idealmente YYYY-MM-DD)
                proveedor TEXT,             -- Nombre del proveedor
                cliente TEXT,               -- Nombre del cliente
                total REAL,                 -- Monto total (REAL para números decimales)
                fecha_procesamiento DATETIME DEFAULT CURRENT_TIMESTAMP -- Marca de tiempo de cuándo se procesó
                -- Puedes añadir más columnas aquí según los datos que extraigas (ej: direccion_proveedor, impuestos, etc.)
            )
        ''')

        # Guardar los cambios en la estructura de la base de datos
        conn.commit()
        print("Tabla 'facturas' verificada/creada.")
        return conn, cursor
    except Exception as e:
        print(f"Error al conectar o crear la base de datos: {e}")
        if conn:
            conn.close()
        return None, None



# Paso 3: Funciones de Procesamiento

def extraer_texto_de_pdf(ruta_archivo, umbral_caracteres, tesseract_cmd=None):
    """
    Intenta extraer texto de un PDF. Primero con pdfplumber (nativo),
    luego con OCR (PyMuPDF + pytesseract) si falla o el texto es escaso.
    Retorna el texto extraído o None si hay un error grave.
    """
    nombre_base_archivo = os.path.basename(ruta_archivo)
    texto_completo = ""

    # 1: Extraer texto nativo usando pdfplumber 
    try:
        print(f"  -> Intentando extracción de texto nativo con pdfplumber de {nombre_base_archivo}...")
        with pdfplumber.open(ruta_archivo) as pdf:
            if not pdf.pages:
                 print(f"  -> El documento {nombre_base_archivo} no contiene páginas según pdfplumber. Intentando OCR...")
                 texto_completo_pdfplumber = "" # No hay páginas, texto nativo es vacío
            else:
                 # Concatena texto de todas las páginas
                 texto_completo_pdfplumber = "".join(pagina.extract_text() or "" for pagina in pdf.pages)

            # Verifica si la extracción nativa produjo poco o ningún texto
            if (not texto_completo_pdfplumber.strip()) or \
               (pdf.pages and len(texto_completo_pdfplumber.strip()) < umbral_caracteres * len(pdf.pages)):

                 print(f"  -> Texto nativo limitado o nulo con pdfplumber para {nombre_base_archivo}. Intentando OCR como fallback...")
                 texto_completo = "" # Reinicia el texto para el OCR

                 # 2 (Fallback): Extrae texto usando OCR con PyMuPDF 
                 if tesseract_cmd and not os.path.exists(tesseract_cmd):
                     print(f"  -> Error: La ruta al ejecutable de Tesseract OCR no es válida: {tesseract_cmd}")
                     print("  -> No se puede realizar el OCR.")
                     return None
                 elif not tesseract_cmd and pytesseract.pytesseract.tesseract_cmd == 'tesseract': # Comprobación básica si no se ha configurado explícitamente
                      try:
                          pytesseract.get_tesseract_version()
                      except pytesseract.TesseractNotFoundError:
                           print("  -> Error: Motor Tesseract OCR no encontrado en el PATH del sistema.")
                           print("  -> Instálalo o configura la ruta con pytesseract.pytesseract.tesseract_cmd.")
                           return None


                 try:
                     # Abre el documento de nuevo con fitz para OCR.
                     with fitz.open(ruta_archivo) as doc_ocr:
                          if doc_ocr.is_closed:
                               print(f"  -> Error (OCR Fallback): El documento {nombre_base_archivo} está cerrado inmediatamente después de abrir con fitz.")
                               return None # Error crítico

                          if doc_ocr.page_count == 0:
                               print(f"  -> El documento {nombre_base_archivo} no contiene páginas para OCR con fitz.")
                               return None


                          for pagina_num in range(doc_ocr.page_count):
                              try:
                                  pagina = doc_ocr.load_page(pagina_num)
                                  pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2)) # Aumenta la resolución
                                  mode = "RGB" if pix.alpha == 0 else "RGBA"
                                  img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

                                  # Aplica OCR a la imagen
                                  texto_pagina = pytesseract.image_to_string(img, lang='spa') # Especifica el idioma
                                  texto_completo += texto_pagina + "\n--- Fin de página ---\n" # Añade separador


                              except Exception as e_ocr_pagina:
                                   print(f"  -> Error (OCR Fallback) durante OCR en página {pagina_num} de {nombre_base_archivo} (fitz+tesseract): {e_ocr_pagina}")
                                   # Si una página falla, intenta las demás.


                 except fitz.FileDataError:
                     print(f"  -> Error (OCR Fallback): El archivo {nombre_base_archivo} no es válido para fitz.")
                     return None
                 except Exception as e_ocr_general:
                     print(f"  -> Error general (OCR Fallback) durante el proceso de OCR en {nombre_base_archivo}: {e_ocr_general}")
                     return None # Error durante el proceso de OCR

            else:
                 # Si la extracción nativa con pdfplumber fue exitosa y con suficiente texto
                 print(f"  -> Extracción de texto nativo con pdfplumber exitosa para {nombre_base_archivo}.")
                 texto_completo = texto_completo_pdfplumber # Usa el texto de pdfplumber

    # --- Manejo de errores específicos de pdfplumber y luego intenta con OCR ---
    except pdfplumber.PDFSyntaxError as e_syntax:
        print(f"  -> Error de sintaxis del PDF con pdfplumber en {nombre_base_archivo}: {e_syntax}. Intentando OCR como fallback...")
        texto_completo = "" # Reinicia el texto

        # --- Intento 2 (Fallback por SyntaxError): Extrae texto usando OCR con PyMuPDF ---
        if tesseract_cmd and not os.path.exists(tesseract_cmd):
             print(f"  -> Error: La ruta al ejecutable de Tesseract OCR no es válida: {tesseract_cmd}")
             print("  -> No se puede realizar el OCR.")
             return None
        elif not tesseract_cmd and pytesseract.pytesseract.tesseract_cmd == 'tesseract':
             try:
                 pytesseract.get_tesseract_version()
             except pytesseract.TesseractNotFoundError:
                  print("  -> Error: Motor Tesseract OCR no encontrado en el PATH del sistema.")
                  print("  -> Instálalo o configura la ruta con pytesseract.pytesseract.tesseract_cmd.")
                  return None


        try:
             with fitz.open(ruta_archivo) as doc_ocr:
                  if doc_ocr.is_closed:
                       print(f"  -> Error (OCR Fallback Syntax): El documento {nombre_base_archivo} está cerrado inmediatamente después de abrir con fitz.")
                       return None

                  if doc_ocr.page_count == 0:
                       print(f"  -> El documento {nombre_base_archivo} no contiene páginas para OCR con fitz (Syntax Fallback).")
                       return None

                  for pagina_num in range(doc_ocr.page_count):
                      try:
                          pagina = doc_ocr.load_page(pagina_num)
                          pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2))
                          mode = "RGB" if pix.alpha == 0 else "RGBA"
                          img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                          texto_pagina = pytesseract.image_to_string(img, lang='spa')
                          texto_completo += texto_pagina + "\n--- Fin de página ---\n"
                      except Exception as e_ocr_pagina:
                           print(f"  -> Error (OCR Fallback Syntax) durante OCR en página {pagina_num} de {nombre_base_archivo} (fitz+tesseract): {e_ocr_pagina}")

        except fitz.FileDataError:
            print(f"  -> Error (OCR Fallback Syntax): El archivo {nombre_base_archivo} no es válido para fitz.")
            return None
        except Exception as e_fitz_ocr_fallback:
            print(f"  -> Error general (OCR Fallback Syntax) durante el proceso de OCR en {nombre_base_archivo}: {e_fitz_ocr_fallback}")
            return None

    except Exception as e_general_pdfplumber:
         # --- Manejo de otros errores generales de pdfplumber y luego intenta con OCR ---
         print(f"  -> Error general con pdfplumber en {nombre_base_archivo}: {e_general_pdfplumber}. Intentando OCR como fallback...")
         texto_completo = "" # Reinicia texto

         # --- Intento 2 (Fallback por Error General): Extrae texto usando OCR con PyMuPDF ---
         if tesseract_cmd and not os.path.exists(tesseract_cmd):
             print(f"  -> Error: La ruta al ejecutable de Tesseract OCR no es válida: {tesseract_cmd}")
             print("  -> No se puede realizar el OCR.")
             return None
         elif not tesseract_cmd and pytesseract.pytesseract.tesseract_cmd == 'tesseract':
              try:
                  pytesseract.get_tesseract_version()
              except pytesseract.TesseractNotFoundError:
                   print("  -> Error: Motor Tesseract OCR no encontrado en el PATH del sistema.")
                   print("  -> Instálalo o configura la ruta con pytesseract.pytesseract.tesseract_cmd.")
                   return None


         try:
             with fitz.open(ruta_archivo) as doc_ocr:
                  if doc_ocr.is_closed:
                       print(f"  -> Error (OCR Fallback General): El documento {nombre_base_archivo} está cerrado inmediatamente después de abrir con fitz.")
                       return None

                  if doc_ocr.page_count == 0:
                       print(f"  -> El documento {nombre_base_archivo} no contiene páginas para OCR con fitz (General Fallback).")
                       return None


                  for pagina_num in range(doc_ocr.page_count):
                      try:
                          pagina = doc_ocr.load_page(pagina_num)
                          pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2))
                          mode = "RGB" if pix.alpha == 0 else "RGBA"
                          img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                          texto_pagina = pytesseract.image_to_string(img, lang='spa')
                          texto_completo += texto_pagina + "\n--- Fin de página ---\n"
                      except Exception as e_ocr_pagina:
                           print(f"  -> Error (OCR Fallback General) durante OCR en página {pagina_num} de {nombre_base_archivo} (fitz+tesseract): {e_ocr_pagina}")

         except fitz.FileDataError:
            print(f"  -> Error (OCR Fallback General): El archivo {nombre_base_archivo} no es válido para fitz.")
            return None
         except Exception as e_fitz_ocr_fallback:
             print(f"  -> Error general (OCR Fallback General) durante el proceso de OCR en {nombre_base_archivo}: {e_fitz_ocr_fallback}")
             return None


    # --- Verificación final del texto extraído ---
    if not texto_completo.strip():
         print(f"  -> No se pudo extraer ningún texto útil de {nombre_base_archivo} después de intentar todos los métodos.")
         return None

    return texto_completo.strip()


def extraer_datos_con_openai(texto_factura, modelo_openai):
    """
    Envía el texto de la factura a la API de OpenAI para extraer datos clave.
    Retorna un diccionario con los datos extraídos o None si falla.
    """
    
    # Prompt para el modelo de OpenAI.
    prompt = f"""Eres un experto en extraer información clave de facturas.
    Analiza el siguiente texto de una factura y extrae la siguiente información en formato JSON:
    - numero_factura: El número único de la factura.
    - fecha_emision: La fecha en que se emitió la factura (intenta un formato ISO 8601 comoYYYY-MM-DD si es posible).
    - proveedor: El nombre de la empresa que emitió la factura.
    - cliente: El nombre del cliente a quien se emitió la factura.
    - total: El monto total de la factura. Extrae solo el valor numérico como un número (float), manejando correctamente los separadores de miles (coma o punto) y el separador decimal (punto o coma). Por ejemplo:
      - '1.234,56' debe ser 1234.56
      - '1,234.56' debe ser 1234.56
      - '1234.56' debe ser 1234.56
      - '1234,56' debe ser 1234.56
      - '73,900.00' debe ser 73900.00
      Si el total no se encuentra, usa null.

    Si no encuentras algún otro campo específico, usa null como valor.

    Texto de la factura:
    ---
    {texto_factura}
    ---

    JSON con la información extraída:
    """

    try:
        response = openai.chat.completions.create(
            model=modelo_openai, 
            messages=[
                {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0 # Usa temperatura baja para resultados más precisos (reduce las alucionaciones del modelo al mínimo y devuelve una salida determinista)
        )

        json_respuesta = response.choices[0].message.content
        datos_extraidos = json.loads(json_respuesta)

        # Lógica de limpieza de total mejorada para convertir a float 
        if datos_extraidos.get('total') is not None:
            try:
                total_str = str(datos_extraidos['total']).strip()

                # Elimina símbolos de moneda y otros caracteres no numéricos excepto puntos y comas
                total_limpio = re.sub(r'[^\d.,]', '', total_str)

                # Maneja la ambigüedad del punto y coma como separadores de miles/decimales
                if ',' in total_limpio and '.' in total_limpio:
                    
                    if total_limpio.rfind(',') > total_limpio.rfind('.'):
                        # Elimina puntos de miles, reemplazar coma decimal por punto.
                        total_limpio = total_limpio.replace('.', '').replace(',', '.')
                    else:
                        # Eliminar comas de miles, el punto decimal está bien.
                        total_limpio = total_limpio.replace(',', '')
                elif ',' in total_limpio:
                    # Solo coma presente. Asumir decimal si está al final y hay 1 o 2 dígitos después.
                    # Si no son centavos al final, asume que es una coma de miles y la elimina.
                    if re.search(r',\d{1,2}$', total_limpio):
                         total_limpio = total_limpio.replace(',', '.')
                    else:
                         total_limpio = total_limpio.replace(',', '') # Eliminar coma de miles

                # Si solo hay punto, asumimos que es decimal y no se necesita reemplazar nada.
                # Si no hay ni punto ni coma, se trata como un entero.

                # Convertir a float
                datos_extraidos['total'] = float(total_limpio)

            except (ValueError, TypeError, re.error) as e:
                 print(f"  -> Error al convertir total a float para {nombre_base_archivo}: {e}. String original: '{total_str}', String limpio tras limpieza inicial: '{total_limpio}'")
                 datos_extraidos['total'] = None

        return datos_extraidos

    except openai.APIError as e:
        print(f"  -> Error de la API de OpenAI: {e}")
        return None
    except json.JSONDecodeError:
        print(f"  -> Error al parsear la respuesta JSON de OpenAI. Respuesta recibida: {json_respuesta[:500]}...") # Imprime parte de la respuesta para depurar
        return None
    except Exception as e:
        print(f"  -> Error desconocido al llamar a OpenAI: {e}")
        return None

def insertar_en_sqlite(conn, cursor, nombre_archivo, datos_extraidos):
    """
    Inserta los datos extraídos de una factura en la base de datos SQLite.
    Aplica redondeo a 2 decimales al campo total.
    """
    try:
        total_a_insertar = datos_extraidos.get('total')

        # --- Redondea el total a 2 decimales si es un número ---
        if isinstance(total_a_insertar, (int, float)):
            total_a_insertar = round(total_a_insertar, 2) # Redondea a 2 decimales
        else:
            total_a_insertar = None # Nos aseguramos de que sea None si no es un número válido

        cursor.execute('''
            INSERT INTO facturas (nombre_archivo, numero_factura, fecha_emision, proveedor, cliente, total)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nombre_archivo,
              datos_extraidos.get('numero_factura'),
              datos_extraidos.get('fecha_emision'),
              datos_extraidos.get('proveedor'),
              datos_extraidos.get('cliente'),
              total_a_insertar)) # Usa la variable total_a_insertar (ahora redondeada o None)

        conn.commit()
        print(f"  -> Datos de {nombre_archivo} insertados correctamente en la base de datos.")

    except sqlite3.IntegrityError:
        print(f"  -> Advertencia: El archivo {nombre_archivo} ya parece estar en la base de datos (nombre de archivo duplicado).")
        conn.rollback()
    except Exception as e:
        print(f"  -> Error al insertar datos de {nombre_archivo}: {e}")
        conn.rollback()


# Paso 4: Función Principal de Ejecución

def main():
    """
    Función principal que coordina la configuración, procesamiento de archivos
    y almacenamiento en la base de datos.
    """
    # Configura la base de datos
    conn, cursor = configurar_base_datos(NOMBRE_BD)
    if conn is None:
        sys.exit(1) # Sale si la conexión a la BD falla

    # Verifica si la carpeta de facturas existe
    if not os.path.isdir(CARPETA_FACTURAS):
        print(f"Error: La carpeta de facturas '{CARPETA_FACTURAS}' no fue encontrada.")
        print("Por favor, verifica la ruta.")
        conn.close() # Cierra la conexión antes de salir
        sys.exit(1)

    # Obtiene la lista de archivos PDF en la carpeta
    try:
        archivos_en_carpeta = os.listdir(CARPETA_FACTURAS)
        lista_facturas_pdf = [archivo for archivo in archivos_en_carpeta if archivo.lower().endswith('.pdf')]
        print(f"\nEncontrados {len(lista_facturas_pdf)} archivos PDF en '{CARPETA_FACTURAS}'.")

        if not lista_facturas_pdf:
            print("No se encontraron archivos PDF para procesar.")
            conn.close()
            sys.exit(0) # Sale si no hay archivos

    except Exception as e:
        print(f"Error al listar archivos en '{CARPETA_FACTURAS}': {e}")
        conn.close()
        sys.exit(1)


    # Procesa cada archivo PDF encontrado
    # Obtiene la ruta configurada de Tesseract (si existe)
    tesseract_config_cmd = getattr(pytesseract.pytesseract, 'tesseract_cmd', 'tesseract') 

    for nombre_archivo in lista_facturas_pdf:
        ruta_completa_archivo = os.path.join(CARPETA_FACTURAS, nombre_archivo)
        print(f"\n--- Procesando: {nombre_archivo} ---")

        # Extrae texto del PDF (manejando nativos y escaneados)
        texto_completo = extraer_texto_de_pdf(ruta_completa_archivo, UMBRAL_CARACTERES_POR_PAGINA, tesseract_config_cmd)

        if texto_completo:
            # print(f"Texto extraído ({len(texto_completo)} caracteres):\n{texto_completo[:500]}...") # 
            
            # Extrae datos clave usando OpenAI
            print("  -> Enviando texto a OpenAI para extracción de datos...")
            datos_extraidos = extraer_datos_con_openai(texto_completo, MODELO_OPENAI)

            if datos_extraidos:
                print(f"  -> Extracción con OpenAI exitosa.") # Evita imprimir todos los datos aquí por si son extensos

                # Inserta los datos en la base de datos SQLite
                insertar_en_sqlite(conn, cursor, nombre_archivo, datos_extraidos)

            else:
                print(f"  -> No se pudieron extraer datos clave de {nombre_archivo} usando OpenAI.")
                
        else:
            print(f"  -> No se pudo extraer texto útil de {nombre_archivo}. Saltando.")
            

    
    # Paso 5: Finalizar y Cerrar Conexiones
    
    conn.close()
    print("\nProcesamiento de todas las facturas completado.")
    print(f"Base de datos {NOMBRE_BD} cerrada.")

# Punto de Entrada del Script
if __name__ == "__main__":
    main()