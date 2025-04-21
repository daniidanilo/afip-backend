import base64
import datetime
import uuid
import subprocess
import os
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

# ======================
# 2. CONFIGURACIÓN AFIP
# ======================
CERT_PATH = "afip_cert/afip.crt"
KEY_PATH = "afip_cert/afip.key"
WSDL_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
SERVICE = "wsfe"

# ============================
# 3. CREACIÓN DEL TICKET XML
# ============================
def crear_login_ticket_request(filename="loginTicketRequest.xml"):
    unique_id = str(uuid.uuid4().int)[:10]
    generation_time = (datetime.datetime.now() - datetime.timedelta(minutes=10)).isoformat()
    expiration_time = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()

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
# 4. FIRMA DEL XML CON OPENSSL
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
# 5. CONSUMO DEL SERVICIO WSAA AFIP
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
