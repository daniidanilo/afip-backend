import os
from datetime import datetime
from zeep import Client
from zeep.transports import Transport

# Certificados
CERT = "afip_cert/afip.crt"
KEY = "afip_cert/afip.key"
CUIT_EMISOR = "20352305368"  # Reemplazalo con tu CUIT real

# WSDL y endpoint de homologación
WSDL_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
WSDL_WSFE = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

# Para simplificar: leer CMS generado localmente
def obtener_token_sign():
    # Acá deberías implementar el pedido real al WSAA usando xmlsec o cargar un CMS ya generado (como prueba)
    raise NotImplementedError("Falta implementar WSAA: generación de CMS y parseo de respuesta")

def emitir_factura(productos: list, total: float, forma_pago: str):
    token, sign = obtener_token_sign()

    client = Client(wsdl=WSDL_WSFE, transport=Transport(timeout=10))
    client.service.__setattr__('CUIT', CUIT_EMISOR)

    punto_venta = 1
    tipo_cbte = 11
    fecha = datetime.today().strftime("%Y%m%d")

    # Obtener último número
    ultimo_nro = client.service.FECompUltimoAutorizado(CUIT_EMISOR, punto_venta, tipo_cbte)["CbteNro"]

    datos = {
        "FeCAEReq": {
            "FeCabReq": {
                "CantReg": 1,
                "PtoVta": punto_venta,
                "CbteTipo": tipo_cbte,
            },
            "FeDetReq": {
                "FECAEDetRequest": [{
                    "Concepto": 1,
                    "DocTipo": 99,
                    "DocNro": 0,
                    "CbteDesde": ultimo_nro + 1,
                    "CbteHasta": ultimo_nro + 1,
                    "CbteFch": fecha,
                    "ImpTotal": total,
                    "ImpNeto": total,
                    "ImpIVA": 0.00,
                    "ImpTrib": 0.00,
                    "MonId": "PES",
                    "MonCotiz": 1.0
                }]
            }
        }
    }

    respuesta = client.service.FECAESolicitar(Auth={"Token": token, "Sign": sign, "Cuit": CUIT_EMISOR}, FeCAEReq=datos)

    cae = respuesta.FeDetResp.FECAEDetResponse[0].CAE
    vto = respuesta.FeDetResp.FECAEDetResponse[0].CAEFchVto

    return {
        "cae": cae,
        "vto_cae": vto,
        "nro_comprobante": ultimo_nro + 1,
        "fecha": fecha,
        "total": total,
        "forma_pago": forma_pago,
        "productos": productos
    }