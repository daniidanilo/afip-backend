import os
import base64
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from factura_afip import emitir_factura

app = FastAPI()

# ===============================
# BLOQUE DIAGNÓSTICO (TEMPORAL)
# ===============================
try:
    cert_b64 = os.getenv("AFIP_CERT_B64")
    key_b64 = os.getenv("AFIP_KEY_B64")

    if cert_b64 and key_b64:
        os.makedirs("afip_cert", exist_ok=True)
        with open("afip_cert/afip.crt", "wb") as f:
            f.write(base64.b64decode(cert_b64))
        with open("afip_cert/afip.key", "wb") as f:
            f.write(base64.b64decode(key_b64))
        print("✅ Certificados escritos con éxito.")
    else:
        print("⚠️ Variables de entorno no encontradas.")
except Exception as e:
    print(f"❌ Error al escribir certificados: {str(e)}")

# ===============================
# MODELOS DE DATOS
# ===============================
class Producto(BaseModel):
    nombre: str
    precio: float

class Venta(BaseModel):
    productos: List[Producto]
    total: float
    forma_pago: str

# ===============================
# ENDPOINTS
# ===============================
@app.get("/")
def home():
    return {"mensaje": "Backend de AFIP activo y listo para facturar"}

@app.get("/cert-status")
def verificar_certificados():
    cert_ok = os.path.isfile("afip_cert/afip.crt")
    key_ok = os.path.isfile("afip_cert/afip.key")
    return {
        "crt_encontrado": cert_ok,
        "key_encontrado": key_ok
    }

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