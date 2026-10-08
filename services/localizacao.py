# -*- coding: utf-8 -*-
"""Geocodificacao via Nominatim (OpenStreetMap).

Gratuito, sem chave. A politica de uso do Nominatim exige User-Agent
identificavel e no maximo uma consulta por segundo - por isso o resultado e
cacheado e a chamada e pontual, nunca em lote.
"""
from core import http
from core.config import TTL_CADASTRAL

NOMINATIM = "https://nominatim.openstreetmap.org/search"


def geocodificar(endereco: str):
    """Devolve (lista_de_pontos, erro). Cada ponto: nome, lat, lon, tipo."""
    from urllib.parse import quote
    url = "%s?q=%s&format=json&limit=5&addressdetails=1&countrycodes=br" % (
        NOMINATIM, quote(endereco))
    resp = http.obter_json(
        url, TTL_CADASTRAL, "Nominatim/%s" % endereco[:40],
        cabecalhos={"User-Agent": "IntegraPublic/1.0 (sistema interno)"})
    if not resp.ok:
        return [], "Nao foi possivel consultar o servico de mapas agora."
    if not isinstance(resp.dados, list):
        return [], ""
    pontos = []
    for item in resp.dados:
        try:
            pontos.append({
                "nome": item.get("display_name", ""),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "tipo": item.get("type", ""),
            })
        except (KeyError, ValueError, TypeError):
            continue
    return pontos, ""
