# -*- coding: utf-8 -*-
"""Configuracoes centrais do IntegraPublic."""
from pathlib import Path

APP_NOME = "IntegraPublic"
APP_SUBTITULO = "Sistema Geral Interdepartamental - Dados Publicos Oficiais"
APP_VERSAO = "1.0.0"

RAIZ = Path(__file__).resolve().parent.parent
DIR_DADOS = RAIZ / "dados"
DIR_CACHE = DIR_DADOS / "cache"
BANCO = DIR_DADOS / "integrapublic.db"

DIR_DADOS.mkdir(parents=True, exist_ok=True)
DIR_CACHE.mkdir(parents=True, exist_ok=True)

# --- Rede -------------------------------------------------------------------
HOST = "0.0.0.0"
PORTA = 6789
IP_REDE = "10.10.1.225"
URL_REDE = "http://%s:%d" % (IP_REDE, PORTA)

# --- Politica de senhas -----------------------------------------------------
SENHA_PADRAO = "mudar@123"
SENHA_MIN_TAMANHO = 8
PBKDF2_ITERACOES = 260_000
MAX_TENTATIVAS_LOGIN = 5
BLOQUEIO_MINUTOS = 10

# --- Cache / atualizacao automatica ----------------------------------------
# TTL em segundos por natureza do dado. O cache em disco garante que o sistema
# sempre exibe a informacao mais recente disponivel na fonte e, se a fonte
# estiver fora do ar, mantem o ultimo dado bom (marcado como defasado).
TTL_INTRADIARIO = 15 * 60          # cotacoes do dia
TTL_DIARIO = 6 * 60 * 60           # series diarias, Focus
TTL_CADASTRAL = 24 * 60 * 60       # instituicoes, agencias, correspondentes
TTL_MENSAL = 12 * 60 * 60          # estatisticas mensais (Pix, meios de pagto)
TTL_MEMORIA = 90                   # cache em processo (Streamlit)

TIMEOUT_HTTP = 45
TENTATIVAS_HTTP = 3
TIMEOUT_LENTO = 90          # fontes reconhecidamente lentas (Querido Diario, PNCP)

# --- Chaves de API ----------------------------------------------------------
# DataJud (CNJ): a chave abaixo NAO e uma credencial sua. O proprio Conselho
# Nacional de Justica a publica na documentacao da API Publica, igual para
# todos os consumidores. Fica aqui como padrao e pode ser sobrescrita em
# Administracao > Fontes de Dados caso o CNJ a rotacione.
CHAVE_DATAJUD_PADRAO = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

# Chaves guardadas na tabela 'configuracoes' e informadas pelo administrador.
CFG_CHAVE_CGU = "cgu_api_key"          # Portal da Transparencia - cadastro gratuito
CFG_CHAVE_DATAJUD = "datajud_api_key"  # sobrescreve CHAVE_DATAJUD_PADRAO

URL_CADASTRO_CGU = "https://api.portaldatransparencia.gov.br/swagger-ui.html"
