# cepea.py -- Cotacao automatica do boi gordo via Cepea / ESALQ
# Tenta buscar o preco atual. Faz fallback gracioso se nao conseguir conectar.

import re
from datetime import date, datetime
from typing import Optional

try:
    import urllib.request as _req
    _URLLIB = True
except ImportError:
    _URLLIB = False

_URL_CEPEA = "https://www.cepea.esalq.usp.br/br/indicador/boi-gordo.aspx"


def buscar_cotacao_cepea(timeout=8):
    if not _URLLIB:
        return _fallback("urllib indisponivel")
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9",
        }
        req = _req.Request(_URL_CEPEA, headers=headers)
        with _req.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        preco = _extrair_preco(html)
        if preco and preco > 50:
            return dict(preco=preco, data=str(date.today()), fonte="cepea", sucesso=True, msg=f"R$ {preco:.2f}/@")
        return _fallback("Preco nao encontrado no HTML")
    except OSError as e:
        return _fallback(f"Sem acesso: {e}")
    except Exception as e:
        return _fallback(f"Erro: {e}")


def _extrair_preco(html):
    for pattern in [r"R\$\s*([\d]{2,3}[,.][\d]{2})", r"([\d]{3}[,.][\d]{2})"]:
        matches = re.findall(pattern, html)
        for m in matches:
            try:
                val = float(m.replace(",","."))
                if 100 < val < 500: return val
            except: continue
    return None


def _fallback(msg):
    return dict(preco=0.0, data=str(date.today()), fonte="indisponivel", sucesso=False, msg=msg)


def cotacao_com_cache(database_module):
    hoje = str(date.today())
    ultima = database_module.obter_ultima_cotacao()
    if ultima and ultima[1] == hoje:
        return dict(preco=ultima[2], data=ultima[1], fonte=ultima[3], sucesso=True, msg="Cache do banco")
    resultado = buscar_cotacao_cepea()
    if resultado["sucesso"]:
        database_module.salvar_cotacao(resultado["data"], resultado["preco"], resultado["fonte"])
        return resultado
    if ultima:
        return dict(preco=ultima[2], data=ultima[1], fonte=f"{ultima[3]} (cache)",
                    sucesso=False, msg=f"Cepea indisponivel. Usando {ultima[1]}")
    return resultado


def historico_grafico(cotacoes):
    if not cotacoes: return dict(datas=[], precos=[])
    return dict(datas=[c[1] for c in cotacoes], precos=[c[2] for c in cotacoes])
