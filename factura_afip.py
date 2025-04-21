import base64
import os
import uuid
import subprocess
from datetime import datetime, timedelta, timezone
from lxml import etree
from zeep import Client

# =======================
# 0. RECONSTRUIR CERTIFICADOS
# =======================
def restaurar_certificados():
    cert_b64 = os.getenv("AFIP_CERT_B64")
    key_b64 = os.getenv("AFIP_KEY_B64")

    print(f"[DEBUG] Certificado presente: {bool(cert_b64)}")
    print(f"[DEBUG] Key presente: {bool(key_b64)}")

    if not cert_b64 or not key_b64:
        raise Exception("Certificados no encontrados en variables de entorno.")

    os.makedirs("afip_cert", exist_ok=True)

    with open("afip_cert/afip.crt", "wb") as f:
        f.write(base64.b64decode(cert_b64))

    with open("afip_cert/afip.key", "wb") as f:
        f.write(base64.b64decode(key_b64))

restaurar_certificados()

# =======================
# 1. CONFIGURACIÓN GLOBAL
# =======================
CERT_PATH = "afip_cert/afip.crt"
KEY_PATH = "afip_cert/afip.key"
WSDL_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
WSDL_WSFE = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
CUIT_EMISOR = "20352305368"  # Reemplazá con tu CUIT
SERVICE = "wsfe"
TA_FILE = "/tmp/token_afip.xml"

# ==============================
# 2. AUTENTICACIÓN (WSAA + CACHE)
# ==============================
def crear_login_ticket_request(filename="/tmp/loginTicketRequest.xml"):
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
    try:
        subprocess.run([
            "openssl", "smime", "-sign",
            "-signer", CERT_PATH,
            "-inkey", KEY_PATH,
            "-in", xml_path,
            "-out", cms_path,
            "-outform", "DER",
            "-nodetach"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print("[ERROR] Falló la firma del ticket con OpenSSL:", e)
        raise

def ta_valido():
    if not os.path.exists(TA_FILE):
        print("[INFO] TA no encontrado, se generará uno nuevo.")
        return False
    try:
        tree = etree.parse(TA_FILE)
        expiration = tree.findtext("//expirationTime")
        expiration_dt = datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%S")
        return datetime.now() < expiration_dt
    except Exception as e:
        print("[ERROR] Fallo al leer el TA:", e)
        return False

def leer_ta():
    tree = etree.parse(TA_FILE)
    token = tree.findtext("//token")
    sign = tree.findtext("//sign")
    return token, sign

def guardar_ta(xml):
    with open(TA_FILE, "w") as f:
        f.write(xml)

def obtener_token_y_sign():
    if ta_valido():
        print("[INFO] Usando TA en caché.")
        return leer_ta()

    xml_path = "/tmp/loginTicketRequest.xml"
    cms_path = "/tmp/loginTicketRequest.cms"

    crear_login_ticket_request(xml_path)
    firmar_ticket(xml_path, cms_path)

    with open(cms_path, "rb") as f:
        cms_base64 = base64.b64encode(f.read()).decode()

    client = Client(wsdl=WSDL_WSAA)

    try:
        response = client.service.loginCms(cms_base64)
        guardar_ta(response)

    except Exception as e:
        if "TA valido" in str(e):
            if os.path.exists(TA_FILE):
                print("[INFO] TA válido detectado y existe en el sistema. Usando TA en caché.")
                return leer_ta()
            else:
                print("[ERROR] TA válido en AFIP pero no encontrado en local. No se puede continuar.")
                raise Exception("TA válido en AFIP pero no encontrado en local")
        else:
            raise

    token_xml = etree.fromstring(response.encode())
    token = token_xml.findtext("//token")
    sign = token_xml.findtext("//sign")
    return token, sign

# ============================================
# 3. EMISIÓN DE FACTURA C CON WSFEv1 (CAE real)
# ============================================
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
                    "FECAEDetRequest": [{
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