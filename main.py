from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from factura_afip import emitir_factura
from datetime import datetime, timezone, timedelta

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

# Endpoint para obtener la hora actual del servidor
@app.get("/hora-servidor")
def hora_servidor():
    now_utc = datetime.now(timezone.utc)
    now_arg = now_utc.astimezone(timezone(timedelta(hours=-3)))
    return {
        "utc": now_utc.isoformat(),
        "argentina": now_arg.isoformat()
    }

# Endpoint de facturación
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
        return {"estado": "rechazado", "error": f"Error en emitir_factura: {str(e)}"}
