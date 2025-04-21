from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Factura(BaseModel):
    cuit: str
    total: float
    productos: list
    forma_pago: str

@app.get("/")
def home():
    return {"mensaje": "Backend de AFIP activo"}

@app.post("/facturar")
def facturar(factura: Factura):
    # Por ahora simulamos: después conectamos con AFIP
    return {
        "estado": "simulado",
        "cae": "12345678901234",
        "vto_cae": "2025-05-01",
        "total": factura.total
    }