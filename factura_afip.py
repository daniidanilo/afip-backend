import os
from afipws.wsaa import WSAA
from afipws.wsfev1 import WSFEv1
from datetime import datetime

# Paths a los archivos
CERT = "afip_cert/afip.crt"
KEY = "afip_cert/afip.key"
CUIT_EMISOR = "20352305368"  # Reemplazá con tu CUIT

# Endpoint del entorno de homologación
WSDL_WSFE = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

def emitir_factura(productos: list, total: float, forma_pago: str):
    # 1. Obtener token y sign con WSAA
    wsaa = WSAA()
    ta = wsaa.Autenticar(
        servicio="wsfe",
        cert=CERT,
        key=KEY,
        wsdl="https://wsaa.afip.gov.ar/wsaa/wsaa.wsdl",
        cache=False
    )
    token = ta["token"]
    sign = ta["sign"]

    # 2. Iniciar conexión con WSFEv1
    wsfe = WSFEv1(CUIT_EMISOR)
    wsfe.SetTicketAcceso(token, sign)

    # 3. Obtener el último comprobante autorizado
    punto_venta = 1
    tipo_cbte = 11  # Factura C
    ultimo = wsfe.CompUltimoAutorizado(punto_venta, tipo_cbte)
    nro_cbte = ultimo + 1

    # 4. Armar y emitir comprobante
    fecha = datetime.today().strftime("%Y%m%d")
    resultado = wsfe.CrearFactura(
        concepto=1,  # Productos
        doc_tipo=99,  # Consumidor final
        doc_nro=0,
        cbte_nro=nro_cbte,
        cbte_tipo=tipo_cbte,
        cbte_punto=punto_venta,
        cbte_fecha=fecha,
        imp_total=total,
        imp_tot_conc=0.00,
        imp_neto=total,
        imp_iva=0.00,
        imp_trib=0.00,
        moneda_id="PES",
        moneda_ctz=1.000
    )

    if resultado["Resultado"] == "A":
        return {
            "cae": resultado["CAE"],
            "vto_cae": resultado["CAEFchVto"],
            "nro_comprobante": nro_cbte,
            "fecha": fecha,
            "total": total,
            "forma_pago": forma_pago,
            "productos": productos
        }
    else:
        raise Exception("Factura rechazada: " + str(resultado["Observaciones"]))