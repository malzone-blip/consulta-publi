# -*- coding: utf-8 -*-
"""Camada de acesso as APIs publicas.

Estrategia de atualizacao automatica
------------------------------------
Toda consulta passa por um cache em disco com TTL por natureza do dado.

    1. Se existe copia local dentro do TTL  -> devolve na hora (rapido).
    2. Se venceu o TTL                      -> busca na fonte e regrava.
    3. Se a fonte falhar                    -> devolve a ultima copia boa,
                                               marcada como DEFASADA.

Assim o sistema sempre mostra a informacao mais recente publicada pela fonte,
sem depender de o usuario clicar em nada, e continua util quando o Banco
Central esta fora do ar (o que acontece com alguma frequencia em janelas de
manutencao). Nenhuma dessas APIs exige chave ou autenticacao.
"""
import hashlib
import json
import threading
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 >= 2 e < 2 expoem Retry em lugares diferentes
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover
    from requests.packages.urllib3.util.retry import Retry  # type: ignore

from core.config import DIR_CACHE, TENTATIVAS_HTTP, TIMEOUT_HTTP

_LOCK = threading.Lock()
_SESSAO: requests.Session | None = None

CABECALHOS = {
    "User-Agent": "IntegraPublic/1.0 (Sistema Geral Interdepartamental)",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}


def sessao() -> requests.Session:
    """Sessao HTTP unica, com retry exponencial em falhas transitorias."""
    global _SESSAO
    if _SESSAO is None:
        with _LOCK:
            if _SESSAO is None:
                s = requests.Session()
                s.headers.update(CABECALHOS)
                politica = Retry(
                    total=TENTATIVAS_HTTP,
                    backoff_factor=1.5,
                    status_forcelist=(429, 500, 502, 503, 504),
                    allowed_methods=frozenset(["GET"]),
                    raise_on_status=False,
                )
                adaptador = HTTPAdapter(max_retries=politica, pool_connections=10,
                                        pool_maxsize=20)
                s.mount("https://", adaptador)
                s.mount("http://", adaptador)
                _SESSAO = s
    return _SESSAO


# --------------------------------------------------------------------------
# Cache em disco
# --------------------------------------------------------------------------
def _arquivo(chave: str):
    nome = hashlib.sha1(chave.encode("utf-8")).hexdigest()[:24]
    return DIR_CACHE / ("%s.json" % nome)


def _ler_cache(chave: str):
    caminho = _arquivo(chave)
    if not caminho.exists():
        return None
    try:
        with caminho.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


# Formato unico de data/hora exibido ao usuario: dd/mm/aaaa HH:MM:SS (padrao BR).
# Definido num so lugar para nunca divergir entre os pontos que geram o selo.
FMT_DATAHORA = "%d/%m/%Y %H:%M:%S"


def _agora_txt() -> str:
    return datetime.now().strftime(FMT_DATAHORA)


def _gravar_cache(chave: str, rotulo: str, url: str, dados: Any) -> None:
    pacote = {
        "rotulo": rotulo,
        "url": url,
        "obtido_em": time.time(),
        "obtido_em_txt": _agora_txt(),
        "dados": dados,
    }
    try:
        tmp = _arquivo(chave).with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(pacote, fh, ensure_ascii=False)
        tmp.replace(_arquivo(chave))
    except OSError:
        pass


class RespostaFonte:
    """Resultado de uma consulta: os dados e a procedencia deles."""

    def __init__(self, dados, obtido_em_txt="", origem="rede", erro=""):
        self.dados = dados
        self.obtido_em_txt = obtido_em_txt
        self.origem = origem            # rede | cache | cache_defasado
        self.erro = erro

    @property
    def defasado(self) -> bool:
        return self.origem == "cache_defasado"

    @property
    def ok(self) -> bool:
        return self.dados is not None

    def selo(self) -> str:
        if self.origem == "rede":
            return "Atualizado agora - %s" % self.obtido_em_txt
        if self.origem == "cache":
            return "Atualizado em %s" % self.obtido_em_txt
        return "Fonte indisponivel - exibindo copia de %s" % self.obtido_em_txt


def obter_json(url: str, ttl: int, rotulo: str = "", forcar: bool = False,
               cabecalhos: dict | None = None, timeout: int | None = None) -> RespostaFonte:
    """Busca JSON respeitando o TTL, com queda para a ultima copia boa."""
    rotulo = rotulo or url
    chave = url
    cache = _ler_cache(chave)
    agora = time.time()

    if cache and not forcar and (agora - cache.get("obtido_em", 0)) < ttl:
        return RespostaFonte(cache["dados"], cache.get("obtido_em_txt", ""), "cache")

    try:
        resp = sessao().get(url, timeout=timeout or TIMEOUT_HTTP,
                            headers=cabecalhos or {})
        # 204 No Content (ex.: PNCP para periodo vazio) e "nada encontrado",
        # nao erro - devolve lista vazia em vez de cair no except.
        if resp.status_code == 204 or not resp.content:
            dados = []
            _gravar_cache(chave, rotulo, url, dados)
            return RespostaFonte(dados, _agora_txt(),
                                 "rede")
        resp.raise_for_status()
        texto = resp.text.strip()
        # O Olinda devolve erro dentro de um comentario /*{...}*/ com HTTP 200
        if texto.startswith("/*"):
            raise ValueError("A fonte retornou erro: %s" % texto[:180])
        dados = json.loads(texto)
        _gravar_cache(chave, rotulo, url, dados)
        return RespostaFonte(dados, _agora_txt(), "rede")
    except Exception as exc:  # rede, timeout, json invalido, http 4xx/5xx
        if cache:
            return RespostaFonte(
                cache["dados"], cache.get("obtido_em_txt", ""), "cache_defasado",
                "%s: %s" % (type(exc).__name__, str(exc)[:200]),
            )
        return RespostaFonte(None, "", "erro", "%s: %s" % (type(exc).__name__, str(exc)[:200]))


def obter_texto(url: str, ttl: int, rotulo: str = "", forcar: bool = False,
                codificacao: str = "utf-8") -> RespostaFonte:
    """Igual a obter_json, para fontes que publicam CSV ou texto puro."""
    rotulo = rotulo or url
    chave = "texto::" + url
    cache = _ler_cache(chave)
    agora = time.time()

    if cache and not forcar and (agora - cache.get("obtido_em", 0)) < ttl:
        return RespostaFonte(cache["dados"], cache.get("obtido_em_txt", ""), "cache")

    try:
        resp = sessao().get(url, timeout=TIMEOUT_HTTP)
        resp.raise_for_status()
        resp.encoding = codificacao
        texto = resp.text
        _gravar_cache(chave, rotulo, url, texto)
        return RespostaFonte(texto, _agora_txt(), "rede")
    except Exception as exc:
        if cache:
            return RespostaFonte(cache["dados"], cache.get("obtido_em_txt", ""),
                                 "cache_defasado",
                                 "%s: %s" % (type(exc).__name__, str(exc)[:200]))
        return RespostaFonte(None, "", "erro", "%s: %s" % (type(exc).__name__, str(exc)[:200]))


def enviar_json(url: str, corpo: dict, ttl: int, rotulo: str = "",
                forcar: bool = False, cabecalhos: dict | None = None,
                timeout: int | None = None) -> RespostaFonte:
    """POST com cache.

    Algumas APIs publicas (ComexStat, DataJud) so aceitam consulta via POST.
    Como a resposta depende do corpo enviado, a chave de cache combina URL e
    corpo - assim duas consultas diferentes nao se sobrescrevem.
    """
    rotulo = rotulo or url
    chave = "post::%s::%s" % (url, json.dumps(corpo, sort_keys=True, ensure_ascii=False))
    cache = _ler_cache(chave)
    agora = time.time()

    if cache and not forcar and (agora - cache.get("obtido_em", 0)) < ttl:
        return RespostaFonte(cache["dados"], cache.get("obtido_em_txt", ""), "cache")

    try:
        resp = sessao().post(url, json=corpo, timeout=timeout or TIMEOUT_HTTP,
                             headers=cabecalhos or {})
        resp.raise_for_status()
        dados = resp.json()
        _gravar_cache(chave, rotulo, url, dados)
        return RespostaFonte(dados, _agora_txt(), "rede")
    except Exception as exc:
        if cache:
            return RespostaFonte(cache["dados"], cache.get("obtido_em_txt", ""),
                                 "cache_defasado",
                                 "%s: %s" % (type(exc).__name__, str(exc)[:200]))
        return RespostaFonte(None, "", "erro", "%s: %s" % (type(exc).__name__, str(exc)[:200]))


# --------------------------------------------------------------------------
# Montagem de URLs OData (Olinda / Banco Central)
# --------------------------------------------------------------------------
BASE_OLINDA = "https://olinda.bcb.gov.br/olinda/servico"


def url_olinda(servico: str, recurso: str, versao: str = "v1",
               parametros: dict | None = None, opcoes: dict | None = None) -> str:
    """Monta a URL de um recurso do Olinda.

    parametros -> argumentos do recurso, no formato do Olinda:
                  Recurso(Chave=@Chave)?@Chave='valor'
                  Valores de texto precisam de aspas simples; numeros nao.
    opcoes     -> opcoes OData ($top, $filter, $select, $orderby, $format...)
    """
    partes = []
    consulta = []
    if parametros is not None:
        for nome in parametros:
            partes.append("%s=@%s" % (nome, nome))
        for nome, valor in parametros.items():
            consulta.append("@%s=%s" % (nome, quote(str(valor), safe="'")))
    # Funcoes do Olinda exigem os parenteses mesmo sem argumentos - passar um
    # dicionario vazio produz "Recurso()", que e o formato aceito. Passar None
    # produz "Recurso", usado pelos conjuntos de entidades.
    sufixo = "(%s)" % ",".join(partes) if parametros is not None else ""

    opcoes = dict(opcoes or {})
    opcoes.setdefault("$format", "json")
    for nome, valor in opcoes.items():
        consulta.append("%s=%s" % (nome, quote(str(valor), safe="'(),/*")))

    return "%s/%s/versao/%s/odata/%s%s?%s" % (
        BASE_OLINDA, servico, versao, recurso, sufixo, "&".join(consulta)
    )


def olinda(servico: str, recurso: str, ttl: int, rotulo: str, versao: str = "v1",
           parametros: dict | None = None, opcoes: dict | None = None,
           forcar: bool = False) -> RespostaFonte:
    """Consulta um recurso do Olinda e devolve a lista em .dados."""
    url = url_olinda(servico, recurso, versao, parametros, opcoes)
    resp = obter_json(url, ttl, rotulo, forcar)
    if resp.ok and isinstance(resp.dados, dict):
        resp.dados = resp.dados.get("value", [])
    return resp


# --------------------------------------------------------------------------
# Estado do cache (usado pela tela administrativa de Fontes de Dados)
# --------------------------------------------------------------------------
def estado_cache() -> list:
    """Lista o que ha em cache, com rotulo, idade e tamanho."""
    itens = []
    for caminho in sorted(DIR_CACHE.glob("*.json")):
        try:
            with caminho.open("r", encoding="utf-8") as fh:
                p = json.load(fh)
            idade = (time.time() - p.get("obtido_em", 0)) / 60.0
            itens.append({
                "Fonte": p.get("rotulo", "-"),
                "Atualizado em": p.get("obtido_em_txt", "-"),
                "Idade (min)": round(idade, 1),
                "Tamanho (KB)": round(caminho.stat().st_size / 1024.0, 1),
                "arquivo": caminho.name,
            })
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(itens, key=lambda x: x["Fonte"])


def limpar_cache() -> int:
    """Apaga todo o cache em disco. A proxima consulta rebusca nas fontes."""
    n = 0
    for caminho in DIR_CACHE.glob("*.json"):
        try:
            caminho.unlink()
            n += 1
        except OSError:
            pass
    for caminho in DIR_CACHE.glob("*.tmp"):
        try:
            caminho.unlink()
        except OSError:
            pass
    return n


def testar(url: str, timeout: int = 20) -> tuple:
    """Ping simples numa fonte. Devolve (ok, detalhe, milissegundos)."""
    inicio = time.perf_counter()
    try:
        resp = sessao().get(url, timeout=timeout)
        ms = int((time.perf_counter() - inicio) * 1000)
        if resp.status_code == 200 and not resp.text.strip().startswith("/*"):
            return True, "HTTP 200", ms
        return False, "HTTP %d" % resp.status_code, ms
    except Exception as exc:
        ms = int((time.perf_counter() - inicio) * 1000)
        return False, type(exc).__name__, ms
