from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from factura_afip import emitir_factura
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

# ============================
# ENDPOINT DE VERIFICACIÓN
# ============================
@app.get("/cert-status")
def cert_status():
    return {
        "crt_encontrado": os.path.exists("afip_cert/afip.crt"),
        "key_encontrado": os.path.exists("afip_cert/afip.key")
    }