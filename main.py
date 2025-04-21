from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from factura_afip import emitir_factura
from fastapi.responses import PlainTextResponse
import os

app = FastAPI()

# ============================
# MODELOS DE DATOS RECIBIDOS
# ============================
class Producto(BaseModel):
    nombre: str
    precio: float

class Venta(BaseModel):
    productos: List[Producto]
    total: float
    forma_pago: str

@app.get("/")
def home():
    return {"mensaje": "Backend de AFIP activo y listo para facturar"}

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
            "error": f"Error en emitir_factura: {str(e)}"
        }

# ========================================
# ENDPOINT DE DIAGNÓSTICO PARA TOKEN CACHE
# ========================================
@app.get("/diagnostico_ta", response_class=PlainTextResponse)
def diagnostico_ta():
    if not os.path.exists("token_afip.xml"):
        return "No existe el archivo token_afip.xml"

    with open("token_afip.xml", "r") as f:
        contenido = f.read()
    return contenido