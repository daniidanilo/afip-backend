import base64
import uuid
import os
import subprocess
from datetime import datetime, timedelta, timezone
from lxml import etree
from zeep import Client

# =======================
# CONFIGURACIÓN GENERAL
# =======================
CERT_PATH = "afip_cert/afip.crt"
KEY_PATH = "afip_cert/afip.key"
WSDL_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
SERVICE = "wsfe"
TA_CACHE_PATH = "ta.xml"

# =======================
# UTILIDADES DE TIEMPO
# =======================
def obtener_tiempos_afip():
    now = datetime.now(timezone.utc) - timedelta(hours=3)  # Hora Argentina sin zona horaria
    generation_time = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    expiration_time = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    return generation_time, expiration_time

# ============================
# CREACIÓN Y FIRMA DEL XML CMS
# ============================
def crear_login_ticket_request(filename="loginTicketRequest.xml"):
    unique_id = str(uuid.uuid4().int)[:10]
    generation_time, expiration_time = obtener_tiempos_afip()

    root = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(root, "header")
    etree.SubElement(header, "uniqueId").text = unique_id
    etree.SubElement(header, "generationTime").text = generation_time
    etree.SubElement(header, "expirationTime").text = expiration_time
    etree.SubElement(root, "service").text = SERVICE

    tree = etree.ElementTree(root)
    tree.write(filename, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return filename

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

# ============================
# CACHE DE TOKEN Y SIGN
# ============================
def ta_valido():
    if not os.path.exists(TA_CACHE_PATH):
        return False
    try:
        tree = etree.parse(TA_CACHE_PATH)
        expiration_time = tree.findtext("//expirationTime")
        expiration = datetime.strptime(expiration_time, "%Y-%m-%dT%H:%M:%S")
        return expiration > datetime.now()
    except Exception:
        return False

def guardar_ta(xml_str):
    with open(TA_CACHE_PATH, "w", encoding="utf-8") as f:
        f.write(xml_str)

def leer_ta():
    tree = etree.parse(TA_CACHE_PATH)
    token = tree.findtext("//token")
    sign = tree.findtext("//sign")
    return token, sign

# ============================
# OBTENER TOKEN Y SIGN
# ============================
def obtener_token_y_sign():
    if ta_valido():
        return leer_ta()

    xml_path = "loginTicketRequest.xml"
    cms_path = "loginTicketRequest.cms"

    crear_login_ticket_request(xml_path)
    firmar_ticket_con_openssl(xml_path, cms_path)

    with open(cms_path, "rb") as f:
        cms_base64 = base64.b64encode(f.read()).decode()

    client = Client(wsdl=WSDL_WSAA)
    response = client.service.loginCms(cms_base64)

    guardar_ta(response)

    token_xml = etree.fromstring(response.encode())
    token = token_xml.findtext("//token")
    sign = token_xml.findtext("//sign")

    return token, sign
