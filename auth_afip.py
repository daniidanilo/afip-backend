import base64
import datetime
import uuid
import subprocess
import os
from lxml import etree
from zeep import Client
from datetime import datetime, timezone, timedelta
from lxml import etree  # Asegúrate de tener instalada esta librería

# ==========================
# 1. FUNCIONES DE DIAGNÓSTICO
# ==========================
def obtener_tiempos_afip():
    # ⚠️ Ajustamos 3 horas hacia atrás (hora argentina)
    now = datetime.now(timezone.utc) - timedelta(hours=3)
    generation_time = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    expiration_time = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "generationTime": generation_time,
        "expirationTime": expiration_time,
        "serverTimeUTC": (now + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S"),
        "serverTimeLocal": now.strftime("%Y-%m-%d %H:%M:%S")
    }

# =======================
# 2. GUARDAR CERTIFICADOS
# =======================
def guardar_certificados():
    cert_b64 = os.getenv("AFIP_CERT_B64")
    key_b64 = os.getenv("AFIP_KEY_B64")

    if not cert_b64 or not key_b64:
        raise Exception("Certificados no encontrados en variables de entorno.")

    os.makedirs("afip_cert", exist_ok=True)

    with open("afip_cert/afip.crt", "wb") as cert_file:
        cert_file.write(base64.b64decode(cert_b64))

    with open("afip_cert/afip.key", "wb") as key_file:
        key_file.write(base64.b64decode(key_b64))

# Ejecutamos al importar
guardar_certificados()

# ======================
# 3. CONFIGURACIÓN AFIP
# ======================
CERT_PATH = "afip_cert/afip.crt"
KEY_PATH = "afip_cert/afip.key"
WSDL_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
SERVICE = "wsfe"

# =============================
# 4. CREACIÓN DEL XML DEL TICKET
# =============================

def crear_login_ticket_request(filename="loginTicketRequest.xml"):
    unique_id = str(uuid.uuid4().int)[:10]

    # AFIP espera la hora local de Argentina (UTC-3)
    now_utc_minus_3 = datetime.utcnow() - timedelta(hours=3)
    generation_time = (now_utc_minus_3 - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    expiration_time = (now_utc_minus_3 + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")

    root = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(root, "header")
    etree.SubElement(header, "uniqueId").text = unique_id
    etree.SubElement(header, "generationTime").text = generation_time
    etree.SubElement(header, "expirationTime").text = expiration_time
    etree.SubElement(root, "service").text = SERVICE

    tree = etree.ElementTree(root)
    tree.write(filename, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return filename


# =============================
# 5. FIRMA DEL XML CON OPENSSL
# =============================
def firmar_ticket_con_openssl(xml_path, cms_path):
    subprocess.run([
        "openssl", "smime", "-sign",
        "-signer", CERT_PATH,
        "-inkey", KEY_PATH,
        "-in", xml_path,
        "-out", cms_path,
        "-outform", "DER",
        "-nodetach"
    ], check=True)

# ==================================
# 6. CONSUMO DEL SERVICIO WSAA AFIP
# ==================================
def obtener_token_y_sign():
    xml_path = "loginTicketRequest.xml"
    cms_path = "loginTicketRequest.cms"

    crear_login_ticket_request(xml_path)
    firmar_ticket_con_openssl(xml_path, cms_path)

    with open(cms_path, "rb") as f:
        cms_base64 = base64.b64encode(f.read()).decode()

    client = Client(wsdl=WSDL_WSAA)
    response = client.service.loginCms(cms_base64)

    token_xml = etree.fromstring(response.encode())
    token = token_xml.findtext("//token")
    sign = token_xml.findtext("//sign")

    return token, sign

# =================================
# 7. FUNCIÓN DE FACTURACIÓN SIMULADA
# =================================
def emitir_factura(productos, total, forma_pago):
    try:
        token, sign = obtener_token_y_sign()

        return {
            "cae": "12345678901234",
            "vto_cae": "20250430",
            "nro_comprobante": 1,
            "fecha": datetime.now().strftime("%Y%m%d"),
            "total": total,
            "forma_pago": forma_pago,
            "productos": productos
        }

    except Exception as e:
        raise Exception(f"Error en emitir_factura: {str(e)}")
