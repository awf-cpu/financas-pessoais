"""Testes dos importadores CSV/OFX e do parser de valores."""
from datetime import date

from app.providers.fileimport import _parse_amount, import_csv, import_ofx


def test_parse_amount_br():
    assert _parse_amount("1.234,56") == 1234.56
    assert _parse_amount("R$ -1.234,56") == -1234.56
    assert _parse_amount("(123,45)") == -123.45
    assert _parse_amount("89,90") == 89.90
    assert _parse_amount("1000.00") == 1000.00


def test_import_csv_virgula_decimal_e_ponto_e_virgula():
    csv_bytes = (
        "Data;Descrição;Valor\n"
        "05/11/2025;IFOOD RESTAURANTE;-45,90\n"
        "06/11/2025;SALARIO;5.000,00\n"
    ).encode("utf-8")
    acc = import_csv(csv_bytes)
    assert len(acc.transactions) == 2
    t0 = acc.transactions[0]
    assert t0.date == date(2025, 11, 5)
    assert t0.description == "IFOOD RESTAURANTE"
    assert t0.amount == -45.90
    assert acc.transactions[1].amount == 5000.00


def test_import_csv_colunas_debito_credito():
    csv_bytes = (
        "Data,Histórico,Débito,Crédito\n"
        "01/10/2025,COMPRA MERCADO,210.00,\n"
        "02/10/2025,DEPOSITO,,300.00\n"
    ).encode("utf-8")
    acc = import_csv(csv_bytes)
    assert acc.transactions[0].amount == -210.00
    assert acc.transactions[1].amount == 300.00


def test_fingerprint_dedup_estavel():
    csv_bytes = "Data;Descrição;Valor\n05/11/2025;IFOOD;-45,90\n".encode("utf-8")
    a = import_csv(csv_bytes).transactions[0].fingerprint()
    b = import_csv(csv_bytes).transactions[0].fingerprint()
    assert a == b  # mesmo conteúdo -> mesmo hash (não duplica)


SAMPLE_OFX = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>BRL
<BANKACCTFROM><BANKID>001<ACCTID>12345<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20251105<TRNAMT>-45.90<FITID>A1<MEMO>IFOOD RESTAURANTE</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20251106<TRNAMT>5000.00<FITID>A2<MEMO>SALARIO</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>4954.10<DTASOF>20251106</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def test_import_ofx_basico():
    acc = import_ofx(SAMPLE_OFX)
    assert len(acc.transactions) == 2
    valores = sorted(t.amount for t in acc.transactions)
    assert valores == [-45.90, 5000.00]
