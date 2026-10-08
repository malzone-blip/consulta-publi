# -*- coding: utf-8 -*-
"""Ferramentas de OSINT para due-diligence - com guardrails de seguranca.

Reune quatro capacidades, todas gratuitas:
  - WhatsMyName : checa um username em ~700 sites (dataset aberto embarcado)
  - Sherlock    : mesma ideia via a ferramenta externa (subprocess, opcional)
  - SpiderFoot  : consulta a uma instancia SpiderFoot que a empresa rode a parte
  - Construtor de dorks : gera links de busca avancada (Google/Bing), sem requisicao

PRINCIPIOS DE SEGURANCA aplicados aqui (nao sao opcionais):
  1. O username so entra em URL/comando depois de validado contra uma whitelist
     de caracteres. Isso barra injecao de comando (Sherlock) e quebra de path (URL).
  2. Sherlock roda via subprocess com LISTA de argumentos e shell=False - nunca
     uma string de shell.
  3. Toda requisicao de rede tem timeout curto e a checagem em massa tem
     concorrencia e teto de sites limitados, para nao virar ferramenta de abuso
     nem queimar o IP do servidor.
  4. As URLs verificadas vem do dataset confiavel do WhatsMyName, nao de input
     livre do usuario - o usuario so fornece o username.
  5. A pagina que usa isto exige permissao dedicada e registra cada consulta na
     auditoria. Compilar a presenca de uma pessoa em centenas de sites e sensivel
     (LGPD): o uso legitimo aqui e due-diligence, com finalidade registrada.

O Social-Engineer Toolkit (SET) foi deliberadamente deixado de fora: e um
framework ofensivo de phishing/engenharia social, nao uma fonte de dados, e nao
tem lugar num painel corporativo de consulta.
"""
import concurrent.futures
import ipaddress
import re
import socket
import subprocess
import sys
import threading
from urllib.parse import quote_plus, urlparse

import urllib3

try:
    import certifi
    _CA = certifi.where()
except Exception:  # pragma: no cover
    _CA = None

urllib3.disable_warnings()

from core import db, http
from core.config import DIR_DADOS, TTL_CADASTRAL

# Sites de alto valor para due-diligence: um "quick scan" que responde rapido.
# Casados (case-insensitive) contra o campo "name" do WhatsMyName.
SITES_PRIORITARIOS = {
    "instagram", "facebook", "twitter", "x", "linkedin", "github", "gitlab",
    "reddit", "youtube", "tiktok", "pinterest", "telegram", "twitch", "steam",
    "soundcloud", "spotify", "medium", "patreon", "paypal", "vimeo", "behance",
    "dribbble", "deviantart", "flickr", "tumblr", "wordpress", "keybase",
    "kaggle", "docker hub", "npm", "pypi", "gravatar", "about.me", "linktree",
    "mercado livre", "gitea", "hackernews",
}


# --- anti-SSRF: recusa hosts que resolvem para a rede interna ---------------
_CACHE_HOST = {}
_LOCK_HOST = threading.Lock()


def _ip_interno(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast)
    except ValueError:
        return True


def _ip_publico_do_host(host: str):
    """Resolve o host e devolve UM ip publico seguro, ou None.

    Chave do anti-SSRF: a resolucao acontece AQUI, uma unica vez, e a conexao
    seguinte e fixada exatamente neste IP (nao ha segunda resolucao). Isso fecha
    o DNS rebinding / TOCTOU - o atacante nao consegue trocar o IP entre a
    validacao e a conexao, porque so existe uma resolucao.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return None
    for info in infos:
        ip = info[4][0]
        if not _ip_interno(ip):
            return ip           # primeiro IP publico; conexao sera fixada nele
    return None


def host_seguro(url: str) -> bool:
    """True se a URL e http/https e o host tem ao menos um IP publico seguro.

    Mantida para clareza e para os testes; a protecao efetiva acontece em
    _buscar_pinado, que conecta no IP validado.
    """
    try:
        p = urlparse(url)
    except ValueError:
        return False
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    host = p.hostname
    with _LOCK_HOST:
        if host in _CACHE_HOST:
            return _CACHE_HOST[host] is not None
    ip = _ip_publico_do_host(host)
    with _LOCK_HOST:
        _CACHE_HOST[host] = ip
    return ip is not None


def _buscar_pinado(url: str, timeout: int):
    """GET com IP fixado (anti-SSRF/rebinding). Devolve (status, corpo) ou None.

    Resolve o host uma vez para um IP publico, conecta EXATAMENTE nesse IP e
    mantem o hostname para SNI e validacao de certificado - assim o conteudo e o
    TLS ficam corretos, mas nenhuma segunda resolucao pode desviar para a rede
    interna. Sem redirecionamentos e com corpo limitado.
    """
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return None
    ip = _ip_publico_do_host(p.hostname)
    if ip is None:
        return None
    porta = p.port or (443 if p.scheme == "https" else 80)
    caminho = p.path or "/"
    if p.query:
        caminho += "?" + p.query
    cabec = {"Host": p.hostname,
             "User-Agent": "Mozilla/5.0 (compatible; IntegraPublic/1.0)",
             "Accept": "text/html,application/xhtml+xml"}
    tmo = urllib3.Timeout(connect=4, read=timeout)
    try:
        if p.scheme == "https":
            pool = urllib3.HTTPSConnectionPool(
                ip, port=porta, timeout=tmo, retries=False, maxsize=1,
                server_hostname=p.hostname, assert_hostname=p.hostname,
                cert_reqs="CERT_REQUIRED" if _CA else "CERT_NONE", ca_certs=_CA)
        else:
            pool = urllib3.HTTPConnectionPool(
                ip, port=porta, timeout=tmo, retries=False, maxsize=1)
        resp = pool.request("GET", caminho, headers=cabec, redirect=False,
                            preload_content=False)
        corpo = b""
        if resp.status < 400:
            corpo = resp.read(CORPO_MAX)
        resp.release_conn()
        pool.close()
        return resp.status, corpo.decode("utf-8", "replace")
    except Exception:
        return None

# --- validacao de username (barra injecao e quebra de URL) ------------------
RE_USERNAME = re.compile(r"^[A-Za-z0-9._-]{2,40}$")

# Checagem em massa: sem retry (um erro e so "nao encontrado") e com corpo
# limitado. A conexao usa IP fixado - ver _buscar_pinado.
CORPO_MAX = 200_000   # le no maximo 200 KB por site (a string de deteccao vem no topo)


def username_valido(username: str) -> bool:
    return bool(RE_USERNAME.match(username or ""))


def normalizar_username(valor: str) -> str:
    """Limpa entradas comuns: tira espacos das pontas e um '@' inicial.

    Assim '@joaosilva' e ' joaosilva ' viram 'joaosilva' e passam na validacao,
    sem afrouxar a whitelist de caracteres (que segue barrando espacos internos,
    acentos e simbolos - importante para a seguranca da URL/subprocess).
    """
    return (valor or "").strip().lstrip("@").strip()


# ===========================================================================
# WhatsMyName - dataset aberto de sites
# ===========================================================================
WMN_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
WMN_LOCAL = DIR_DADOS / "wmn-data.json"


def carregar_wmn(forcar: bool = False):
    """Baixa (uma vez) e devolve a lista de sites do WhatsMyName."""
    import json
    if WMN_LOCAL.exists() and not forcar:
        try:
            with WMN_LOCAL.open("r", encoding="utf-8") as fh:
                return json.load(fh).get("sites", []), ""
        except (json.JSONDecodeError, OSError):
            pass
    resp = http.obter_json(WMN_URL, TTL_CADASTRAL, "WhatsMyName/dataset", forcar)
    if not resp.ok or not isinstance(resp.dados, dict):
        return [], "Nao foi possivel obter o dataset do WhatsMyName."
    try:
        with WMN_LOCAL.open("w", encoding="utf-8") as fh:
            json.dump(resp.dados, fh, ensure_ascii=False)
    except OSError:
        pass
    return resp.dados.get("sites", []), ""


def categorias_wmn():
    sites, _ = carregar_wmn()
    return sorted({s.get("cat", "outros") for s in sites if s.get("cat")})


def _checar_site(site: dict, username: str, timeout: int):
    """Aplica o algoritmo do WhatsMyName a um site. Devolve dict ou None."""
    uri = site.get("uri_check", "")
    if "{account}" not in uri:
        return None
    url = uri.replace("{account}", quote_plus(username))
    # Conexao com IP fixado: resolve uma vez, valida e conecta nesse IP. Fecha
    # SSRF e DNS rebinding num unico passo (sem segunda resolucao).
    resultado = _buscar_pinado(url, timeout)
    if resultado is None:
        return None
    status_code, corpo = resultado
    e_code = site.get("e_code")
    e_string = site.get("e_string")
    m_string = site.get("m_string")
    # Conta existe: status esperado E string de existencia presente E string de
    # ausencia nao presente.
    existe = (status_code == e_code)
    if existe and e_string:
        existe = e_string in corpo
    if existe and m_string:
        existe = m_string not in corpo
    if not existe:
        return None
    return {
        "Site": site.get("name"),
        "Categoria": site.get("cat", ""),
        "URL": (site.get("uri_pretty", uri)).replace("{account}", username),
    }


def buscar_username(username: str, categorias=None, apenas_prioritarios: bool = True,
                    max_sites: int = 400, workers: int = 40, timeout: int = 6):
    """Procura o username nos sites do WhatsMyName.

    apenas_prioritarios=True faz o "quick scan": so os ~35 sites de maior valor,
    rapido mesmo em rede restrita. False varre tudo (mais lento).
    Devolve (encontrados, total_checado, truncado, erro).
    """
    if not username_valido(username):
        return [], 0, False, ("Username invalido. Use de 2 a 40 caracteres, "
                              "apenas letras, numeros, ponto, hifen ou sublinhado.")
    sites, erro = carregar_wmn()
    if erro:
        return [], 0, False, erro
    if apenas_prioritarios:
        sites = [s for s in sites
                 if (s.get("name", "").lower() in SITES_PRIORITARIOS)]
    elif categorias:
        sites = [s for s in sites if s.get("cat") in categorias]
    truncado = len(sites) > max_sites
    sites = sites[:max_sites]

    encontrados = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = [executor.submit(_checar_site, s, username, timeout) for s in sites]
        for f in concurrent.futures.as_completed(futuros):
            r = f.result()
            if r:
                encontrados.append(r)
    encontrados.sort(key=lambda x: (x["Categoria"] or "", x["Site"] or ""))
    return encontrados, len(sites), truncado, ""


# ===========================================================================
# Sherlock - ferramenta externa (opcional)
# ===========================================================================
def sherlock_disponivel() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("sherlock_project") is not None
    except Exception:
        return False


def buscar_sherlock(username: str, timeout_por_site: int = 10,
                    timeout_total: int = 180):
    """Roda o Sherlock via subprocess seguro e devolve (encontrados, erro).

    Invocacao confirmada contra o codigo-fonte do sherlock-project:
        python -m sherlock_project USER --csv --folderoutput DIR --timeout N
               --no-color --print-found
    Saida: DIR/USER.csv com colunas
        username,name,url_main,url_user,exists,http_status,response_time_s

    Nota de ambiente: nesta VM a rede de saida e lenta (cada site leva ~5-15s),
    entao um scan completo (480+ sites) pode nao terminar no tempo. O timeout por
    site fica baixo para cortar sites travados; se ainda assim estourar, a
    funcao explica e sugere a busca rapida (WhatsMyName).
    """
    import csv
    import tempfile
    from pathlib import Path

    if not username_valido(username):
        return [], "Username invalido para a busca."
    if not sherlock_disponivel():
        return [], ("Sherlock nao esta instalado neste servidor. Um administrador "
                    "pode instala-lo no venv com: python -m pip install sherlock-project")

    with tempfile.TemporaryDirectory(prefix="sherlock_") as tmp:
        # argv como LISTA + shell=False: o username, ja validado, entra como um
        # unico argumento e nunca e interpretado pelo shell.
        argv = [
            sys.executable, "-m", "sherlock_project", username,
            "--csv", "--folderoutput", tmp,
            "--timeout", str(int(timeout_por_site)), "--no-color", "--print-found",
        ]
        esgotou = False
        try:
            subprocess.run(argv, capture_output=True, timeout=timeout_total,
                           shell=False, check=False)
        except subprocess.TimeoutExpired:
            esgotou = True   # tenta aproveitar o CSV parcial, se houver
        except Exception as exc:
            return [], "Falha ao executar o Sherlock: %s" % type(exc).__name__

        arquivo = Path(tmp) / ("%s.csv" % username)
        if not arquivo.exists():
            if esgotou:
                return [], ("O Sherlock nao terminou no tempo - a rede deste "
                            "servidor e lenta para varrer centenas de sites. Use a "
                            "busca rapida (WhatsMyName) acima, que ja cobre os "
                            "principais, ou tente o Sherlock novamente.")
            return [], ""
        encontrados = []
        try:
            with arquivo.open("r", encoding="utf-8", newline="") as fh:
                for linha in csv.DictReader(fh):
                    if linha.get("exists") == "Claimed":
                        encontrados.append({
                            "Site": linha.get("name"),
                            "URL": linha.get("url_user"),
                            "HTTP": linha.get("http_status"),
                        })
        except Exception as exc:
            return [], "Falha ao ler a saida do Sherlock: %s" % type(exc).__name__
    encontrados.sort(key=lambda x: x["Site"] or "")
    return encontrados, ""


# ===========================================================================
# SpiderFoot - instancia externa da empresa
# ===========================================================================
CFG_SPIDERFOOT_URL = "spiderfoot_url"       # ex.: http://127.0.0.1:5001


def spiderfoot_url() -> str:
    return db.obter_config(CFG_SPIDERFOOT_URL, "").rstrip("/")


def spiderfoot_configurado() -> bool:
    return bool(spiderfoot_url())


def spiderfoot_ping():
    """Verifica se a instancia SpiderFoot responde. (ok, versao_ou_erro)."""
    base = spiderfoot_url()
    if not base:
        return False, "URL do SpiderFoot nao configurada."
    try:
        r = http.sessao().get("%s/ping" % base, timeout=10)
        if r.status_code == 200:
            dados = r.json()
            if isinstance(dados, list) and dados and dados[0] == "SUCCESS":
                return True, dados[1] if len(dados) > 1 else "ok"
            return True, "ok"
        return False, "HTTP %d" % r.status_code
    except Exception as exc:
        return False, type(exc).__name__


# O SpiderFoot 4.0 casa o usecase com o NOME do grupo de modulos, que e
# capitalizado. "passive" minusculo nao casa (resulta em "no modules"); tem de
# ser "Passive". Os cinco campos precisam sempre estar presentes no POST, senao
# o CherryPy nao consegue vincular o metodo e devolve 404.
USECASES_SF = {"passive": "Passive", "investigate": "Investigate",
               "footprint": "Footprint", "all": "All"}


# Tipos de alvo aceitos pelo SpiderFoot (confirmado em spiderfoot/helpers.py,
# targetTypeFromString). Ele NAO e so username: aceita dominio, e-mail, IP,
# telefone, nome completo e nome de usuario. Cada um precisa de um formato:
# nome e username vao entre aspas; nome completo exige espaco; telefone comeca
# com '+'.
TIPOS_ALVO_SF = {
    "dominio": "Dominio (ex.: empresa.com.br)",
    "email": "E-mail (ex.: fulano@empresa.com)",
    "ip": "Endereco IP (ex.: 200.100.50.10)",
    "telefone": "Telefone com DDI (ex.: +5511999998888)",
    "nome": "Nome completo da pessoa",
    "username": "Nome de usuario",
}


def formatar_alvo_sf(tipo: str, valor: str):
    """Formata/valida o alvo conforme o tipo. Devolve (alvo_formatado, erro)."""
    v = (valor or "").strip()
    if not v:
        return None, "Informe o alvo."
    if tipo == "dominio":
        d = v.lower()
        for pre in ("https://", "http://"):
            if d.startswith(pre):
                d = d[len(pre):]
        return d.split("/")[0], ""
    if tipo == "email":
        return (v, "") if "@" in v else (None, "E-mail invalido.")
    if tipo == "ip":
        return v, ""
    if tipo == "telefone":
        dig = "".join(c for c in v if c.isdigit())
        if len(dig) < 10:
            return None, "Telefone incompleto. Use DDI+DDD+numero (ex.: +5511...)."
        return "+" + dig, ""
    if tipo == "nome":
        limpo = v.strip('"')
        if " " not in limpo:
            return None, ("Para o SpiderFoot reconhecer como nome de pessoa, informe "
                          "nome E sobrenome.")
        return '"%s"' % limpo, ""
    if tipo == "username":
        return '"%s"' % v.strip('"'), ""
    return v, ""


def spiderfoot_iniciar_scan(nome: str, alvo: str, usecase: str = "passive"):
    """Inicia um scan no SpiderFoot. Devolve (scan_id, erro).

    Usa POST /startscan. Por padrao usecase=passive (nao toca o alvo).
    """
    base = spiderfoot_url()
    if not base:
        return None, "SpiderFoot nao configurado."
    grupo = USECASES_SF.get(usecase, "Passive")
    try:
        # timeout generoso: com muitos modulos passivos, o SpiderFoot leva alguns
        # segundos para montar o scan antes de devolver o id.
        r = http.sessao().post(
            "%s/startscan" % base,
            data={"scanname": nome, "scantarget": alvo, "usecase": grupo,
                  "modulelist": "", "typelist": ""},
            headers={"Accept": "application/json"}, timeout=90)
        if r.status_code != 200:
            return None, "HTTP %d ao iniciar o scan." % r.status_code
        dados = r.json()
        # A API devolve ["SUCCESS", scan_id] ou ["ERROR", mensagem].
        if isinstance(dados, list) and dados:
            if dados[0] == "SUCCESS" and len(dados) > 1:
                return dados[1], ""
            if dados[0] == "ERROR":
                return None, "SpiderFoot recusou: %s" % (dados[1] if len(dados) > 1
                                                         else "erro desconhecido")
        if isinstance(dados, str):
            return dados, ""
        return None, "Resposta inesperada ao iniciar o scan."
    except Exception as exc:
        return None, "Falha ao falar com o SpiderFoot: %s" % type(exc).__name__


def spiderfoot_resultados(scan_id: str):
    """Puxa os resultados de um scan. Devolve (lista, erro)."""
    base = spiderfoot_url()
    if not base:
        return [], "SpiderFoot nao configurado."
    try:
        r = http.sessao().get("%s/scaneventresults" % base,
                              params={"id": scan_id, "eventType": "ALL"},
                              headers={"Accept": "application/json"}, timeout=30)
        if r.status_code != 200:
            return [], "HTTP %d ao buscar resultados." % r.status_code
        return (r.json() if isinstance(r.json(), list) else []), ""
    except Exception as exc:
        return [], "Falha ao buscar resultados: %s" % type(exc).__name__


# ===========================================================================
# Construtor de dorks (sem requisicao - so gera links)
# ===========================================================================
MOTORES = {
    "Google": "https://www.google.com/search?q=%s",
    "Bing": "https://www.bing.com/search?q=%s",
    "DuckDuckGo": "https://duckduckgo.com/?q=%s",
}

# Templates de due-diligence. {alvo}=nome/razao social, {dominio}=site,
# {cnpj}=documento. O usuario preenche o que tiver.
TEMPLATES_DORK = [
    ("Nome em qualquer lugar", '"{alvo}"'),
    ("Nome + CNPJ", '"{alvo}" "{cnpj}"'),
    ("Documentos PDF sobre o alvo", '"{alvo}" filetype:pdf'),
    ("Planilhas expostas", '"{alvo}" (filetype:xlsx OR filetype:csv)'),
    ("Mencoes em diarios oficiais", '"{alvo}" (site:jusbrasil.com.br OR diario oficial)'),
    ("Processos e reclamacoes", '"{alvo}" (reclamacao OR processo OR condenacao)'),
    ("Noticias negativas", '"{alvo}" (fraude OR golpe OR investigacao OR denuncia)'),
    ("Vazamentos e credenciais", '"{alvo}" (senha OR password OR credencial)'),
    ("Perfis em redes sociais", '"{alvo}" (site:linkedin.com OR site:instagram.com OR site:facebook.com)'),
    ("Tudo no dominio da empresa", 'site:{dominio}'),
    ("Documentos no dominio", 'site:{dominio} filetype:pdf'),
    ("Paginas de login no dominio", 'site:{dominio} (inurl:login OR inurl:admin)'),
    ("Diretorios abertos no dominio", 'site:{dominio} intitle:"index of"'),
    ("Emails no dominio", 'intext:"@{dominio}"'),
    ("CNPJ em bases publicas", '"{cnpj}"'),
]


def montar_dorks(motor: str, alvo: str = "", dominio: str = "", cnpj: str = ""):
    """Devolve [(rotulo, texto_busca, url)] para os templates aplicaveis."""
    base = MOTORES.get(motor, MOTORES["Google"])
    saida = []
    for rotulo, modelo in TEMPLATES_DORK:
        # so inclui templates cujos placeholders foram preenchidos
        if "{alvo}" in modelo and not alvo:
            continue
        if "{dominio}" in modelo and not dominio:
            continue
        if "{cnpj}" in modelo and not cnpj:
            continue
        texto = (modelo.replace("{alvo}", alvo)
                       .replace("{dominio}", dominio)
                       .replace("{cnpj}", cnpj))
        saida.append((rotulo, texto, base % quote_plus(texto)))
    return saida
