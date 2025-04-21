import base64
import datetime
import uuid
import subprocess
import os
import requests
from lxml import etree
from zeep import Client

# =======================
# COMENTARIO: Este archivo sincroniza la hora con el servidor de AFIP
# para evitar el error: "generationTime posee formato o dato inválido"
# que ocurre cuando el servidor Render tiene un desfase horario.
# =======================

# 1. GUARDAR CERTIFICADOS DESDE VARIABLES DE ENTORNO

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

# 2. CONFIGURACIÓN DE RUTAS Y DATOS
CERT_PATH = "afip_cert/afip.crt"
KEY_PATH = "afip_cert/afip.key"
WSDL_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
SERVICE = "wsfe"

# 3. OBTENER HORA DESDE AFIP

def obtener_hora_afip():
    try:
        r = requests.get("https://time.afip.gov.ar")
        if r.status_code == 200:
            hora_afip = r.json().get("serverTime")
            return datetime.datetime.fromisoformat(hora_afip)
        else:
            raise Exception("No se pudo obtener la hora de AFIP")
    except Exception as e:
        raise Exception(f"Error al sincronizar con AFIP: {e}")

# 4. CREAR TICKET LOGIN XML

def crear_login_ticket_request(filename="loginTicketRequest.xml"):
    unique_id = str(uuid.uuid4().int)[:10]

    now = obtener_hora_afip()
    generation_time = (now - datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    expiration_time = (now + datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")

    root = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(root, "header")
    etree.SubElement(header, "uniqueId").text = unique_id
    etree.SubElement(header, "generationTime").text = generation_time
    etree.SubElement(header, "expirationTime").text = expiration_time
    etree.SubElement(root, "service").text = SERVICE

    tree = etree.ElementTree(root)
    tree.write(filename, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return filename

# 5. FIRMAR XML CON OPENSSL

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

# 6. OBTENER TOKEN Y SIGN

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
