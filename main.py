from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from factura_afip import emitir_factura

app = FastAPI()

# Modelos de datos que recibimos desde la app
class Producto(BaseModel):
    nombre: str
    precio: float

class Venta(BaseModel):
    productos: List[Producto]
    total: float
    forma_pago: str

@app.get("/")
def home():
    return {"mensaje": "Backend de AFIP activo y esperando facturas"}

@app.post("/facturar")
def facturar(venta: Venta):
    try:
        # Convertimos productos a tuplas para pasarlos al módulo
        lista_productos = [(p.nombre, p.precio) for p in venta.productos]

        resultado = emitir_factura(
            productos=lista_productos,
            total=venta.total,
            forma_pago=venta.forma_pago
        )

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
        return {
            "estado": "rechazado",
            "error": str(e)
        }
