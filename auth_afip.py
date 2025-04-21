import os
import base64
import uuid
import datetime
import subprocess
from lxml import etree
from zeep import Client

CERT_PATH = "afip_cert/afip.crt"
KEY_PATH = "afip_cert/afip.key"
WSDL_WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"
SERVICE = "wsfe"

def crear_login_ticket_request():
    unique_id = str(uuid.uuid4().int)[:10]
    generation_time = (datetime.datetime.now() - datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    expiration_time = (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")

    root = etree.Element("loginTicketRequest", version="1.0")
    header = etree.SubElement(root, "header")
    etree.SubElement(header, "uniqueId").text = unique_id
    etree.SubElement(header, "generationTime").text = generation_time
    etree.SubElement(header, "expirationTime").text = expiration_time
    etree.SubElement(root, "service").text = SERVICE

    xml_path = "loginTicketRequest.xml"
    tree = etree.ElementTree(root)
    tree.write(xml_path, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return xml_path

def firmar_con_openssl(xml_path):
    signed_path = "loginTicketRequest.cms"
    subprocess.run([
        "openssl", "smime", "-sign",
        "-signer", CERT_PATH,
        "-inkey", KEY_PATH,
        "-in", xml_path,
        "-out", signed_path,
        "-outform", "DER",
        "-nodetach"
    ], check=True)
    return signed_path

def obtener_token_y_sign():
    xml_path = crear_login_ticket_request()
    cms_path = firmar_con_openssl(xml_path)

    with open(cms_path, "rb") as f:
        cms_der = f.read()

    cms_base64 = base64.b64encode(cms_der).decode()

    client = Client(wsdl=WSDL_WSAA)
    response = client.service.loginCms(cms_base64)

    token_xml = etree.fromstring(response.encode())
    token = token_xml.findtext(".//token")
    sign = token_xml.findtext(".//sign")

    return token, sign