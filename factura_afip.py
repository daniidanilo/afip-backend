import os
from datetime import datetime
from zeep import Client
from auth_afip import obtener_token_y_sign

# Configuración
CUIT_EMISOR = "20352305368"  # Reemplazar por tu CUIT
WSDL_WSFE = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

def emitir_factura(productos: list, total: float, forma_pago: str):
    # Obtener Token y Sign desde WSAA
    token, sign = obtener_token_y_sign()

    # Inicializar cliente WSFE
    client = Client(wsdl=WSDL_WSFE)
    service = client.service
    auth = {
        "Token": token,
        "Sign": sign,
        "Cuit": int(CUIT_EMISOR)
    }

    # Obtener último comprobante autorizado
    punto_venta = 1
    tipo_cbte = 11  # Factura C
    ultimo_cbte = service.FECompUltimoAutorizado(auth, punto_venta, tipo_cbte).CbteNro
    nro_cbte = ultimo_cbte + 1

    # Crear el cuerpo del comprobante
    fecha = datetime.now().strftime("%Y%m%d")
    detalle = {
        "Concepto": 1,
        "DocTipo": 99,
        "DocNro": 0,
        "CbteDesde": nro_cbte,
        "CbteHasta": nro_cbte,
        "CbteFch": fecha,
        "ImpTotal": total,
        "ImpTotConc": 0.00,
        "ImpNeto": total,
        "ImpIVA": 0.00,
        "ImpTrib": 0.00,
        "MonId": "PES",
        "MonCotiz": 1.0
    }

    req = {
        "FeCAEReq": {
            "FeCabReq": {
                "CantReg": 1,
                "PtoVta": punto_venta,
                "CbteTipo": tipo_cbte
            },
            "FeDetReq": {
                "FECAEDetRequest": [detalle]
            }
        }
    }

    # Enviar solicitud
    respuesta = service.FECAESolicitar(auth, **req)

    # Procesar respuesta
    resultado = respuesta.FeDetResp.FECAEDetResponse[0]

    if resultado.Resultado == "A":
        return {
            "cae": resultado.CAE,
            "vto_cae": resultado.CAEFchVto,
            "nro_comprobante": nro_cbte,
            "fecha": fecha,
            "total": total,
            "forma_pago": forma_pago,
            "productos": productos
        }
    else:
        obs = resultado.Observaciones.Obs if resultado.Observaciones else []
        errores = [o.Msg for o in obs]
        raise Exception("Factura rechazada: " + ", ".join(errores))