import sqlite3
import json # Para convertir la lista de diccionarios a JSON
import os
from jinja2 import Environment, FileSystemLoader 


# Base de datos
NOMBRE_BD = 'facturas_analizadas.db'

# Template HTML
HTML_TEMPLATE = 'reporte_facturas_template.html'

# Reporte HTML 
OUTPUT_HTML = 'reporte_facturas.html'

# Configuración del entorno para cargar templates desde la carpeta actual
directorio_actual = os.path.dirname(os.path.abspath(__file__))
loader = FileSystemLoader(directorio_actual)
env = Environment(loader=loader)


# Funciones

def fetch_invoice_data(db_name):
    """
    Conecta a la base de datos SQLite y recupera todos los datos de la tabla 'facturas'.
    Retorna una lista de diccionarios, donde cada diccionario representa una fila de la tabla.
    """
    conn = None
    data = []
    try:
        conn = sqlite3.connect(db_name)
        conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre
        cursor = conn.cursor()

        
        cursor.execute("SELECT * FROM facturas")

        
        rows = cursor.fetchall()

        # Convierte las filas a una lista de diccionarios
        # Esto es necesario para pasar los datos a Jinja2 y luego a JSON para DataTables
        data = [dict(row) for row in rows]

        print(f"Recuperados {len(data)} registros de la base de datos.")
        return data

    except FileNotFoundError:
        print(f"Error: La base de datos '{db_name}' no fue encontrada.")
        return None
    except Exception as e:
        print(f"Error al recuperar datos de la base de datos: {e}")
        return None
    finally:
        
        if conn:
            conn.close()


def render_report_html(template_name, output_filename, data_to_render):
    """
    Carga el template HTML, renderiza los datos en él y guarda el resultado en un archivo.
    """
    try:
        # Cargar el template
        template = env.get_template(template_name)

        # Pasamos la lista de diccionarios a una variable llamada 'facturas_data' en el template.
        # El filtro 'tojson' de Jinja2 es crucial para convertir la lista a una cadena JSON válida para JavaScript.
        rendered_html = template.render(facturas_data=data_to_render)

        # Guarda el HTML renderizado en el archivo de salida
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(rendered_html)

        print(f"Reporte HTML generado exitosamente en '{output_filename}'.")

    except FileNotFoundError:
        print(f"Error: El archivo de template '{template_name}' no fue encontrado.")
    except Exception as e:
        print(f"Error al renderizar o guardar el reporte HTML: {e}")



# Ejecución Principal

if __name__ == "__main__":
    # 1. Recupera los datos de la base de datos
    invoice_data = fetch_invoice_data(NOMBRE_BD)

    if invoice_data is not None: # Procede solo si se recuperaron datos (incluso si la lista está vacía)
        # 2. Genera el reporte HTML
        render_report_html(HTML_TEMPLATE, OUTPUT_HTML, invoice_data)
    else:
        print("No se pudieron recuperar datos de la base de datos. No se generará el reporte.")