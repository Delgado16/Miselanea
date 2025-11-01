from flask import current_app

def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """
    Función helper para ejecutar queries de manera segura
    """
    from app import mysql
    
    cur = mysql.connection.cursor()
    try:
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        
        if commit:
            mysql.connection.commit()
            return cur.lastrowid
        
        if fetch_one:
            return cur.fetchone()
        
        if fetch_all:
            return cur.fetchall()
        
        return None
    except Exception as e:
        mysql.connection.rollback()
        raise e
    finally:
        cur.close()

def get_productos_bajo_stock():
    """Obtiene productos con stock bajo o crítico"""
    query = """
        SELECT ID_Producto, Descripcion, Existencias, Stock_Minimo,
               CASE 
                   WHEN Existencias = 0 THEN 'critico'
                   WHEN Existencias <= Stock_Minimo * 0.5 THEN 'muy_bajo'
                   ELSE 'bajo'
               END as nivel_alerta
        FROM Productos
        WHERE Existencias <= Stock_Minimo AND Estado = 1
        ORDER BY Existencias ASC
    """
    return execute_query(query, fetch_all=True)
