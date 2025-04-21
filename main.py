from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from factura_afip import emitir_factura

app = FastAPI()

# Modelo para los productos
class Producto(BaseModel):
    nombre: str
    precio: float

# Modelo para la venta (sin CUIT)
class Venta(BaseModel):
    productos: List[Producto]
    total: float
    forma_pago: str

# Ruta de prueba
@app.get("/")
def home():
    return {"mensaje": "Backend de AFIP activo"}

# Endpoint principal para facturar
@app.post("/facturar")
def facturar(venta: Venta):
    try:
        # Preparo lista simple para enviar al módulo de AFIP
        lista_productos = [(p.nombre, p.precio) for p in venta.productos]

        # Emito la factura
        resultado = emitir_factura(
            productos=lista_productos,
            total=venta.total,
            forma_pago=venta.forma_pago
        )

        # Devuelvo los datos de la factura
        return {
            "estado": "aprobado",
            "cae": resultado["cae"],
            "vto_cae": resultado["vto_cae"],
            "numero": resultado["nro_comprobante"],
            "fecha": resultado["fecha"],
            "total": resultado["total"],
            "forma_pago": resultado["forma_pago"],
            "productos": resultado["productos"]
        }

    except Exception as e:
        return {"estado": "rechazado", "error": str(e)}
