from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from factura_afip import emitir_factura, obtener_tiempos_afip

app = FastAPI()

# Modelo de datos que recibimos desde la app
class Producto(BaseModel):
    nombre: str
    precio: float

class Venta(BaseModel):
    productos: List[Producto]
    total: float
    forma_pago: str

@app.get("/")
def home():
    return {"mensaje": "Backend de AFIP activo"}

@app.post("/facturar")
def facturar(venta: Venta):
    try:
        lista_productos = [(p.nombre, p.precio) for p in venta.productos]
        resultado = emitir_factura(
            productos=lista_productos,
            total=venta.total,
            forma_pago=venta.forma_pago
        )
        return {
            "estado": "aprobado",
            **resultado
        }

    except Exception as e:
        # Obtener los tiempos para debug
        tiempos = obtener_tiempos_afip()
        return {
            "estado": "rechazado",
            "error": f"Error en emitir_factura: {str(e)}",
            **tiempos
        }