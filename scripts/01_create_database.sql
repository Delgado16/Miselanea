-- Script para crear la base de datos MySQL
-- Ejecutar este script primero

CREATE DATABASE IF NOT EXISTS sistema_ventas CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE sistema_ventas;

-- Tabla de Roles
CREATE TABLE Roles (
    ID_Rol INT AUTO_INCREMENT PRIMARY KEY,
    Nombre_Rol VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- Tabla de Usuarios del Sistema
CREATE TABLE Usuarios (
    ID_Usuario INT AUTO_INCREMENT PRIMARY KEY,
    NombreUsuario VARCHAR(100) UNIQUE NOT NULL,
    ContrasenaHash VARCHAR(255) NOT NULL,
    Rol_ID INT,
    Estado TINYINT DEFAULT 1,
    Fecha_Creacion DATE DEFAULT (CURRENT_DATE),
    FOREIGN KEY (Rol_ID) REFERENCES Roles(ID_Rol)
) ENGINE=InnoDB;

-- Tabla de Métodos de Pago
CREATE TABLE Metodos_Pago (
    ID_MetodoPago INT AUTO_INCREMENT PRIMARY KEY,
    Nombre VARCHAR(50) NOT NULL
) ENGINE=InnoDB;

-- Tabla de Proveedores
CREATE TABLE Proveedores (
    ID_Proveedor INT AUTO_INCREMENT PRIMARY KEY,
    Nombre VARCHAR(200) NOT NULL,
    Telefono VARCHAR(20),
    Direccion TEXT,
    RUC_CEDULA VARCHAR(20)
) ENGINE=InnoDB;

-- Catálogo de Tipos de Movimiento
CREATE TABLE Catalogo_Movimientos (
    ID_TipoMovimiento INT AUTO_INCREMENT PRIMARY KEY,
    Descripcion VARCHAR(100),
    Adicion VARCHAR(10),
    Letra VARCHAR(5)
) ENGINE=InnoDB;

-- Tabla de Unidades de Medida
CREATE TABLE Unidades_Medida (
    ID_Unidad INT AUTO_INCREMENT PRIMARY KEY,
    Descripcion VARCHAR(100) NOT NULL,
    Abreviatura VARCHAR(10)
) ENGINE=InnoDB;

-- Tabla de Categorías de Productos
CREATE TABLE Categorias (
    ID_Categoria INT AUTO_INCREMENT PRIMARY KEY,
    Descripcion VARCHAR(100) NOT NULL
) ENGINE=InnoDB;

-- Tabla de Bodegas
CREATE TABLE Bodegas (
    ID_Bodega INT AUTO_INCREMENT PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    Ubicacion VARCHAR(200)
) ENGINE=InnoDB;

-- Tabla de Productos
CREATE TABLE Productos (
    ID_Producto INT AUTO_INCREMENT PRIMARY KEY,
    Descripcion VARCHAR(200) NOT NULL,
    Unidad_Medida INT,
    Existencias DECIMAL(10,2) DEFAULT 0,
    Estado TINYINT DEFAULT 1,
    Costo_Promedio DECIMAL(10,2),
    Precio_Venta DECIMAL(10,2),
    Categoria_ID INT,
    Fecha_Creacion DATE DEFAULT (CURRENT_DATE),
    Usuario_Creador INT,
    Stock_Minimo DECIMAL(10,2) DEFAULT 5,
    FOREIGN KEY (Unidad_Medida) REFERENCES Unidades_Medida(ID_Unidad),
    FOREIGN KEY (Categoria_ID) REFERENCES Categorias(ID_Categoria),
    FOREIGN KEY (Usuario_Creador) REFERENCES Usuarios(ID_Usuario)
) ENGINE=InnoDB;

-- Tabla de Facturación (Ventas)
CREATE TABLE Facturacion (
    ID_Factura INT AUTO_INCREMENT PRIMARY KEY,
    Fecha DATE NOT NULL DEFAULT (CURRENT_DATE),
    Hora TIME NOT NULL DEFAULT (CURRENT_TIME),
    Total DECIMAL(10,2) NOT NULL,
    Efectivo DECIMAL(10,2),
    Cambio DECIMAL(10,2),
    ID_MetodoPago INT,
    Observacion TEXT,
    ID_Usuario INT,
    Estado TINYINT DEFAULT 1,
    FOREIGN KEY (ID_MetodoPago) REFERENCES Metodos_Pago(ID_MetodoPago),
    FOREIGN KEY (ID_Usuario) REFERENCES Usuarios(ID_Usuario)
) ENGINE=InnoDB;

-- Detalle de Facturación
CREATE TABLE Detalle_Facturacion (
    ID_Detalle INT AUTO_INCREMENT PRIMARY KEY,
    ID_Factura INT,
    ID_Producto INT,
    Cantidad DECIMAL(10,2),
    Precio_Venta DECIMAL(10,2),
    Subtotal DECIMAL(10,2),
    FOREIGN KEY (ID_Factura) REFERENCES Facturacion(ID_Factura) ON DELETE CASCADE,
    FOREIGN KEY (ID_Producto) REFERENCES Productos(ID_Producto)
) ENGINE=InnoDB;

-- Tabla de Movimientos de Inventario
CREATE TABLE Movimientos_Inventario (
    ID_Movimiento INT AUTO_INCREMENT PRIMARY KEY,
    ID_TipoMovimiento INT,
    N_Factura VARCHAR(50),
    Fecha DATE DEFAULT (CURRENT_DATE),
    ID_Proveedor INT,
    Observacion TEXT,
    ID_Bodega INT,
    FOREIGN KEY (ID_TipoMovimiento) REFERENCES Catalogo_Movimientos(ID_TipoMovimiento),
    FOREIGN KEY (ID_Proveedor) REFERENCES Proveedores(ID_Proveedor),
    FOREIGN KEY (ID_Bodega) REFERENCES Bodegas(ID_Bodega)
) ENGINE=InnoDB;

-- Detalle de Movimientos de Inventario
CREATE TABLE Detalle_Movimiento_Inventario (
    ID_Detalle INT AUTO_INCREMENT PRIMARY KEY,
    ID_Movimiento INT,
    ID_Producto INT,
    Cantidad INT,
    Costo DECIMAL(10,2),
    Costo_Total DECIMAL(10,2),
    FOREIGN KEY (ID_Movimiento) REFERENCES Movimientos_Inventario(ID_Movimiento) ON DELETE CASCADE,
    FOREIGN KEY (ID_Producto) REFERENCES Productos(ID_Producto)
) ENGINE=InnoDB;

-- Tabla de Inventario por Bodega
CREATE TABLE Inventario_Bodega (
    ID_Bodega INT,
    ID_Producto INT,
    Existencias DECIMAL(10,2) DEFAULT 0,
    PRIMARY KEY (ID_Bodega, ID_Producto),
    FOREIGN KEY (ID_Bodega) REFERENCES Bodegas(ID_Bodega),
    FOREIGN KEY (ID_Producto) REFERENCES Productos(ID_Producto)
) ENGINE=InnoDB;

-- Índices para mejorar el rendimiento
CREATE INDEX idx_productos_descripcion ON Productos(Descripcion);
CREATE INDEX idx_facturacion_fecha ON Facturacion(Fecha);
CREATE INDEX idx_movimientos_fecha ON Movimientos_Inventario(Fecha);
CREATE INDEX idx_detalle_factura_producto ON Detalle_Facturacion(ID_Producto);
CREATE INDEX idx_detalle_movimiento_producto ON Detalle_Movimiento_Inventario(ID_Producto);
CREATE INDEX idx_usuarios_nombre ON Usuarios(NombreUsuario);
CREATE INDEX idx_productos_estado ON Productos(Estado);
