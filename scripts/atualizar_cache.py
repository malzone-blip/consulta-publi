# -*- coding: utf-8 -*-
"""Aquece o cache das fontes publicas.

Nao e obrigatorio: o sistema ja se atualiza sozinho quando uma tela e aberta e
o prazo do dado venceu. Este script serve para deixar tudo pronto ANTES de o
primeiro usuario chegar, de modo que ninguem espere o carregamento inicial.

Uso manual:
    .venv\\Scripts\\python.exe scripts\\atualizar_cache.py

Agendamento sugerido (Agendador de Tarefas do Windows, todo dia as 06h30):
    Programa:   C:\\Sistemas Pronto\\Sistema Geral Interdepartamental\\.venv\\Scripts\\python.exe
    Argumentos: scripts\\atualizar_cache.py
    Iniciar em: C:\\Sistemas Pronto\\Sistema Geral Interdepartamental
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import http  # noqa: E402
from core.config import TTL_CADASTRAL, TTL_DIARIO, TTL_INTRADIARIO  # noqa: E402

UFS_PRIORITARIAS = ["SP", "RJ", "MG", "PR", "RS", "BA", "PE", "SC", "GO", "DF"]


def _sgs(codigo, dias=730):
    fim = date.today()
    inicio = fim - timedelta(days=dias)
    return ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.%d/dados"
            "?formato=json&dataInicial=%s&dataFinal=%s"
            % (codigo, inicio.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y")))


def _trimestre_recente(voltar=1):
    """AnoMes do n-esimo trimestre fechado mais recente (formato AAAAMM)."""
    hoje = date.today()
    ano, mes = hoje.year, ((hoje.month - 1) // 3) * 3
    if mes == 0:
        ano, mes = ano - 1, 12
    for _ in range(voltar - 1):
        mes -= 3
        if mes <= 0:
            ano, mes = ano - 1, 12
    return int("%d%02d" % (ano, mes))


def _mes_anterior(voltar=1):
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    for _ in range(voltar):
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
    return "%d%02d" % (ano, mes)


def _ultimo_dia_mes_anterior():
    anomes = _mes_anterior(1)
    ano, mes = int(anomes[:4]), int(anomes[4:])
    if mes == 12:
        return "%d-12-31" % ano
    return (date(ano, mes + 1, 1) - timedelta(days=1)).strftime("%Y-%m-%d")


def tarefas():
    """(rotulo, url, ttl) de tudo que vale pre-carregar."""
    itens = []

    # Series economicas mais usadas no painel
    for codigo in (432, 11, 12, 433, 13522, 189, 226, 1):
        itens.append(("BCB/SGS serie %d" % codigo, _sgs(codigo), TTL_DIARIO))
        itens.append(("BCB/SGS serie %d" % codigo, _sgs(codigo, 1100), TTL_DIARIO))

    # Cambio
    fim = date.today()
    for dias in (90, 180):
        inicio = fim - timedelta(days=dias)
        itens.append((
            "BCB/PTAX USD",
            http.url_olinda("PTAX", "CotacaoMoedaPeriodo", "v1",
                            {"moeda": "'USD'",
                             "dataInicial": "'%s'" % inicio.strftime("%m-%d-%Y"),
                             "dataFinalCotacao": "'%s'" % fim.strftime("%m-%d-%Y")},
                            {"$orderby": "dataHoraCotacao desc", "$top": 5000}),
            TTL_INTRADIARIO,
        ))
    itens.append(("BCB/PTAX moedas",
                  http.url_olinda("PTAX", "Moedas", "v1", None,
                                  {"$orderby": "nomeFormatado"}), TTL_CADASTRAL))

    # Focus
    itens.append(("BCB/Focus anuais",
                  http.url_olinda("Expectativas", "ExpectativasMercadoAnuais", "v1",
                                  None, {"$top": 3000, "$orderby": "Data desc"}),
                  TTL_DIARIO))

    # Cadastros
    for recurso in ("SedesBancoComMultCE", "SedesCooperativas", "SedesConsorcios",
                    "SedesSociedades", "DominiosVerificados"):
        itens.append((
            "BCB/Instituicoes %s" % recurso,
            http.url_olinda("Instituicoes_em_funcionamento", recurso, "v1", None,
                            {"$top": 20000}),
            TTL_CADASTRAL,
        ))

    for recurso in ("QuadroGeralInabilitados", "QuadroGeralProibidos"):
        itens.append((
            "BCB/%s" % recurso,
            http.url_olinda("Gepad_QuadrosGeraisInternet", recurso, "v1", None,
                            {"$top": 20000}),
            TTL_CADASTRAL,
        ))

    # Rede de atendimento das UFs mais consultadas
    for uf in UFS_PRIORITARIAS:
        itens.append((
            "BCB/Agencias %s" % uf,
            http.url_olinda("Informes_Agencias", "Agencias", "v1", None,
                            {"$top": 20000, "$orderby": "NomeIf",
                             "$filter": "UF eq '%s'" % uf}),
            TTL_CADASTRAL,
        ))
        itens.append((
            "BCB/Correspondentes %s" % uf,
            http.url_olinda("Informes_Correspondentes", "Correspondentes", "v1", None,
                            {"$top": 30000, "$filter": "UF eq '%s'" % uf}),
            TTL_CADASTRAL,
        ))

    # Pagamentos
    itens.append(("BCB/SPI liquidados",
                  http.url_olinda("SPI", "PixLiquidadosAtual", "v1", None,
                                  {"$top": 4000}), TTL_DIARIO))
    itens.append(("BCB/STR liquidados",
                  http.url_olinda("STR", "STRLiquidadosAtual", "v2", None,
                                  {"$top": 6000}), TTL_DIARIO))
    itens.append(("BCB/Pix usuarios DICT",
                  http.url_olinda("Pix_DadosAbertos", "PixUsuariosCadastradosDICT",
                                  "v1", None, {"$top": 500}), TTL_DIARIO))

    # Telas mais pesadas na carga fria - pre-carregar faz diferenca real
    for anomes in (_trimestre_recente(1), _trimestre_recente(2)):
        itens.append((
            "BCB/IFData valores %s r1" % anomes,
            http.url_olinda("IFDATA", "IfDataValores", "v1",
                            {"AnoMes": anomes, "TipoInstituicao": 1, "Relatorio": "'1'"},
                            {"$top": 20000}),
            TTL_CADASTRAL,
        ))
        itens.append((
            "BCB/IFData cadastro %s" % anomes,
            http.url_olinda("IFDATA", "IfDataCadastro", "v1", {"AnoMes": anomes},
                            {"$top": 5000}),
            TTL_CADASTRAL,
        ))
    itens.append(("BCB/IFData relatorios",
                  http.url_olinda("IFDATA", "ListaDeRelatorio", "v1", {}),
                  TTL_CADASTRAL))

    mes_mpv = _mes_anterior(3)
    itens.append((
        "BCB/Meios de pagamento %s" % mes_mpv,
        http.url_olinda("MPV_DadosAbertos", "MeiosdePagamentosMensalDA", "v1",
                        {"AnoMes": "'%s'" % mes_mpv}, {"$top": 1000}),
        TTL_DIARIO,
    ))

    fim_mes = _ultimo_dia_mes_anterior()
    itens.append((
        "BCB/Pix chaves %s" % fim_mes,
        http.url_olinda("Pix_DadosAbertos", "ChavesPix", "v1",
                        {"Data": "'%s'" % fim_mes}, {"$top": 60000}),
        TTL_DIARIO,
    ))

    # Tarifas e catalogos
    itens.append(("BCB/Tarifas grupos",
                  http.url_olinda("Informes_ListaValoresDeServicoBancario",
                                  "GruposConsolidados", "v1"), TTL_CADASTRAL))
    itens.append(("BCB/DASFN todos",
                  http.url_olinda("DASFN", "Recursos", "v1", None, {"$top": 20000}),
                  TTL_CADASTRAL))

    # Fontes externas
    itens.append(("IBGE/Estados",
                  "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
                  "?orderBy=nome", TTL_CADASTRAL))
    itens.append(("BrasilAPI/Bancos", "https://brasilapi.com.br/api/banks/v1",
                  TTL_CADASTRAL))
    itens.append(("BrasilAPI/Participantes Pix",
                  "https://brasilapi.com.br/api/pix/v1/participants", TTL_CADASTRAL))
    itens.append(("OpenFinance/Diretorio",
                  "https://data.directory.openbankingbrasil.org.br/participants",
                  TTL_CADASTRAL))
    return itens


def main():
    lista = tarefas()
    print("IntegraPublic - aquecimento de cache (%d fontes)" % len(lista))
    print("-" * 70)
    ok = falhas = 0
    for rotulo, url, ttl in lista:
        resp = http.obter_json(url, ttl, rotulo, forcar=True)
        if resp.ok and resp.origem == "rede":
            ok += 1
            print("  OK    %s" % rotulo)
        elif resp.ok:
            ok += 1
            print("  CACHE %s (fonte falhou, copia local mantida)" % rotulo)
        else:
            falhas += 1
            print("  FALHA %s -> %s" % (rotulo, resp.erro))
    print("-" * 70)
    print("Concluido: %d atualizadas, %d com falha." % (ok, falhas))
    return 0 if falhas == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
