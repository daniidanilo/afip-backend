import datetime
from zeep import Client
from auth_afip import obtener_token_y_sign

# ======================
# CONFIGURACIÓN DE AFIP
# ======================
CUIT_EMISOR = "20352305368"  # Reemplazá con tu CUIT real
WSDL_WSFE = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

# ====================================
# FUNCIÓN PARA EMITIR FACTURA ELECTRÓNICA
# ====================================
def emitir_factura(productos, total, forma_pago):
    try:
        token, sign = obtener_token_y_sign()

        # Crear cliente SOAP para WSFE
        client = Client(wsdl=WSDL_WSFE)
        service = client.service

        # Autenticación
        auth = {
            "Token": token,
            "Sign": sign,
            "Cuit": int(CUIT_EMISOR)
        }

        # Obtener último comprobante autorizado
        punto_venta = 1
        tipo_cbte = 11  # Factura C
        ultimo_cbte = service.FECompUltimoAutorizado(auth, punto_venta, tipo_cbte)
        nro_cbte = ultimo_cbte['CbteNro'] + 1

        # Fecha de hoy en formato AAAAMMDD
        fecha_hoy = datetime.datetime.now().strftime("%Y%m%d")

        # Armar el detalle de la factura
        detalle = {
            "Concepto": 1,         # 1 = Productos
            "DocTipo": 99,        # 99 = Consumidor final
            "DocNro": 0,
            "CbteDesde": nro_cbte,
            "CbteHasta": nro_cbte,
            "CbteFch": fecha_hoy,
            "ImpTotal": total,
            "ImpTotConc": 0.0,
            "ImpNeto": total,
            "ImpIVA": 0.0,
            "ImpTrib": 0.0,
            "MonId": "PES",
            "MonCotiz": 1.0
        }

        # Armar la solicitud completa
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

        # Llamar al servicio para autorizar la factura
        respuesta = service.FECAESolicitar(auth, req["FeCAEReq"])
        resultado = respuesta.FeDetResp.FECAEDetResponse[0]

        if resultado.Resultado == "A":
            return {
                "cae": resultado.CAE,
                "vto_cae": resultado.CAEFchVto,
                "nro_comprobante": nro_cbte,
                "fecha": fecha_hoy,
                "total": total,
                "forma_pago": forma_pago,
                "productos": productos
            }
        else:
            errores = resultado.Observaciones.Obs if resultado.Observaciones else "Sin detalles"
            raise Exception(f"Factura rechazada: {errores}")

    except Exception as e:
        raise Exception(f"Error en emitir_factura: {str(e)}")
