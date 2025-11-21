from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tu-clave-secreta-super-segura-cambiar-en-produccion')

# Configuración de MySQL
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', 'admin')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'proyecto')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# Decorador para requerir login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para acceder a esta página', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para requerir rol de administrador
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para acceder a esta página', 'warning')
            return redirect(url_for('login'))
        if session.get('rol_id') != 1:
            flash('No tienes permisos para acceder a esta página', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def utility_processor():
    return {
        'now': datetime.now,
        'current_year': lambda: datetime.now().year
    }

# Ruta principal - redirige según el rol
@app.route('/')
@login_required
def index():
    if session.get('rol_id') == 1:  # Administrador
        return redirect(url_for('dashboard'))
    else:  # Vendedor
        return redirect(url_for('ventas'))

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está autenticado, redirigir al índice
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Validación básica
        if not username or not password:
            flash('Por favor ingrese usuario y contraseña', 'danger')
            return render_template('login.html')
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                SELECT u.ID_Usuario, u.NombreUsuario, u.ContrasenaHash, 
                       u.Rol_ID, r.Nombre_Rol
                FROM Usuarios u
                INNER JOIN Roles r ON u.Rol_ID = r.ID_Rol
                WHERE u.NombreUsuario = %s AND u.Estado = 1
            """, (username,))
            user = cur.fetchone()
            cur.close()
            
            if user and check_password_hash(user['ContrasenaHash'], password):
                session['user_id'] = user['ID_Usuario']
                session['username'] = user['NombreUsuario']
                session['rol_id'] = user['Rol_ID']
                session['rol_nombre'] = user['Nombre_Rol']
                flash(f'Bienvenido {username}', 'success')
                return redirect(url_for('index'))
            else:
                # Log del intento fallido (opcional)
                flash('Usuario o contraseña incorrectos', 'danger')
                
        except Exception as e:
            flash('Error en el sistema, por favor intente más tarde', 'danger')
            # Log del error real para administradores
    
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('login'))

# Dashboard (solo administrador)
@app.route('/dashboard')
@admin_required
def dashboard():
    cur = mysql.connection.cursor()
    
    # Obtener estadísticas
    # Total de ventas del día
    cur.execute("""
        SELECT COALESCE(SUM(Total), 0) as total_dia
        FROM Facturacion
        WHERE DATE(Fecha) = CURDATE() AND Estado = 1
    """)
    ventas_dia = cur.fetchone()['total_dia']
    
    # Total de ventas del mes
    cur.execute("""
        SELECT COALESCE(SUM(Total), 0) as total_mes
        FROM Facturacion
        WHERE MONTH(Fecha) = MONTH(CURDATE()) 
        AND YEAR(Fecha) = YEAR(CURDATE()) 
        AND Estado = 1
    """)
    ventas_mes = cur.fetchone()['total_mes']
    
    # Productos con stock bajo
    cur.execute("""
        SELECT ID_Producto, Descripcion, Existencias, Stock_Minimo
        FROM Productos
        WHERE Existencias <= Stock_Minimo AND Estado = 1
        ORDER BY Existencias ASC
        LIMIT 10
    """)
    productos_bajo_stock = cur.fetchall()
    
    # Total de productos
    cur.execute("SELECT COUNT(*) as total FROM Productos WHERE Estado = 1")
    total_productos = cur.fetchone()['total']
    
    # Ventas de los últimos 7 días
    cur.execute("""
        SELECT DATE(Fecha) as fecha, COALESCE(SUM(Total), 0) as total
        FROM Facturacion
        WHERE Fecha >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) AND Estado = 1
        GROUP BY DATE(Fecha)
        ORDER BY fecha ASC
    """)
    ventas_semana = cur.fetchall()
    
    # Productos más vendidos
    cur.execute("""
        SELECT p.Descripcion, SUM(df.Cantidad) as total_vendido
        FROM Detalle_Facturacion df
        INNER JOIN Productos p ON df.ID_Producto = p.ID_Producto
        INNER JOIN Facturacion f ON df.ID_Factura = f.ID_Factura
        WHERE f.Fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) AND f.Estado = 1
        GROUP BY p.ID_Producto, p.Descripcion
        ORDER BY total_vendido DESC
        LIMIT 5
    """)
    productos_mas_vendidos = cur.fetchall()
    
    producto_id = request.args.get('producto')
    if producto_id:
        return redirect(url_for('inventario_entrada') + f'?producto={producto_id}')
    
    cur.close()
    
    return render_template('dashboard.html',
                         ventas_dia=ventas_dia,
                         ventas_mes=ventas_mes,
                         productos_bajo_stock=productos_bajo_stock,
                         total_productos=total_productos,
                         ventas_semana=ventas_semana,
                         productos_mas_vendidos=productos_mas_vendidos)

# Productos
@app.route('/productos')
@admin_required
def productos():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT p.*, c.Descripcion as Categoria, u.Descripcion as Unidad, u.Abreviatura
        FROM Productos p
        LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
        LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
        WHERE p.Estado = 1
        ORDER BY p.Descripcion
    """)
    productos = cur.fetchall()
    cur.close()
    return render_template('productos/lista.html', productos=productos)

@app.route('/productos/nuevo', methods=['GET', 'POST'])
@admin_required
def producto_nuevo():
    if request.method == 'POST':
        descripcion = request.form['descripcion']
        unidad_medida = request.form['unidad_medida']
        precio_venta = request.form['precio_venta']
        costo_promedio = request.form.get('costo_promedio', 0)
        categoria_id = request.form['categoria_id']
        stock_minimo = request.form.get('stock_minimo', 5)
        
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO Productos (Descripcion, Unidad_Medida, Precio_Venta, Costo_Promedio, 
                                 Categoria_ID, Stock_Minimo, Usuario_Creador)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (descripcion, unidad_medida, precio_venta, costo_promedio, categoria_id, 
              stock_minimo, session['user_id']))
        mysql.connection.commit()
        cur.close()
        
        flash('Producto creado exitosamente', 'success')
        return redirect(url_for('productos'))
    
    # GET - Cargar datos para el formulario
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Categorias ORDER BY Descripcion")
    categorias = cur.fetchall()
    cur.execute("SELECT * FROM Unidades_Medida ORDER BY Descripcion")
    unidades = cur.fetchall()
    cur.close()
    
    return render_template('productos/form.html', categorias=categorias, unidades=unidades)

@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def producto_editar(id):
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        descripcion = request.form['descripcion']
        unidad_medida = request.form['unidad_medida']
        precio_venta = request.form['precio_venta']
        costo_promedio = request.form.get('costo_promedio', 0)
        categoria_id = request.form['categoria_id']
        stock_minimo = request.form.get('stock_minimo', 5)
        
        cur.execute("""
            UPDATE Productos 
            SET Descripcion = %s, Unidad_Medida = %s, Precio_Venta = %s, 
                Costo_Promedio = %s, Categoria_ID = %s, Stock_Minimo = %s
            WHERE ID_Producto = %s
        """, (descripcion, unidad_medida, precio_venta, costo_promedio, 
              categoria_id, stock_minimo, id))
        mysql.connection.commit()
        cur.close()
        
        flash('Producto actualizado exitosamente', 'success')
        return redirect(url_for('productos'))
    
    # GET
    cur.execute("SELECT * FROM Productos WHERE ID_Producto = %s", (id,))
    producto = cur.fetchone()
    cur.execute("SELECT * FROM Categorias ORDER BY Descripcion")
    categorias = cur.fetchall()
    cur.execute("SELECT * FROM Unidades_Medida ORDER BY Descripcion")
    unidades = cur.fetchall()
    cur.close()
    
    return render_template('productos/form.html', producto=producto, 
                         categorias=categorias, unidades=unidades)

@app.route('/productos/eliminar/<int:id>', methods=['POST'])
@admin_required
def producto_eliminar(id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE Productos SET Estado = 0 WHERE ID_Producto = %s", (id,))
    mysql.connection.commit()
    cur.close()
    
    flash('Producto eliminado exitosamente', 'success')
    return redirect(url_for('productos'))

# Categorías
@app.route('/categorias')
@admin_required
def categorias():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Categorias ORDER BY Descripcion")
    categorias = cur.fetchall()
    cur.close()
    return render_template('productos/categorias.html', categorias=categorias)

@app.route('/categorias/nueva', methods=['POST'])
@admin_required
def categoria_nueva():
    descripcion = request.form['descripcion']
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO Categorias (Descripcion) VALUES (%s)", (descripcion,))
    mysql.connection.commit()
    cur.close()
    flash('Categoría creada exitosamente', 'success')
    return redirect(url_for('categorias'))

@app.route('/categorias/editar/<int:id>', methods=['POST'])
@admin_required
def categoria_editar(id):
    descripcion = request.form['descripcion']
    cur = mysql.connection.cursor()
    cur.execute("UPDATE Categorias SET Descripcion = %s WHERE ID_Categoria = %s", 
                (descripcion, id))
    mysql.connection.commit()
    cur.close()
    flash('Categoría actualizada exitosamente', 'success')
    return redirect(url_for('categorias'))

@app.route('/categorias/eliminar/<int:id>', methods=['POST'])
@admin_required
def categoria_eliminar(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM Categorias WHERE ID_Categoria = %s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('Categoría eliminada exitosamente', 'success')
    return redirect(url_for('categorias'))

# Unidades de Medida
@app.route('/unidades-medida')
@admin_required
def unidades_medida():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Unidades_Medida ORDER BY Descripcion")
    unidades = cur.fetchall()
    cur.close()
    return render_template('productos/unidades.html', unidades=unidades)

@app.route('/unidades-medida/nueva', methods=['POST'])
@admin_required
def unidad_nueva():
    descripcion = request.form['descripcion']
    abreviatura = request.form['abreviatura']
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO Unidades_Medida (Descripcion, Abreviatura) VALUES (%s, %s)", 
                (descripcion, abreviatura))
    mysql.connection.commit()
    cur.close()
    flash('Unidad de medida creada exitosamente', 'success')
    return redirect(url_for('unidades_medida'))

@app.route('/unidades-medida/editar/<int:id>', methods=['POST'])
@admin_required
def unidad_editar(id):
    descripcion = request.form['descripcion']
    abreviatura = request.form['abreviatura']
    cur = mysql.connection.cursor()
    cur.execute("UPDATE Unidades_Medida SET Descripcion = %s, Abreviatura = %s WHERE ID_Unidad = %s", 
                (descripcion, abreviatura, id))
    mysql.connection.commit()
    cur.close()
    flash('Unidad de medida actualizada exitosamente', 'success')
    return redirect(url_for('unidades_medida'))

@app.route('/unidades-medida/eliminar/<int:id>', methods=['POST'])
@admin_required
def unidad_eliminar(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM Unidades_Medida WHERE ID_Unidad = %s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('Unidad de medida eliminada exitosamente', 'success')
    return redirect(url_for('unidades_medida'))

# Proveedores
@app.route('/proveedores')
@admin_required
def proveedores():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Proveedores ORDER BY Nombre")
    proveedores = cur.fetchall()
    cur.close()
    return render_template('proveedores/lista.html', proveedores=proveedores)

@app.route('/proveedores/nuevo', methods=['GET', 'POST'])
@admin_required
def proveedor_nuevo():
    if request.method == 'POST':
        nombre = request.form['nombre']
        telefono = request.form.get('telefono', '')
        direccion = request.form.get('direccion', '')
        ruc_cedula = request.form.get('ruc_cedula', '')
        
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO Proveedores (Nombre, Telefono, Direccion, RUC_CEDULA)
            VALUES (%s, %s, %s, %s)
        """, (nombre, telefono, direccion, ruc_cedula))
        mysql.connection.commit()
        cur.close()
        
        flash('Proveedor creado exitosamente', 'success')
        return redirect(url_for('proveedores'))
    
    return render_template('proveedores/form.html')

@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def proveedor_editar(id):
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        nombre = request.form['nombre']
        telefono = request.form.get('telefono', '')
        direccion = request.form.get('direccion', '')
        ruc_cedula = request.form.get('ruc_cedula', '')
        
        cur.execute("""
            UPDATE Proveedores 
            SET Nombre = %s, Telefono = %s, Direccion = %s, RUC_CEDULA = %s
            WHERE ID_Proveedor = %s
        """, (nombre, telefono, direccion, ruc_cedula, id))
        mysql.connection.commit()
        cur.close()
        
        flash('Proveedor actualizado exitosamente', 'success')
        return redirect(url_for('proveedores'))
    
    cur.execute("SELECT * FROM Proveedores WHERE ID_Proveedor = %s", (id,))
    proveedor = cur.fetchone()
    cur.close()
    
    return render_template('proveedores/form.html', proveedor=proveedor)

@app.route('/proveedores/eliminar/<int:id>', methods=['POST'])
@admin_required
def proveedor_eliminar(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM Proveedores WHERE ID_Proveedor = %s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('Proveedor eliminado exitosamente', 'success')
    return redirect(url_for('proveedores'))

# Sistema de Ventas (POS) - Accesible para vendedores y administradores
@app.route('/ventas')
@login_required
def ventas():
    cur = mysql.connection.cursor()
    
    try:
        # Obtener productos activos con stock (corregido para tu estructura)
        cur.execute("""
            SELECT p.*, c.Descripcion as Categoria, u.Abreviatura,
                   COALESCE(ib.Existencias, 0) as Stock_Bodega
            FROM Productos p
            LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
            LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
            LEFT JOIN Inventario_Bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = 1
            WHERE p.Estado = 1 AND (p.Existencias > 0 OR ib.Existencias > 0)
            ORDER BY p.Descripcion
        """)
        productos = cur.fetchall()
        
        # Obtener métodos de pago activos
        cur.execute("SELECT * FROM Metodos_Pago ORDER BY Nombre")
        metodos_pago = cur.fetchall()
        
        # Obtener categorías activas para filtros
        cur.execute("SELECT * FROM Categorias ORDER BY Descripcion")
        categorias = cur.fetchall()
        
        # Obtener bodega principal para ventas
        cur.execute("SELECT * FROM Bodegas WHERE ID_Bodega = 1")
        bodega_principal = cur.fetchone()
        
        return render_template('ventas/pos.html', 
                             productos=productos, 
                             metodos_pago=metodos_pago,
                             categorias=categorias,
                             bodega_principal=bodega_principal)
    except Exception as e:
        flash(f'Error al cargar datos: {str(e)}', 'danger')
        return render_template('ventas/pos.html', 
                             productos=[], 
                             metodos_pago=[],
                             categorias=[],
                             bodega_principal=None)
    finally:
        cur.close()

@app.route('/ventas/procesar', methods=['POST'])
@login_required
def procesar_venta():
    try:
        data = request.get_json()
        items = data.get('items', [])
        metodo_pago_id = data.get('metodo_pago_id')
        efectivo = data.get('efectivo', 0)
        observacion = data.get('observacion', '')
        bodega_id = data.get('bodega_id', 1)
        
        # Validaciones básicas
        if not items:
            return jsonify({'success': False, 'message': 'No hay productos en el carrito'}), 400
        
        if not metodo_pago_id:
            return jsonify({'success': False, 'message': 'Selecciona un método de pago'}), 400
        
        # Calcular total
        total = sum(float(item['subtotal']) for item in items)
        cambio = max(float(efectivo) - total, 0)
        
        cur = mysql.connection.cursor()
        
        # Verificar stock disponible EN LA BODEGA (corregido)
        productos_sin_stock = []
        for item in items:
            producto_id = item['producto_id']
            cantidad_necesaria = float(item['cantidad'])
            
            cur.execute("""
                SELECT p.Descripcion, COALESCE(ib.Existencias, 0) as Stock_Bodega
                FROM Productos p
                LEFT JOIN Inventario_Bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                WHERE p.ID_Producto = %s AND p.Estado = 1
            """, (bodega_id, producto_id))
            
            inventario = cur.fetchone()
            stock_disponible = float(inventario['Stock_Bodega']) if inventario else 0
            
            if not inventario:
                productos_sin_stock.append(f"Producto ID {producto_id} no encontrado")
            elif stock_disponible < cantidad_necesaria:
                productos_sin_stock.append(
                    f"{inventario['Descripcion']} (disp: {stock_disponible}, neces: {cantidad_necesaria})"
                )
        
        if productos_sin_stock:
            mensaje_error = "Stock insuficiente: " + ", ".join(productos_sin_stock)
            return jsonify({'success': False, 'message': mensaje_error}), 400
        
        # Insertar factura (corregido para tu estructura)
        cur.execute("""
            INSERT INTO Facturacion (Total, Efectivo, Cambio, ID_MetodoPago, Observacion, ID_Usuario)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (total, efectivo, cambio, metodo_pago_id, observacion, session['user_id']))
        
        factura_id = cur.lastrowid
        
        # Obtener ID del tipo de movimiento para venta (corregido)
        cur.execute("""
            SELECT ID_TipoMovimiento 
            FROM Catalogo_Movimientos 
            WHERE Descripcion LIKE '%VENTA%' AND Adicion = 'SALIDA'
        """)
        tipo_movimiento_venta = cur.fetchone()
        
        if not tipo_movimiento_venta:
            mysql.connection.rollback()
            return jsonify({'success': False, 'message': 'Tipo de movimiento para venta no configurado'}), 500
        
        # Insertar movimiento de inventario para la venta
        cur.execute("""
            INSERT INTO Movimientos_Inventario 
            (ID_TipoMovimiento, Observacion, ID_Bodega)
            VALUES (%s, %s, %s)
        """, (tipo_movimiento_venta['ID_TipoMovimiento'], f"Venta - Factura #{factura_id}", bodega_id))
        
        movimiento_id = cur.lastrowid
        
        # Insertar detalles de factura y ACTUALIZAR STOCK
        for item in items:
            producto_id = item['producto_id']
            cantidad = float(item['cantidad'])
            precio_venta = float(item['precio_venta'])
            subtotal = float(item['subtotal'])
            
            # Insertar detalle de factura
            cur.execute("""
                INSERT INTO Detalle_Facturacion (ID_Factura, ID_Producto, Cantidad, Precio_Venta, Subtotal)
                VALUES (%s, %s, %s, %s, %s)
            """, (factura_id, producto_id, cantidad, precio_venta, subtotal))
            
            # Insertar detalle en movimiento de inventario (corregido tipo de datos)
            cur.execute("""
                INSERT INTO Detalle_Movimiento_Inventario 
                (ID_Movimiento, ID_Producto, Cantidad, Costo, Costo_Total)
                VALUES (%s, %s, %s, %s, %s)
            """, (movimiento_id, producto_id, cantidad, 0, 0))
            
            # ACTUALIZAR STOCK EN PRODUCTOS
            cur.execute("""
                UPDATE Productos 
                SET Existencias = Existencias - %s
                WHERE ID_Producto = %s
            """, (cantidad, producto_id))
            
            # ACTUALIZAR INVENTARIO EN BODEGA (manejar INSERT si no existe)
            cur.execute("""
                SELECT 1 FROM Inventario_Bodega 
                WHERE ID_Producto = %s AND ID_Bodega = %s
            """, (producto_id, bodega_id))
            
            if cur.fetchone():
                cur.execute("""
                    UPDATE Inventario_Bodega 
                    SET Existencias = Existencias - %s 
                    WHERE ID_Producto = %s AND ID_Bodega = %s
                """, (cantidad, producto_id, bodega_id))
            else:
                cur.execute("""
                    INSERT INTO Inventario_Bodega (ID_Bodega, ID_Producto, Existencias)
                    VALUES (%s, %s, %s)
                """, (bodega_id, producto_id, -cantidad))
        
        mysql.connection.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Venta procesada exitosamente! Factura #{factura_id}',
            'factura_id': factura_id,
            'total': total,
            'cambio': cambio
        })
        
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'success': False, 'message': f'Error al procesar la venta: {str(e)}'}), 500
    finally:
        cur.close()

@app.route('/ventas/historial')
@login_required
def ventas_historial():
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    
    cur = mysql.connection.cursor()
    
    try:
        # Construir consulta base (optimizada)
        if session.get('rol_id') == 2:  # Vendedor
            sql = """
                SELECT f.*, u.NombreUsuario, m.Nombre as MetodoPago
                FROM Facturacion f
                INNER JOIN Usuarios u ON f.ID_Usuario = u.ID_Usuario
                INNER JOIN Metodos_Pago m ON f.ID_MetodoPago = m.ID_MetodoPago
                WHERE f.ID_Usuario = %s AND f.Estado = 1
            """
            params = [session['user_id']]
        else:  # Administrador
            sql = """
                SELECT f.*, u.NombreUsuario, m.Nombre as MetodoPago
                FROM Facturacion f
                INNER JOIN Usuarios u ON f.ID_Usuario = u.ID_Usuario
                INNER JOIN Metodos_Pago m ON f.ID_MetodoPago = m.ID_MetodoPago
                WHERE f.Estado = 1
            """
            params = []
        
        # Aplicar filtros de fecha
        if fecha_inicio:
            sql += " AND f.Fecha >= %s"
            params.append(fecha_inicio)
        
        if fecha_fin:
            sql += " AND f.Fecha <= %s"
            params.append(fecha_fin)
        
        sql += " ORDER BY f.Fecha DESC, f.Hora DESC LIMIT 100"
        
        cur.execute(sql, params)
        ventas = cur.fetchall()
        
        # Estadísticas
        total_ventas = len(ventas)
        total_monto = sum(float(venta['Total']) for venta in ventas) if ventas else 0
        
        mensaje = f'Mostrando {total_ventas} ventas - Total: ${total_monto:.2f}' if fecha_inicio or fecha_fin else f'Historial de ventas - {total_ventas} registros'
        
        return render_template('ventas/historial.html', 
                             ventas=ventas, 
                             fecha_inicio=fecha_inicio, 
                             fecha_fin=fecha_fin,
                             mensaje=mensaje)
    except Exception as e:
        flash(f'Error al cargar historial: {str(e)}', 'danger')
        return render_template('ventas/historial.html', ventas=[])
    finally:
        cur.close()

@app.route('/ventas/detalle/<int:id>')
@login_required
def venta_detalle(id):
    cur = mysql.connection.cursor()
    
    try:
        # Obtener factura
        cur.execute("""
            SELECT f.*, u.NombreUsuario, m.Nombre as MetodoPago
            FROM Facturacion f
            INNER JOIN Usuarios u ON f.ID_Usuario = u.ID_Usuario
            INNER JOIN Metodos_Pago m ON f.ID_MetodoPago = m.ID_MetodoPago
            WHERE f.ID_Factura = %s AND f.Estado = 1
        """, (id,))
        factura = cur.fetchone()
        
        if not factura:
            flash('Factura no encontrada', 'danger')
            return redirect(url_for('ventas_historial'))
        
        # Verificar permisos
        if session.get('rol_id') == 2 and factura['ID_Usuario'] != session['user_id']:
            flash('No tienes permisos para ver esta factura', 'danger')
            return redirect(url_for('ventas_historial'))
        
        # Obtener detalles
        cur.execute("""
            SELECT df.*, p.Descripcion as Producto, u.Abreviatura
            FROM Detalle_Facturacion df
            INNER JOIN Productos p ON df.ID_Producto = p.ID_Producto
            LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
            WHERE df.ID_Factura = %s
        """, (id,))
        detalles = cur.fetchall()
        
        return render_template('ventas/detalle.html', factura=factura, detalles=detalles)
    except Exception as e:
        flash(f'Error al cargar detalle: {str(e)}', 'danger')
        return redirect(url_for('ventas_historial'))
    finally:
        cur.close()

@app.route('/api/productos/buscar')
@login_required
def buscar_productos():
    query = request.args.get('q', '')
    categoria_id = request.args.get('categoria', '')
    bodega_id = request.args.get('bodega_id', 1)
    
    cur = mysql.connection.cursor()
    
    try:
        sql = """
            SELECT p.*, c.Descripcion as Categoria, u.Abreviatura,
                   COALESCE(ib.Existencias, 0) as Stock_Bodega
            FROM Productos p
            LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
            LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
            LEFT JOIN Inventario_Bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
            WHERE p.Estado = 1 AND (p.Existencias > 0 OR ib.Existencias > 0)
        """
        params = [bodega_id]
        
        if query:
            sql += " AND (p.Descripcion LIKE %s OR p.ID_Producto = %s)"
            params.extend([f'%{query}%', query if query.isdigit() else '0'])
        
        if categoria_id and categoria_id != 'todas':
            sql += " AND p.Categoria_ID = %s"
            params.append(categoria_id)
        
        sql += " ORDER BY p.Descripcion LIMIT 50"
        
        cur.execute(sql, params)
        productos = cur.fetchall()
        
        return jsonify([dict(producto) for producto in productos])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()

@app.route('/api/producto/<int:id>')
@login_required
def obtener_producto(id):
    bodega_id = request.args.get('bodega_id', 1)
    
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            SELECT p.*, c.Descripcion as Categoria, u.Abreviatura,
                   COALESCE(ib.Existencias, 0) as Stock_Bodega
            FROM Productos p
            LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
            LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
            LEFT JOIN Inventario_Bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
            WHERE p.ID_Producto = %s AND p.Estado = 1
        """, (bodega_id, id))
        producto = cur.fetchone()
        
        if producto:
            return jsonify(dict(producto))
        
        return jsonify({'error': 'Producto no encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()

# Inventario - Gestión de movimientos
@app.route('/inventario')
@admin_required
def inventario():
    cur = mysql.connection.cursor()
    
    # Obtener movimientos recientes
    cur.execute("""
        SELECT mi.*, cm.Descripcion as TipoMovimiento, cm.Letra, 
               p.Nombre as Proveedor, b.Nombre as Bodega
        FROM Movimientos_Inventario mi
        INNER JOIN Catalogo_Movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
        LEFT JOIN Proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
        LEFT JOIN Bodegas b ON mi.ID_Bodega = b.ID_Bodega
        ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC
        LIMIT 100
    """)
    movimientos = cur.fetchall()
    
    cur.close()
    return render_template('inventario/lista.html', movimientos=movimientos)

@app.route('/inventario/entrada', methods=['GET', 'POST'])
@admin_required
def inventario_entrada():
    if request.method == 'POST':
        try:
            data = request.get_json()
            tipo_movimiento_id = data.get('tipo_movimiento_id')
            proveedor_id = data.get('proveedor_id')
            bodega_id = data.get('bodega_id')
            n_factura = data.get('n_factura', '')
            observacion = data.get('observacion', '')
            items = data.get('items', [])
            
            if not items:
                flash('No hay productos en el movimiento', 'warning')
                return jsonify({'success': False, 'message': 'No hay productos en el movimiento'}), 400
            
            cur = mysql.connection.cursor()
            
            # VERIFICAR que el tipo de movimiento es de entrada
            cur.execute("SELECT Descripcion, Adicion FROM Catalogo_Movimientos WHERE ID_TipoMovimiento = %s", (tipo_movimiento_id,))
            tipo_movimiento = cur.fetchone()
            
            if not tipo_movimiento or tipo_movimiento['Adicion'] != 'ENTRADA':
                flash('Tipo de movimiento no válido para entrada', 'danger')
                return jsonify({'success': False, 'message': 'Tipo de movimiento no válido para entrada'}), 400
            
            # Insertar movimiento
            cur.execute("""
                INSERT INTO Movimientos_Inventario 
                (ID_TipoMovimiento, N_Factura, ID_Proveedor, Observacion, ID_Bodega)
                VALUES (%s, %s, %s, %s, %s)
            """, (tipo_movimiento_id, n_factura, proveedor_id, observacion, bodega_id))
            
            movimiento_id = cur.lastrowid
            
            # Obtener nombre de bodega para el mensaje
            cur.execute("SELECT Nombre FROM Bodegas WHERE ID_Bodega = %s", (bodega_id,))
            bodega_nombre = cur.fetchone()['Nombre']
            
            # Procesar cada item del movimiento
            total_productos = 0
            for item in items:
                producto_id = item['producto_id']
                cantidad = item['cantidad']
                costo = item['costo']
                costo_total = item['costo_total']
                
                total_productos += cantidad
                
                # Insertar detalle
                cur.execute("""
                    INSERT INTO Detalle_Movimiento_Inventario 
                    (ID_Movimiento, ID_Producto, Cantidad, Costo, Costo_Total)
                    VALUES (%s, %s, %s, %s, %s)
                """, (movimiento_id, producto_id, cantidad, costo, costo_total))
                
                # ACTUALIZAR INVENTARIO EN BODEGA
                cur.execute("""
                    INSERT INTO Inventario_Bodega (ID_Bodega, ID_Producto, Existencias)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                    Existencias = Existencias + VALUES(Existencias)
                """, (bodega_id, producto_id, cantidad))
                
                # ACTUALIZAR COSTO PROMEDIO Y EXISTENCIAS TOTALES
                cur.execute("""
                    UPDATE Productos 
                    SET Existencias = Existencias + %s,
                        Costo_Promedio = CASE 
                            WHEN Existencias = 0 THEN %s
                            ELSE ((Existencias * Costo_Promedio) + (%s * %s)) / (Existencias + %s)
                        END
                    WHERE ID_Producto = %s
                """, (cantidad, costo, cantidad, costo, cantidad, producto_id))
            
            mysql.connection.commit()
            cur.close()
            
            flash(f'✅ Entrada de inventario registrada exitosamente! Movimiento #{movimiento_id} - {total_productos} unidades en {bodega_nombre}', 'success')
            return jsonify({
                'success': True,
                'message': 'Entrada de inventario registrada exitosamente',
                'movimiento_id': movimiento_id
            })
            
        except Exception as e:
            mysql.connection.rollback()
            flash(f'❌ Error al registrar entrada de inventario: {str(e)}', 'danger')
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # GET (mantener igual)
    cur = mysql.connection.cursor()
    
    cur.execute("""
        SELECT p.*, c.Descripcion as Categoria, u.Abreviatura
        FROM Productos p
        LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
        LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
        WHERE p.Estado = 1
        ORDER BY p.Descripcion
    """)
    productos = cur.fetchall()
    
    cur.execute("SELECT * FROM Proveedores ORDER BY Nombre")
    proveedores = cur.fetchall()
    
    cur.execute("SELECT * FROM Bodegas ORDER BY Nombre")
    bodegas = cur.fetchall()
    
    cur.execute("SELECT * FROM Catalogo_Movimientos WHERE Adicion = 'ENTRADA' ORDER BY Descripcion")
    tipos_movimiento = cur.fetchall()
    
    cur.close()
    
    return render_template('inventario/entrada.html',
                         productos=productos,
                         proveedores=proveedores,
                         bodegas=bodegas,
                         tipos_movimiento=tipos_movimiento)

@app.route('/inventario/salida', methods=['GET', 'POST'])
@admin_required
def inventario_salida():
    if request.method == 'POST':
        try:
            data = request.get_json()
            tipo_movimiento_id = data.get('tipo_movimiento_id')
            bodega_id = data.get('bodega_id')
            observacion = data.get('observacion', '')
            items = data.get('items', [])
            
            if not items:
                flash('No hay productos en el movimiento', 'warning')
                return jsonify({'success': False, 'message': 'No hay productos en el movimiento'}), 400
            
            cur = mysql.connection.cursor()
            
            # VERIFICAR que el tipo de movimiento es de salida
            cur.execute("SELECT Descripcion, Adicion FROM Catalogo_Movimientos WHERE ID_TipoMovimiento = %s", (tipo_movimiento_id,))
            tipo_movimiento = cur.fetchone()
            
            if not tipo_movimiento or tipo_movimiento['Adicion'] != 'SALIDA':
                flash('Tipo de movimiento no válido para salida', 'danger')
                return jsonify({'success': False, 'message': 'Tipo de movimiento no válido para salida'}), 400
            
            # Obtener nombre de bodega para mensajes
            cur.execute("SELECT Nombre FROM Bodegas WHERE ID_Bodega = %s", (bodega_id,))
            bodega_nombre = cur.fetchone()['Nombre']
            
            # Verificar stock disponible EN LA BODEGA ESPECÍFICA
            productos_sin_stock = []
            for item in items:
                cur.execute("""
                    SELECT COALESCE(ib.Existencias, 0) as Existencias_Bodega, 
                           p.Descripcion as Nombre_Producto
                    FROM Productos p
                    LEFT JOIN Inventario_Bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                    WHERE p.ID_Producto = %s
                """, (bodega_id, item['producto_id']))
                
                inventario = cur.fetchone()
                stock_disponible = inventario['Existencias_Bodega'] if inventario else 0
                
                if not inventario or stock_disponible < item['cantidad']:
                    productos_sin_stock.append({
                        'producto': inventario['Nombre_Producto'] if inventario else f"ID {item['producto_id']}",
                        'disponible': stock_disponible,
                        'solicitado': item['cantidad']
                    })
            
            if productos_sin_stock:
                mensaje_error = "Stock insuficiente: " + ", ".join([
                    f"{p['producto']} (disp: {p['disponible']}, neces: {p['solicitado']})" 
                    for p in productos_sin_stock
                ])
                flash(mensaje_error, 'danger')
                return jsonify({'success': False, 'message': mensaje_error}), 400
            
            # Insertar movimiento
            cur.execute("""
                INSERT INTO Movimientos_Inventario 
                (ID_TipoMovimiento, Observacion, ID_Bodega)
                VALUES (%s, %s, %s)
            """, (tipo_movimiento_id, observacion, bodega_id))
            
            movimiento_id = cur.lastrowid
            
            # Insertar detalles y ACTUALIZAR INVENTARIO
            total_productos = 0
            for item in items:
                producto_id = item['producto_id']
                cantidad = item['cantidad']
                costo = item.get('costo', 0)
                costo_total = item.get('costo_total', 0)
                
                total_productos += cantidad
                
                # Insertar detalle
                cur.execute("""
                    INSERT INTO Detalle_Movimiento_Inventario 
                    (ID_Movimiento, ID_Producto, Cantidad, Costo, Costo_Total)
                    VALUES (%s, %s, %s, %s, %s)
                """, (movimiento_id, producto_id, cantidad, costo, costo_total))
                
                # ACTUALIZAR INVENTARIO EN BODEGA
                cur.execute("""
                    UPDATE Inventario_Bodega 
                    SET Existencias = Existencias - %s
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (cantidad, bodega_id, producto_id))
                
                # ACTUALIZAR EXISTENCIAS TOTALES EN PRODUCTOS
                cur.execute("""
                    UPDATE Productos 
                    SET Existencias = Existencias - %s
                    WHERE ID_Producto = %s
                """, (cantidad, producto_id))
            
            mysql.connection.commit()
            cur.close()
            
            flash(f'✅ Salida de inventario registrada exitosamente! Movimiento #{movimiento_id} - {total_productos} unidades desde {bodega_nombre}', 'success')
            return jsonify({
                'success': True,
                'message': 'Salida de inventario registrada exitosamente',
                'movimiento_id': movimiento_id
            })
            
        except Exception as e:
            mysql.connection.rollback()
            flash(f'❌ Error al registrar salida de inventario: {str(e)}', 'danger')
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # GET (mantener igual)
    cur = mysql.connection.cursor()
    
    cur.execute("""
        SELECT p.*, c.Descripcion as Categoria, u.Abreviatura,
               COALESCE(ib.Existencias, 0) as Stock_Bodega
        FROM Productos p
        LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
        LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
        LEFT JOIN Inventario_Bodega ib ON p.ID_Producto = ib.ID_Producto
        WHERE p.Estado = 1 AND p.Existencias > 0
        ORDER BY p.Descripcion
    """)
    productos = cur.fetchall()
    
    cur.execute("SELECT * FROM Bodegas ORDER BY Nombre")
    bodegas = cur.fetchall()
    
    cur.execute("SELECT * FROM Catalogo_Movimientos WHERE Adicion = 'SALIDA' ORDER BY Descripcion")
    tipos_movimiento = cur.fetchall()
    
    cur.close()
    
    return render_template('inventario/salida.html',
                         productos=productos,
                         bodegas=bodegas,
                         tipos_movimiento=tipos_movimiento)

@app.route('/inventario/detalle/<int:id>')
@admin_required
def inventario_detalle(id):
    cur = mysql.connection.cursor()
    
    # Obtener movimiento
    cur.execute("""
        SELECT mi.*, cm.Descripcion as TipoMovimiento, cm.Adicion, cm.Letra,
               p.Nombre as Proveedor, b.Nombre as Bodega
        FROM Movimientos_Inventario mi
        INNER JOIN Catalogo_Movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
        LEFT JOIN Proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
        LEFT JOIN Bodegas b ON mi.ID_Bodega = b.ID_Bodega
        WHERE mi.ID_Movimiento = %s
    """, (id,))
    movimiento = cur.fetchone()
    
    if not movimiento:
        flash('❌ Movimiento no encontrado', 'danger')
        return redirect(url_for('inventario'))
    
    # Obtener detalles
    cur.execute("""
        SELECT dmi.*, p.Descripcion as Producto, u.Abreviatura
        FROM Detalle_Movimiento_Inventario dmi
        INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
        LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
        WHERE dmi.ID_Movimiento = %s
    """, (id,))
    detalles = cur.fetchall()
    
    cur.close()
    
    return render_template('inventario/detalle.html', 
                           movimiento=movimiento, 
                           detalles=detalles)

@app.route('/inventario/reportes')
@admin_required
def reportes():
    cur = mysql.connection.cursor()
    
    try:
        # Productos con más movimientos
        cur.execute("""
            SELECT p.Descripcion, 
                   SUM(CASE WHEN cm.Adicion = 'ENTRADA' THEN dmi.Cantidad ELSE 0 END) as Entradas,
                   SUM(CASE WHEN cm.Adicion = 'SALIDA' THEN dmi.Cantidad ELSE 0 END) as Salidas,
                   p.Existencias
            FROM Detalle_Movimiento_Inventario dmi
            INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
            INNER JOIN Movimientos_Inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
            INNER JOIN Catalogo_Movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
            WHERE mi.Fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY p.ID_Producto, p.Descripcion, p.Existencias
            ORDER BY (Entradas + Salidas) DESC
            LIMIT 10
        """)
        productos_movimientos = cur.fetchall()
        
        # Movimientos por tipo
        cur.execute("""
            SELECT cm.Descripcion, COUNT(*) as Total, cm.Letra, cm.Adicion
            FROM Movimientos_Inventario mi
            INNER JOIN Catalogo_Movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
            WHERE mi.Fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY cm.ID_TipoMovimiento, cm.Descripcion, cm.Letra, cm.Adicion
            ORDER BY Total DESC
        """)
        movimientos_tipo = cur.fetchall()
        
        # Valor del inventario
        cur.execute("""
            SELECT SUM(Existencias * Costo_Promedio) as ValorTotal
            FROM Productos
            WHERE Estado = 1
        """)
        valor_inventario = cur.fetchone()['ValorTotal'] or 0
        
        # Productos sin movimiento
        cur.execute("""
            SELECT p.Descripcion, p.Existencias, p.Fecha_Creacion
            FROM Productos p
            WHERE p.Estado = 1
            AND NOT EXISTS (
                SELECT 1 FROM Detalle_Movimiento_Inventario dmi
                INNER JOIN Movimientos_Inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                WHERE dmi.ID_Producto = p.ID_Producto
                AND mi.Fecha >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
            )
            ORDER BY p.Fecha_Creacion DESC
            LIMIT 10
        """)
        productos_sin_movimiento = cur.fetchall()
        
        # Productos con stock bajo
        cur.execute("""
            SELECT p.Descripcion, p.Existencias, p.Stock_Minimo, 
                   (p.Existencias - p.Stock_Minimo) as Diferencia
            FROM Productos p
            WHERE p.Estado = 1 AND p.Existencias <= p.Stock_Minimo
            ORDER BY Diferencia ASC
            LIMIT 10
        """)
        productos_stock_bajo = cur.fetchall()
        
        cur.close()
        
    except Exception as e:
        flash(f'❌ Error al generar reportes: {str(e)}', 'danger')
        # Inicializar variables vacías en caso de error
        productos_movimientos = []
        movimientos_tipo = []
        valor_inventario = 0
        productos_sin_movimiento = []
        productos_stock_bajo = []
    
    return render_template('inventario/reportes.html',
                         productos_movimientos=productos_movimientos,
                         movimientos_tipo=movimientos_tipo,
                         valor_inventario=valor_inventario,
                         productos_sin_movimiento=productos_sin_movimiento,
                         productos_stock_bajo=productos_stock_bajo)

if __name__ == '__main__':
    app.run(debug=True)
