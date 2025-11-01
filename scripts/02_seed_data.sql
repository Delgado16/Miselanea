-- Script para poblar datos iniciales
USE sistema_ventas;

-- Insertar Roles
INSERT INTO Roles (Nombre_Rol) VALUES 
('Administrador'),
('Vendedor');

-- Insertar usuario administrador por defecto
-- Contraseña: admin123 (debes cambiarla después del primer login)
INSERT INTO Usuarios (NombreUsuario, ContrasenaHash, Rol_ID, Estado) VALUES 
('admin', 'admin123!', 1, 1);

-- Insertar Métodos de Pago
INSERT INTO Metodos_Pago (Nombre) VALUES 
('Efectivo'),
('Tarjeta de Crédito'),
('Tarjeta de Débito'),
('Transferencia'),
('Cheque');

-- Insertar Tipos de Movimiento
INSERT INTO Catalogo_Movimientos (Descripcion, Adicion, Letra) VALUES 
('Entrada por Compra', 'SI', 'E'),
('Salida por Venta', 'NO', 'S'),
('Ajuste de Inventario', 'SI', 'A'),
('Devolución', 'SI', 'D');

-- Insertar Unidades de Medida
INSERT INTO Unidades_Medida (Descripcion, Abreviatura) VALUES 
('Unidad', 'UND'),
('Kilogramo', 'KG'),
('Gramo', 'GR'),
('Litro', 'LT'),
('Metro', 'MT'),
('Caja', 'CJA'),
('Paquete', 'PAQ'),
('Docena', 'DOC');

-- Insertar Categorías
INSERT INTO Categorias (Descripcion) VALUES 
('Alimentos'),
('Bebidas'),
('Limpieza'),
('Cuidado Personal'),
('Electrónica'),
('Papelería'),
('Otros');

-- Insertar Bodega Principal
INSERT INTO Bodegas (Nombre, Ubicacion) VALUES 
('Bodega Principal', 'Almacén Central'),
('Bodega Secundaria', 'Punto de Venta');

-- Insertar algunos proveedores de ejemplo
INSERT INTO Proveedores (Nombre, Telefono, Direccion, RUC_CEDULA) VALUES 
('Distribuidora Central', '555-0001', 'Av. Principal 123', '1234567890001'),
('Proveedor ABC', '555-0002', 'Calle Comercio 456', '0987654321001');
