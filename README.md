# Sistema de Punto de Venta (POS) - Flask

Sistema completo de gestión de ventas e inventario desarrollado con Flask, MySQL y Jinja2.

## Características

### Rol Administrador
- Dashboard con estadísticas en tiempo real
- Alertas de productos con stock bajo
- Gestión completa de productos
- Gestión de proveedores
- Gestión de unidades de medida
- Gestión de categorías
- Reportes de entradas y salidas
- Gestión de usuarios

### Rol Vendedor
- Sistema de ventas (POS)
- Consulta de inventario
- Historial de ventas

## Instalación

1. Clonar el repositorio
2. Crear un entorno virtual:
\`\`\`bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
\`\`\`

3. Instalar dependencias:
\`\`\`bash
pip install -r requirements.txt
\`\`\`

4. Configurar la base de datos:
   - Crear la base de datos MySQL ejecutando `scripts/01_create_database.sql`
   - Poblar datos iniciales con `scripts/02_seed_data.sql`
   - Crear triggers con `scripts/03_triggers.sql`

5. Configurar variables de entorno:
   - Copiar `.env.example` a `.env`
   - Configurar las credenciales de MySQL

6. Ejecutar la aplicación:
\`\`\`bash
python app.py
\`\`\`

## Credenciales por defecto

- Usuario: admin
- Contraseña: admin123

**IMPORTANTE:** Cambiar la contraseña después del primer login.

## Estructura del proyecto

\`\`\`
├── app.py                 # Aplicación principal
├── config.py             # Configuración
├── requirements.txt      # Dependencias
├── utils/               # Utilidades
│   ├── auth.py          # Autenticación
│   └── db_helpers.py    # Helpers de base de datos
├── templates/           # Templates Jinja2
├── static/             # CSS, JS, imágenes
└── scripts/            # Scripts SQL
\`\`\`

## Tecnologías

- Python 3.8+
- Flask 3.0
- MySQL 8.0+
- Jinja2
- Bootstrap 5
- JavaScript (Vanilla)
