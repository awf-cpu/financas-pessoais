"""Testes do motor de regras PT-BR (sem rede, sem IA)."""
from app.categorize import categorize_by_rules


def test_ifood_alimentacao():
    assert categorize_by_rules("IFOOD *RESTAURANTE", -45.90) == "Alimentação"


def test_uber_transporte():
    assert categorize_by_rules("UBER *TRIP SAO PAULO", -22.30) == "Transporte"


def test_supermercado_mercado():
    assert categorize_by_rules("CARREFUR SUPERMERCADO", -210.00) == "Mercado"


def test_netflix_streaming():
    assert categorize_by_rules("NETFLIX.COM", -39.90) == "Lazer & Streaming"


def test_salario_receita():
    assert categorize_by_rules("SALARIO EMPRESA XYZ", 5000.0) == "Receitas"


def test_pix_entrada_vira_receita():
    # PIX de entrada (valor positivo) deve ser classificado como Receita.
    assert categorize_by_rules("PIX RECEBIDO JOAO", 150.0) == "Receitas"


def test_pix_saida_transferencia():
    assert categorize_by_rules("PIX ENVIADO MARIA", -150.0) == "Transferências"


def test_tarifa():
    assert categorize_by_rules("TARIFA PACOTE SERVICOS", -29.90) == "Tarifas & Juros"


def test_desconhecido_retorna_none():
    assert categorize_by_rules("XPTO9988 QWERTY", -10.0) is None
