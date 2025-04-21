import base64
import datetime
import uuid
import subprocess
import os
from lxml import etree
from zeep import Client
import os
# ...
BASE_DIR = os.path.dirname(__file__)
CMS_FILE = os.path.join(BASE_DIR, "requests", "loginCMS.xml")
CMS_SIGNED = os.path.join(BASE_DIR, "requests", "loginCMS_signed.xml")


# Configuración de certificados
CERT_PATH = "afip_cert/afip.crt"
KEY_PATH = "afip_cert/afip.key"
WSDL_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
SERVICE = "wsfe"

# Archivo temporal
CMS_FILE = "/tmp/loginCMS.xml"
CMS_SIGNED = "/tmp/loginCMS_signed.xml"


def crear_login_ticket_request():
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
    tree.write(CMS_FILE, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def firmar_login_ticket_request():
    cmd = [
        "xmlsec1",
        "--sign",
        "--output", CMS_SIGNED,
        "--pkcs12", KEY_PATH,
        "--pwd", "",
        CMS_FILE
    ]
    subprocess.run(cmd, check=True)


def obtener_token_y_sign():
    crear_login_ticket_request()

    # Firmamos usando xmlsec (puede variar dependiendo si usas PEM o PKCS12)
    # Alternativamente, usá openssl smime si no tenés xmlsec1
    with open(CMS_FILE, 'rb') as f:
        cms_raw = f.read()

    # Firmamos con openssl (si no tenés xmlsec1 instalado)
    signed_cms_path = "/tmp/loginCMS.signed"
    subprocess.run([
        "openssl", "smime", "-sign",
        "-signer", CERT_PATH,
        "-inkey", KEY_PATH,
        "-outform", "DER",
        "-nodetach",
        "-in", CMS_FILE,
        "-out", signed_cms_path
    ], check=True)

    with open(signed_cms_path, 'rb') as f:
        cms_signed = f.read()

    cms_base64 = base64.b64encode(cms_signed).decode()

    # Consumir WSAA
    client = Client(wsdl=WSDL_WSAA)
    response = client.service.loginCms(cms_base64)

    token_xml = etree.fromstring(response.encode())
    token = token_xml.findtext("//token")
    sign = token_xml.findtext("//sign")

    return token, sign
