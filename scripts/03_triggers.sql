-- Triggers para mantener la integridad del inventario
USE sistema_ventas;

DELIMITER //

-- Trigger para actualizar existencias después de una venta
CREATE TRIGGER after_detalle_factura_insert
AFTER INSERT ON Detalle_Facturacion
FOR EACH ROW
BEGIN
    UPDATE Productos 
    SET Existencias = Existencias - NEW.Cantidad
    WHERE ID_Producto = NEW.ID_Producto;
END//

-- Trigger para actualizar existencias después de un movimiento de inventario
CREATE TRIGGER after_detalle_movimiento_insert
AFTER INSERT ON Detalle_Movimiento_Inventario
FOR EACH ROW
BEGIN
    DECLARE tipo_adicion VARCHAR(10);
    
    SELECT Adicion INTO tipo_adicion
    FROM Catalogo_Movimientos cm
    INNER JOIN Movimientos_Inventario mi ON cm.ID_TipoMovimiento = mi.ID_TipoMovimiento
    WHERE mi.ID_Movimiento = NEW.ID_Movimiento;
    
    IF tipo_adicion = 'SI' THEN
        UPDATE Productos 
        SET Existencias = Existencias + NEW.Cantidad
        WHERE ID_Producto = NEW.ID_Producto;
    ELSE
        UPDATE Productos 
        SET Existencias = Existencias - NEW.Cantidad
        WHERE ID_Producto = NEW.ID_Producto;
    END IF;
END//

-- Trigger para actualizar inventario por bodega
CREATE TRIGGER after_movimiento_update_bodega
AFTER INSERT ON Detalle_Movimiento_Inventario
FOR EACH ROW
BEGIN
    DECLARE bodega_id INT;
    DECLARE tipo_adicion VARCHAR(10);
    
    SELECT mi.ID_Bodega, cm.Adicion INTO bodega_id, tipo_adicion
    FROM Movimientos_Inventario mi
    INNER JOIN Catalogo_Movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
    WHERE mi.ID_Movimiento = NEW.ID_Movimiento;
    
    IF EXISTS (SELECT 1 FROM Inventario_Bodega WHERE ID_Bodega = bodega_id AND ID_Producto = NEW.ID_Producto) THEN
        IF tipo_adicion = 'SI' THEN
            UPDATE Inventario_Bodega 
            SET Existencias = Existencias + NEW.Cantidad
            WHERE ID_Bodega = bodega_id AND ID_Producto = NEW.ID_Producto;
        ELSE
            UPDATE Inventario_Bodega 
            SET Existencias = Existencias - NEW.Cantidad
            WHERE ID_Bodega = bodega_id AND ID_Producto = NEW.ID_Producto;
        END IF;
    ELSE
        INSERT INTO Inventario_Bodega (ID_Bodega, ID_Producto, Existencias)
        VALUES (bodega_id, NEW.ID_Producto, NEW.Cantidad);
    END IF;
END//

DELIMITER ;
