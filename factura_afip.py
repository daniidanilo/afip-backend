import base64
import os
import uuid
import subprocess
from datetime import datetime, timedelta, timezone
from lxml import etree
from zeep import Client

# =======================
# 1. CONFIGURACIÓN GLOBAL
# =======================
CERT_PATH = "afip_cert/afip.crt"
KEY_PATH = "afip_cert/afip.key"
WSDL_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
WSDL_WSFE = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
CUIT_EMISOR = "20352305368"  # Reemplazá con tu CUIT
SERVICE = "wsfe"
TA_CACHE_PATH = "afip_cert/token_cache.xml"

# ==========================
# 2. FUNCIÓN PARA OBTENER TA
# ==========================
def crear_login_ticket_request(filename="loginTicketRequest.xml"):
    unique_id = str(uuid.uuid4().int)[:10]
    now = datetime.now(timezone.utc) - timedelta(hours=3)
    generation_time = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    expiration_time = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")

    root = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(root, "header")
    etree.SubElement(header, "uniqueId").text = unique_id
    etree.SubElement(header, "generationTime").text = generation_time
    etree.SubElement(header, "expirationTime").text = expiration_time
    etree.SubElement(root, "service").text = SERVICE

    tree = etree.ElementTree(root)
    tree.write(filename, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return filename

def firmar_ticket(xml_path, cms_path):
    subprocess.run([
        "openssl", "smime", "-sign",
        "-signer", CERT_PATH,
        "-inkey", KEY_PATH,
        "-in", xml_path,
        "-out", cms_path,
        "-outform", "DER",
        "-nodetach"
    ], check=True)

def obtener_token_y_sign():
    # Si el token está cacheado y no vencido, lo usamos
    if os.path.exists(TA_CACHE_PATH):
        try:
            with open(TA_CACHE_PATH, "r", encoding="utf-8") as f:
                ta_xml = etree.parse(f)
                expiration = ta_xml.findtext(".//expirationTime")
                if expiration and datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%S") > datetime.now():
                    token = ta_xml.findtext(".//token")
                    sign = ta_xml.findtext(".//sign")
                    return token, sign
        except Exception:
            pass  # Si falla el parseo o lo que sea, seguimos y pedimos nuevo

    # Si no hay token válido, lo generamos
    xml_path = "loginTicketRequest.xml"
    cms_path = "loginTicketRequest.cms"

    crear_login_ticket_request(xml_path)
    firmar_ticket(xml_path, cms_path)

    with open(cms_path, "rb") as f:
        cms_base64 = base64.b64encode(f.read()).decode()

    client = Client(wsdl=WSDL_WSAA)
    response = client.service.loginCms(cms_base64)

    with open(TA_CACHE_PATH, "w", encoding="utf-8") as f:
        f.write(response)  # Cacheamos el XML entero

    token_xml = etree.fromstring(response.encode())
    token = token_xml.findtext(".//token")
    sign = token_xml.findtext(".//sign")

    return token, sign

# ========================================
# 3. FUNCIÓN PARA EMITIR FACTURA TIPO C
# ========================================
def emitir_factura(productos, total, forma_pago):
    try:
        token, sign = obtener_token_y_sign()
        client = Client(wsdl=WSDL_WSFE)
        service = client.service

        punto_venta = 1
        tipo_cbte = 11  # Factura C

        ultimo = service.FECompUltimoAutorizado(
            Auth={"Token": token, "Sign": sign, "Cuit": CUIT_EMISOR},
            PtoVta=punto_venta,
            CbteTipo=tipo_cbte
        )

        nuevo_nro = ultimo.CbteNro + 1
        hoy = datetime.now().strftime("%Y%m%d")

        data = {
            "Auth": {"Token": token, "Sign": sign, "Cuit": CUIT_EMISOR},
            "FeCAEReq": {
                "FeCabReq": {
                    "CantReg": 1,
                    "PtoVta": punto_venta,
                    "CbteTipo": tipo_cbte
                },
                "FeDetReq": {
                    "FECAEDetRequest": [ {
                        "Concepto": 1,
                        "DocTipo": 99,
                        "DocNro": 0,
                        "CbteDesde": nuevo_nro,
                        "CbteHasta": nuevo_nro,
                        "CbteFch": hoy,
                        "ImpTotal": total,
                        "ImpNeto": total,
                        "ImpIVA": 0.0,
                        "ImpTrib": 0.0,
                        "MonId": "PES",
                        "MonCotiz": 1.0
                    }]
                }
            }
        }

        response = service.FECAESolicitar(**data)
        resultado = response.FeDetResp.FECAEDetResponse[0]

        if resultado.Resultado == "A":
            return {
                "cae": resultado.CAE,
                "vto_cae": resultado.CAEFchVto,
                "nro_comprobante": nuevo_nro,
                "fecha": hoy,
                "total": total,
                "forma_pago": forma_pago,
                "productos": productos
            }
        else:
            errores = response.Errors or resultado.Observaciones
            raise Exception(str(errores))

    except Exception as e:
        raise Exception(f"Error en emitir_factura: {str(e)}")
