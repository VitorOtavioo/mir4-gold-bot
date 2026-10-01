import json
import os
from typing import Optional

from utils.cotacao import obter_cotacao_usd_brl

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "precos.json")


def carregar_config() -> dict:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_config(dados: dict) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def preco_brl_por_mil(quantidade: int, faixas: list) -> Optional[float]:
    for faixa in faixas:
        minimo = faixa["min"]
        maximo = faixa["max"]
        if quantidade >= minimo and (maximo is None or quantidade <= maximo):
            return faixa["preco"]
    return None


async def calcular_pedido(quantidade: int) -> dict:
    config = carregar_config()
    taxa_percent = config["taxa_mercado_percent"]
    faixas = config["faixas_brl"]

    preco_brl_mil = preco_brl_por_mil(quantidade, faixas)
    if preco_brl_mil is None:
        raise ValueError("Não há faixa de preço cadastrada para essa quantidade.")

    cotacao = await obter_cotacao_usd_brl(config["cotacao_fallback_usd_brl"])
    preco_usd_mil = preco_brl_mil / cotacao

    total_brl = (quantidade / 1000) * preco_brl_mil
    total_usd = (quantidade / 1000) * preco_usd_mil

    gold_a_enviar = round(quantidade * (1 + taxa_percent / 100))

    return {
        "quantidade": quantidade,
        "taxa_percent": taxa_percent,
        "gold_a_enviar": gold_a_enviar,
        "preco_brl_mil": preco_brl_mil,
        "preco_usd_mil": preco_usd_mil,
        "cotacao": cotacao,
        "total_brl": total_brl,
        "total_usd": total_usd,
    }
