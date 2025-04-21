import base64
import datetime
import uuid
import subprocess
import os
import requests
from lxml import etree
from zeep import Client

# =======================
# 1. GUARDAR CERTIFICADOS
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

# Ejecutamos esto al importar el archivo
guardar_certificados()

# =========================
# 2. CONFIGURACIÓN GENERAL
# =========================
CERT_PATH = "afip_cert/afip.crt"
KEY_PATH = "afip_cert/afip.key"
WSDL_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
SERVICE = "wsfe"

# =============================================
# 3. OBTENER HORA EXACTA DESDE UN SERVIDOR WEB
# =============================================
def obtener_hora_desde_afip():
    try:
        r = requests.get("https://www.afip.gob.ar", timeout=5)
        date_str = r.headers['Date']  # Formato: 'Mon, 21 Apr 2025 03:26:53 GMT'
        date_dt = datetime.datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S GMT')
        return date_dt.replace(tzinfo=datetime.timezone.utc)
    except Exception as e:
        raise Exception("No se pudo obtener la hora desde AFIP: " + str(e))

# ============================
# 4. CREAR XML DEL LOGIN TICKET
# ============================
def crear_login_ticket_request(filename="loginTicketRequest.xml"):
    now = obtener_hora_desde_afip()
    generation_time = (now - datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    expiration_time = (now + datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")

    unique_id = str(uuid.uuid4().int)[:10]
    root = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(root, "header")
    etree.SubElement(header, "uniqueId").text = unique_id
    etree.SubElement(header, "generationTime").text = generation_time
    etree.SubElement(header, "expirationTime").text = expiration_time
    etree.SubElement(root, "service").text = SERVICE

    tree = etree.ElementTree(root)
    tree.write(filename, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return filename

# ==============================
# 5. FIRMAR EL XML CON OPENSSL
# ==============================
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

# ===================================
# 6. OBTENER TOKEN Y SIGN DEL WSAA
# ===================================
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
