# -*- coding: utf-8 -*-
"""Portal da Transparencia do Governo Federal (CGU) - API completa.

Sao 106 endpoints em 17 grupos tematicos: sancoes, servidores, despesas,
licitacoes, contratos, convenios, viagens, cartoes de pagamento, imoveis
funcionais, emendas, renuncias fiscais, notas fiscais, beneficios e mais.

Em vez de escrever um formulario para cada endpoint - o que envelheceria a
cada mudanca da CGU -, o sistema le o proprio catalogo OpenAPI publicado pelo
orgao e monta os formularios a partir dele. Endpoint novo que a CGU publicar
aparece aqui sozinho, sem precisar mexer no codigo.

O catalogo e publico. Apenas as CONSULTAS exigem a chave gratuita, enviada no
cabecalho 'chave-api-dados'.
"""
import pandas as pd
import streamlit as st

from core import db, http
from core.config import CFG_CHAVE_CGU, TTL_CADASTRAL, TTL_DIARIO, TTL_MEMORIA

BASE = "https://api.portaldatransparencia.gov.br"
CATALOGO_URL = "%s/v3/api-docs" % BASE
URL_CADASTRO = "http://www.portaldatransparencia.gov.br/api-de-dados/cadastrar-email"

# Atalhos para o que mais se usa no dia a dia de compliance e controladoria.
DESTAQUES = [
    ("/api-de-dados/ceis", "CEIS - empresas inidoneas e suspensas"),
    ("/api-de-dados/cnep", "CNEP - empresas punidas pela Lei Anticorrupcao"),
    ("/api-de-dados/cepim", "CEPIM - entidades privadas sem fins lucrativos impedidas"),
    ("/api-de-dados/acordos-leniencia", "Acordos de leniencia"),
    ("/api-de-dados/ceaf", "CEAF - expulsoes da administracao federal"),
    ("/api-de-dados/peps", "PEP - pessoas expostas politicamente"),
    ("/api-de-dados/pessoa-juridica", "Pessoa juridica - visao consolidada por CNPJ"),
    ("/api-de-dados/contratos/cpf-cnpj", "Contratos federais de um CNPJ"),
    ("/api-de-dados/licitacoes", "Licitacoes do Executivo Federal"),
    ("/api-de-dados/servidores", "Servidores do Executivo Federal"),
    ("/api-de-dados/viagens", "Viagens a servico"),
    ("/api-de-dados/cartoes", "Gastos com cartao de pagamento"),
]


# ---------------------------------------------------------------------------
# Chave de acesso
# ---------------------------------------------------------------------------
def chave() -> str:
    return db.obter_config(CFG_CHAVE_CGU, "")


def tem_chave() -> bool:
    return bool(chave().strip())


def cabecalhos() -> dict:
    return {"chave-api-dados": chave(), "Accept": "application/json"}


# ---------------------------------------------------------------------------
# Catalogo (publico, dispensa chave)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def catalogo(forcar: bool = False):
    """Le o OpenAPI da CGU e devolve {grupo: [endpoints]}.

    Cada endpoint: caminho, resumo, descricao e a lista de parametros com
    nome, obrigatoriedade, tipo e texto de ajuda - tudo que a tela precisa
    para montar o formulario.
    """
    resp = http.obter_json(CATALOGO_URL, TTL_CADASTRAL, "CGU/Catalogo de endpoints",
                           forcar)
    if not resp.ok or not isinstance(resp.dados, dict):
        return {}, resp

    grupos: dict = {}
    for caminho, metodos in (resp.dados.get("paths") or {}).items():
        info = metodos.get("get")
        if not info:
            continue
        grupo = (info.get("tags") or ["Outros"])[0]
        parametros = []
        for p in info.get("parameters", []):
            esquema = p.get("schema") or {}
            parametros.append({
                "nome": p.get("name"),
                "obrigatorio": bool(p.get("required")),
                "tipo": esquema.get("type", "string"),
                "opcoes": esquema.get("enum"),
                "ajuda": (p.get("description") or "").strip(),
                "onde": p.get("in", "query"),
            })
        grupos.setdefault(grupo, []).append({
            "caminho": caminho,
            "resumo": (info.get("summary") or caminho).strip(),
            "descricao": (info.get("description") or "").strip(),
            "parametros": parametros,
        })

    for grupo in grupos:
        grupos[grupo].sort(key=lambda e: e["caminho"])
    return dict(sorted(grupos.items())), resp


def endpoint_por_caminho(grupos: dict, caminho: str):
    for lista in grupos.values():
        for e in lista:
            if e["caminho"] == caminho:
                return e
    return None


# ---------------------------------------------------------------------------
# Consulta (exige chave)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def consultar(caminho: str, parametros: tuple, forcar: bool = False):
    """Executa um endpoint. 'parametros' e uma tupla de pares para ser hashavel."""
    if not tem_chave():
        return pd.DataFrame(), http.RespostaFonte(
            None, "", "erro",
            "Chave do Portal da Transparencia nao cadastrada.")

    valores = {k: v for k, v in parametros if v not in (None, "")}
    caminho_final = caminho
    consulta = {}
    for nome, valor in valores.items():
        marcador = "{%s}" % nome
        if marcador in caminho_final:                 # parametro de rota
            caminho_final = caminho_final.replace(marcador, str(valor))
        else:
            consulta[nome] = valor

    url = BASE + caminho_final
    if consulta:
        from urllib.parse import urlencode
        url += "?" + urlencode(consulta)

    resp = http.obter_json(url, TTL_DIARIO, "CGU %s" % caminho, forcar,
                           cabecalhos=cabecalhos(), timeout=90)
    if not resp.ok:
        return pd.DataFrame(), resp

    dados = resp.dados
    if isinstance(dados, dict):
        for k in ("content", "items", "data", "lista", "registros"):
            if isinstance(dados.get(k), list):
                dados = dados[k]
                break
    if isinstance(dados, dict):
        dados = [dados]
    if not isinstance(dados, list) or not dados:
        return pd.DataFrame(), resp

    return pd.json_normalize(dados), resp


# ---------------------------------------------------------------------------
# Atalho de compliance: um CNPJ contra todas as bases de sancao de uma vez
# ---------------------------------------------------------------------------
# Cada entrada: (caminho, nome_do_parametro_do_documento, rotulo, tipo_doc)
# tipo_doc: 'cnpj', 'cpf' ou 'ambos' - define em qual atalho aparece.
FONTES_COMPLIANCE = [
    ("/api-de-dados/ceis", "codigoSancionado",
     "CEIS - inidoneas e suspensas de licitar", "ambos"),
    ("/api-de-dados/cnep", "codigoSancionado",
     "CNEP - punidas pela Lei Anticorrupcao", "ambos"),
    ("/api-de-dados/cepim", "cnpjSancionado",
     "CEPIM - impedidas de receber recursos", "cnpj"),
    ("/api-de-dados/acordos-leniencia", "cnpjSancionado",
     "Acordos de leniencia", "cnpj"),
    ("/api-de-dados/ceaf", "cpfSancionado",
     "CEAF - expulsoes da administracao federal", "cpf"),
]


def _so_digitos(valor: str) -> str:
    return "".join(c for c in str(valor or "") if c.isdigit())


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def _consulta_bruta(caminho: str, parametros: tuple, forcar: bool = False):
    """Consulta simples devolvendo (lista_de_registros, resposta)."""
    if not tem_chave():
        return [], http.RespostaFonte(None, "", "erro", "Chave da CGU nao cadastrada.")
    from urllib.parse import urlencode
    consulta = {k: v for k, v in parametros if v not in (None, "")}
    url = BASE + caminho + "?" + urlencode(consulta)
    resp = http.obter_json(url, TTL_DIARIO, "CGU %s" % caminho, forcar,
                           cabecalhos=cabecalhos(), timeout=90)
    if not resp.ok:
        return [], resp
    dados = resp.dados
    if isinstance(dados, dict):
        for k in ("content", "items", "data", "lista"):
            if isinstance(dados.get(k), list):
                dados = dados[k]
                break
    if isinstance(dados, dict):
        dados = [dados]
    return (dados if isinstance(dados, list) else []), resp


def verificar_documento(documento: str, forcar: bool = False):
    """Roda o documento contra todas as bases de sancao aplicaveis.

    Devolve uma lista de resultados por base:
        {rotulo, caminho, quantidade, registros, erro}
    O tipo (CNPJ x CPF) e inferido pela quantidade de digitos.
    """
    dig = _so_digitos(documento)
    if len(dig) == 14:
        tipo = "cnpj"
    elif len(dig) == 11:
        tipo = "cpf"
    else:
        return None, "Informe um CNPJ (14 digitos) ou CPF (11 digitos)."

    saida = []
    for caminho, param, rotulo, aceita in FONTES_COMPLIANCE:
        if aceita != "ambos" and aceita != tipo:
            continue
        parametros = ((param, dig), ("pagina", 1))
        registros, resp = _consulta_bruta(caminho, parametros, forcar)
        saida.append({
            "rotulo": rotulo,
            "caminho": caminho,
            "quantidade": len(registros),
            "registros": registros,
            "erro": resp.erro if (resp and not resp.ok) else "",
            "selo": resp.selo() if resp and resp.ok else "",
        })

    # Contratos federais (so CNPJ) - contexto, nao sancao
    contratos = []
    if tipo == "cnpj":
        contratos, resp_c = _consulta_bruta(
            "/api-de-dados/contratos/cpf-cnpj", (("cpfCnpj", dig), ("pagina", 1)), forcar)

    return {"tipo": tipo, "documento": dig, "sancoes": saida,
            "contratos": contratos}, ""


def testar_chave(valor: str):
    """Valida a chave antes de gravar. Devolve (ok, mensagem)."""
    if not (valor or "").strip():
        return False, "Informe a chave."
    try:
        r = http.sessao().get(
            "%s/api-de-dados/ceis?pagina=1" % BASE, timeout=45,
            headers={"chave-api-dados": valor.strip(), "Accept": "application/json"},
        )
        if r.status_code == 200:
            return True, "Chave valida - a API respondeu normalmente."
        if r.status_code in (401, 403):
            return False, "A CGU recusou a chave (HTTP %d). Confira se copiou " \
                          "o token inteiro do e-mail." % r.status_code
        if r.status_code == 429:
            return False, "Chave aceita, mas o limite de requisicoes foi atingido " \
                          "agora. Tente novamente em alguns minutos."
        return False, "Resposta inesperada da CGU: HTTP %d." % r.status_code
    except Exception as exc:
        return False, "Nao foi possivel falar com a CGU: %s" % type(exc).__name__
