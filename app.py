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
    
    # Obtener productos activos con stock
    cur.execute("""
        SELECT p.*, c.Descripcion as Categoria, u.Abreviatura
        FROM Productos p
        LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
        LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
        WHERE p.Estado = 1 AND p.Existencias > 0
        ORDER BY p.Descripcion
    """)
    productos = cur.fetchall()
    
    # Obtener métodos de pago
    cur.execute("SELECT * FROM Metodos_Pago ORDER BY Nombre")
    metodos_pago = cur.fetchall()
    
    # Obtener categorías para filtros
    cur.execute("SELECT * FROM Categorias ORDER BY Descripcion")
    categorias = cur.fetchall()
    
    cur.close()
    
    return render_template('ventas/pos.html', 
                         productos=productos, 
                         metodos_pago=metodos_pago,
                         categorias=categorias)

@app.route('/ventas/procesar', methods=['POST'])
@login_required
def procesar_venta():
    try:
        data = request.get_json()
        items = data.get('items', [])
        metodo_pago_id = data.get('metodo_pago_id')
        efectivo = data.get('efectivo', 0)
        observacion = data.get('observacion', '')
        
        if not items:
            return jsonify({'success': False, 'message': 'No hay productos en el carrito'}), 400
        
        # Calcular total
        total = sum(item['subtotal'] for item in items)
        cambio = efectivo - total if efectivo > total else 0
        
        cur = mysql.connection.cursor()
        
        # Verificar stock disponible
        for item in items:
            cur.execute("SELECT Existencias FROM Productos WHERE ID_Producto = %s", 
                       (item['producto_id'],))
            producto = cur.fetchone()
            if not producto or producto['Existencias'] < item['cantidad']:
                cur.close()
                return jsonify({
                    'success': False, 
                    'message': f'Stock insuficiente para el producto ID {item["producto_id"]}'
                }), 400
        
        # Insertar factura
        cur.execute("""
            INSERT INTO Facturacion (Total, Efectivo, Cambio, ID_MetodoPago, Observacion, ID_Usuario)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (total, efectivo, cambio, metodo_pago_id, observacion, session['user_id']))
        
        factura_id = cur.lastrowid
        
        # Insertar detalles de factura
        for item in items:
            cur.execute("""
                INSERT INTO Detalle_Facturacion (ID_Factura, ID_Producto, Cantidad, Precio_Venta, Subtotal)
                VALUES (%s, %s, %s, %s, %s)
            """, (factura_id, item['producto_id'], item['cantidad'], 
                  item['precio_venta'], item['subtotal']))
        
        mysql.connection.commit()
        cur.close()
        
        return jsonify({
            'success': True, 
            'message': 'Venta procesada exitosamente',
            'factura_id': factura_id,
            'total': total,
            'cambio': cambio
        })
        
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/ventas/historial')
@login_required
def ventas_historial():
    cur = mysql.connection.cursor()
    
    # Si es vendedor, solo ve sus propias ventas
    if session.get('rol_id') == 2:
        cur.execute("""
            SELECT f.*, u.NombreUsuario, m.Nombre as MetodoPago
            FROM Facturacion f
            INNER JOIN Usuarios u ON f.ID_Usuario = u.ID_Usuario
            INNER JOIN Metodos_Pago m ON f.ID_MetodoPago = m.ID_MetodoPago
            WHERE f.ID_Usuario = %s AND f.Estado = 1
            ORDER BY f.Fecha DESC, f.Hora DESC
            LIMIT 100
        """, (session['user_id'],))
    else:
        # Administrador ve todas las ventas
        cur.execute("""
            SELECT f.*, u.NombreUsuario, m.Nombre as MetodoPago
            FROM Facturacion f
            INNER JOIN Usuarios u ON f.ID_Usuario = u.ID_Usuario
            INNER JOIN Metodos_Pago m ON f.ID_MetodoPago = m.ID_MetodoPago
            WHERE f.Estado = 1
            ORDER BY f.Fecha DESC, f.Hora DESC
            LIMIT 100
        """)
    
    ventas = cur.fetchall()
    cur.close()
    
    return render_template('ventas/historial.html', ventas=ventas)

@app.route('/ventas/detalle/<int:id>')
@login_required
def venta_detalle(id):
    cur = mysql.connection.cursor()
    
    # Obtener factura
    cur.execute("""
        SELECT f.*, u.NombreUsuario, m.Nombre as MetodoPago
        FROM Facturacion f
        INNER JOIN Usuarios u ON f.ID_Usuario = u.ID_Usuario
        INNER JOIN Metodos_Pago m ON f.ID_MetodoPago = m.ID_MetodoPago
        WHERE f.ID_Factura = %s
    """, (id,))
    factura = cur.fetchone()
    
    if not factura:
        flash('Factura no encontrada', 'danger')
        return redirect(url_for('ventas_historial'))
    
    # Verificar permisos (vendedor solo ve sus ventas)
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
    
    cur.close()
    
    return render_template('ventas/detalle.html', factura=factura, detalles=detalles)

@app.route('/api/productos/buscar')
@login_required
def buscar_productos():
    query = request.args.get('q', '')
    categoria_id = request.args.get('categoria', '')
    
    cur = mysql.connection.cursor()
    
    sql = """
        SELECT p.*, c.Descripcion as Categoria, u.Abreviatura
        FROM Productos p
        LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
        LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
        WHERE p.Estado = 1 AND p.Existencias > 0
    """
    params = []
    
    if query:
        sql += " AND p.Descripcion LIKE %s"
        params.append(f'%{query}%')
    
    if categoria_id:
        sql += " AND p.Categoria_ID = %s"
        params.append(categoria_id)
    
    sql += " ORDER BY p.Descripcion LIMIT 50"
    
    cur.execute(sql, params)
    productos = cur.fetchall()
    cur.close()
    
    return jsonify(productos)

@app.route('/api/producto/<int:id>')
@login_required
def obtener_producto(id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT p.*, c.Descripcion as Categoria, u.Abreviatura
        FROM Productos p
        LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
        LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
        WHERE p.ID_Producto = %s AND p.Estado = 1
    """, (id,))
    producto = cur.fetchone()
    cur.close()
    
    if producto:
        return jsonify(producto)
    return jsonify({'error': 'Producto no encontrado'}), 404

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
                return jsonify({'success': False, 'message': 'No hay productos en el movimiento'}), 400
            
            cur = mysql.connection.cursor()
            
            # Insertar movimiento
            cur.execute("""
                INSERT INTO Movimientos_Inventario 
                (ID_TipoMovimiento, N_Factura, ID_Proveedor, Observacion, ID_Bodega)
                VALUES (%s, %s, %s, %s, %s)
            """, (tipo_movimiento_id, n_factura, proveedor_id, observacion, bodega_id))
            
            movimiento_id = cur.lastrowid
            
            # Insertar detalles
            for item in items:
                cur.execute("""
                    INSERT INTO Detalle_Movimiento_Inventario 
                    (ID_Movimiento, ID_Producto, Cantidad, Costo, Costo_Total)
                    VALUES (%s, %s, %s, %s, %s)
                """, (movimiento_id, item['producto_id'], item['cantidad'], 
                      item['costo'], item['costo_total']))
            
            mysql.connection.commit()
            cur.close()
            
            return jsonify({
                'success': True,
                'message': 'Movimiento registrado exitosamente',
                'movimiento_id': movimiento_id
            })
            
        except Exception as e:
            mysql.connection.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # GET
    cur = mysql.connection.cursor()
    
    # Obtener productos
    cur.execute("""
        SELECT p.*, c.Descripcion as Categoria, u.Abreviatura
        FROM Productos p
        LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
        LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
        WHERE p.Estado = 1
        ORDER BY p.Descripcion
    """)
    productos = cur.fetchall()
    
    # Obtener proveedores
    cur.execute("SELECT * FROM Proveedores ORDER BY Nombre")
    proveedores = cur.fetchall()
    
    # Obtener bodegas
    cur.execute("SELECT * FROM Bodegas ORDER BY Nombre")
    bodegas = cur.fetchall()
    
    # Obtener tipos de movimiento (solo entradas)
    cur.execute("SELECT * FROM Catalogo_Movimientos WHERE Adicion = 'SI' ORDER BY Descripcion")
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
                return jsonify({'success': False, 'message': 'No hay productos en el movimiento'}), 400
            
            cur = mysql.connection.cursor()
            
            # Verificar stock disponible
            for item in items:
                cur.execute("SELECT Existencias FROM Productos WHERE ID_Producto = %s", 
                           (item['producto_id'],))
                producto = cur.fetchone()
                if not producto or producto['Existencias'] < item['cantidad']:
                    cur.close()
                    return jsonify({
                        'success': False,
                        'message': f'Stock insuficiente para el producto ID {item["producto_id"]}'
                    }), 400
            
            # Insertar movimiento
            cur.execute("""
                INSERT INTO Movimientos_Inventario 
                (ID_TipoMovimiento, Observacion, ID_Bodega)
                VALUES (%s, %s, %s)
            """, (tipo_movimiento_id, observacion, bodega_id))
            
            movimiento_id = cur.lastrowid
            
            # Insertar detalles
            for item in items:
                cur.execute("""
                    INSERT INTO Detalle_Movimiento_Inventario 
                    (ID_Movimiento, ID_Producto, Cantidad, Costo, Costo_Total)
                    VALUES (%s, %s, %s, %s, %s)
                """, (movimiento_id, item['producto_id'], item['cantidad'], 
                      item.get('costo', 0), item.get('costo_total', 0)))
            
            mysql.connection.commit()
            cur.close()
            
            return jsonify({
                'success': True,
                'message': 'Movimiento registrado exitosamente',
                'movimiento_id': movimiento_id
            })
            
        except Exception as e:
            mysql.connection.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # GET
    cur = mysql.connection.cursor()
    
    # Obtener productos con stock
    cur.execute("""
        SELECT p.*, c.Descripcion as Categoria, u.Abreviatura
        FROM Productos p
        LEFT JOIN Categorias c ON p.Categoria_ID = c.ID_Categoria
        LEFT JOIN Unidades_Medida u ON p.Unidad_Medida = u.ID_Unidad
        WHERE p.Estado = 1 AND p.Existencias > 0
        ORDER BY p.Descripcion
    """)
    productos = cur.fetchall()
    
    # Obtener bodegas
    cur.execute("SELECT * FROM Bodegas ORDER BY Nombre")
    bodegas = cur.fetchall()
    
    # Obtener tipos de movimiento (solo salidas)
    cur.execute("SELECT * FROM Catalogo_Movimientos WHERE Adicion = 'NO' ORDER BY Descripcion")
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
        flash('Movimiento no encontrado', 'danger')
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
    
    return render_template('inventario/detalle.html', movimiento=movimiento, detalles=detalles)

@app.route('/inventario/reportes')
@admin_required
def reportes():
    cur = mysql.connection.cursor()
    
    # Productos con más movimientos
    cur.execute("""
        SELECT p.Descripcion, 
               SUM(CASE WHEN cm.Adicion = 'SI' THEN dmi.Cantidad ELSE 0 END) as Entradas,
               SUM(CASE WHEN cm.Adicion = 'NO' THEN dmi.Cantidad ELSE 0 END) as Salidas,
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
        SELECT cm.Descripcion, COUNT(*) as Total, cm.Letra
        FROM Movimientos_Inventario mi
        INNER JOIN Catalogo_Movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
        WHERE mi.Fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        GROUP BY cm.ID_TipoMovimiento, cm.Descripcion, cm.Letra
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
    
    cur.close()
    
    return render_template('inventario/reportes.html',
                         productos_movimientos=productos_movimientos,
                         movimientos_tipo=movimientos_tipo,
                         valor_inventario=valor_inventario,
                         productos_sin_movimiento=productos_sin_movimiento)

if __name__ == '__main__':
    app.run(debug=True)
