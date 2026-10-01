import logging
import time

import aiohttp

log = logging.getLogger("mir4bot")

_CACHE_SEGUNDOS = 1800  # 30 minutos — evita bater na API a cada comando
_cache = {"valor": None, "timestamp": 0.0}


async def obter_cotacao_usd_brl(fallback: float) -> float:
    """Retorna quantos reais valem 1 dólar. Usa cache de 30min e, se a API
    falhar, cai para o último valor conhecido ou para o fallback configurado."""

    agora = time.time()
    if _cache["valor"] is not None and (agora - _cache["timestamp"]) < _CACHE_SEGUNDOS:
        return _cache["valor"]

    try:
        async with aiohttp.ClientSession() as session:
            timeout = aiohttp.ClientTimeout(total=5)
            async with session.get(
                "https://economia.awesomeapi.com.br/last/USD-BRL", timeout=timeout
            ) as resp:
                dados = await resp.json()
                valor = float(dados["USDBRL"]["bid"])
                _cache["valor"] = valor
                _cache["timestamp"] = agora
                return valor
    except Exception as exc:
        log.warning("Falha ao buscar cotação USD/BRL (%s). Usando valor de reserva.", exc)
        return _cache["valor"] if _cache["valor"] is not None else fallback
