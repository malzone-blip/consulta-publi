# -*- coding: utf-8 -*-
"""Autoteste do IntegraPublic.

Verifica, sem subir a interface:
  1. que todos os modulos de pagina importam e expoem render();
  2. que o banco inicializa e a regra de senha padrao funciona;
  3. que as URLs montadas para o Olinda respondem de verdade.

Uso:  .venv\\Scripts\\python.exe scripts\\autoteste.py
"""
import importlib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

falhas = []


def verificar(titulo, condicao, detalhe=""):
    marca = "OK   " if condicao else "FALHA"
    print("  %s %s%s" % (marca, titulo, (" -> " + detalhe) if detalhe and not condicao else ""))
    if not condicao:
        falhas.append(titulo)


print("\n=== 1. Modulos de pagina ===")
from core.modulos import MODULOS  # noqa: E402

for m in MODULOS:
    try:
        mod = importlib.import_module("paginas.%s" % m["arquivo"])
        verificar("%s (%s)" % (m["titulo"], m["arquivo"]), callable(getattr(mod, "render", None)),
                  "sem funcao render()")
    except Exception as exc:
        verificar("%s (%s)" % (m["titulo"], m["arquivo"]), False,
                  "%s: %s" % (type(exc).__name__, exc))

print("\n=== 2. Banco, usuarios e senhas ===")
import tempfile  # noqa: E402

from core import db  # noqa: E402
from core.config import SENHA_PADRAO  # noqa: E402
from core.security import criar_credencial, validar_forca, verificar_senha  # noqa: E402

# O teste roda sobre um banco temporario: nao toca no banco de producao e pode
# ser executado quantas vezes for preciso, com o sistema no ar.
_temporario = Path(tempfile.mkdtemp(prefix="integrapublic_teste_")) / "teste.db"
db.BANCO = _temporario
print("  (banco de teste: %s)" % _temporario)

db.inicializar()
admin = db.buscar_usuario("admin")
verificar("usuario admin criado", admin is not None)
if admin:
    verificar("admin nasce com troca de senha obrigatoria", bool(admin["deve_trocar_senha"]))
    verificar("admin tem perfil administrador", bool(admin["is_admin"]))
    verificar("senha padrao '%s' confere" % SENHA_PADRAO,
              verificar_senha(SENHA_PADRAO, admin["senha_hash"], admin["salt"],
                              admin["iteracoes"]))
    verificar("senha errada e rejeitada",
              not verificar_senha("outra", admin["senha_hash"], admin["salt"],
                                  admin["iteracoes"]))

h1, s1, i1 = criar_credencial("Teste@123")
h2, s2, _ = criar_credencial("Teste@123")
verificar("salt individual por usuario", s1 != s2 and h1 != h2)
verificar("politica rejeita a propria senha padrao", not validar_forca(SENHA_PADRAO)[0])
verificar("politica rejeita senha curta", not validar_forca("ab1")[0])
verificar("politica rejeita senha so com letras", not validar_forca("somenteletras")[0])
verificar("politica aceita senha valida", validar_forca("Integra2026")[0])

print("\n=== 2b. Ciclo de vida de um usuario ===")
uid = db.criar_usuario("maria.silva", "Maria Silva", "maria@empresa.com", "Financeiro",
                       False, ["painel", "cambio"], "admin")
novo = db.buscar_usuario_id(uid)
verificar("usuario criado", novo is not None)
verificar("nasce com a senha padrao",
          verificar_senha(SENHA_PADRAO, novo["senha_hash"], novo["salt"],
                          novo["iteracoes"]))
verificar("nasce exigindo troca de senha", bool(novo["deve_trocar_senha"]))
verificar("nasce sem perfil de administrador", not novo["is_admin"])
verificar("recebe apenas os modulos concedidos",
          db.permissoes_do_usuario(uid) == {"painel", "cambio"})

db.atualizar_usuario(uid, "Maria S. Silva", "m@empresa.com", "Controladoria",
                     False, True, ["painel", "correspondentes", "compliance"])
verificar("edicao troca o conjunto de permissoes",
          db.permissoes_do_usuario(uid) == {"painel", "correspondentes", "compliance"})
verificar("edicao grava os dados cadastrais",
          db.buscar_usuario_id(uid)["setor"] == "Controladoria")

db.gravar_nova_senha(uid, "Maria@2026")
depois = db.buscar_usuario_id(uid)
verificar("troca de senha limpa a exigencia", not depois["deve_trocar_senha"])
verificar("senha nova confere",
          verificar_senha("Maria@2026", depois["senha_hash"], depois["salt"],
                          depois["iteracoes"]))
verificar("senha padrao deixa de valer",
          not verificar_senha(SENHA_PADRAO, depois["senha_hash"], depois["salt"],
                              depois["iteracoes"]))

db.redefinir_para_senha_padrao(uid)
resetado = db.buscar_usuario_id(uid)
verificar("admin consegue redefinir para a senha padrao",
          verificar_senha(SENHA_PADRAO, resetado["senha_hash"], resetado["salt"],
                          resetado["iteracoes"]) and resetado["deve_trocar_senha"])

verificar("existe apenas um administrador ativo", db.contar_admins_ativos() == 1)

for _ in range(5):
    db.registrar_falha_login(uid, 5, 10)
verificar("cinco falhas bloqueiam o acesso", db.esta_bloqueado(db.buscar_usuario_id(uid)))
db.registrar_login_ok(uid)
verificar("login bem-sucedido libera o bloqueio",
          not db.esta_bloqueado(db.buscar_usuario_id(uid)))

db.excluir_usuario(uid)
verificar("exclusao remove o usuario", db.buscar_usuario_id(uid) is None)
verificar("exclusao remove as permissoes", db.permissoes_do_usuario(uid) == set())

print("\n=== 3. Montagem de URLs OData ===")
from core import http  # noqa: E402

url_entidade = http.url_olinda("Informes_Agencias", "Agencias", "v1", None, {"$top": 1})
verificar("conjunto de entidades sem parenteses", "Agencias?" in url_entidade, url_entidade)

url_funcao = http.url_olinda("IFDATA", "ListaDeRelatorio", "v1", {}, {"$top": 1})
verificar("funcao sem argumentos recebe ()", "ListaDeRelatorio()?" in url_funcao, url_funcao)

url_param = http.url_olinda("Pix_DadosAbertos", "ChavesPix", "v1",
                            {"Data": "'2026-07-31'"}, {"$top": 1})
verificar("funcao com argumento monta corretamente",
          "ChavesPix(Data=@Data)?@Data='2026-07-31'" in url_param, url_param)

print("\n=== 4. Fontes ao vivo ===")
testes = [
    ("SGS (Selic)",
     "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"),
    ("PTAX (moedas)", http.url_olinda("PTAX", "Moedas", "v1", None, {"$top": 1})),
    ("IF.data (funcao com parenteses)", url_funcao),
    ("Pix chaves (funcao com argumento)", url_param),
    ("Correspondentes", http.url_olinda("Informes_Correspondentes", "Correspondentes",
                                        "v1", None, {"$top": 1, "$filter": "UF eq 'SP'"})),
    ("Tarifas (valores de mercado)",
     http.url_olinda("Informes_ListaValoresDeServicoBancario",
                     "ListaValoresServicoBancario", "v1",
                     {"PessoaFisicaOuJuridica": "'F'", "CodigoGrupoConsolidado": "'01'"},
                     {"$top": 1})),
    ("IBGE (gzip)", "https://servicodados.ibge.gov.br/api/v1/localidades/estados/33"),
    ("BrasilAPI", "https://brasilapi.com.br/api/banks/v1"),
    ("Open Finance", "https://data.directory.openbankingbrasil.org.br/participants"),
]
for nome, url in testes:
    ok, detalhe, ms = http.testar(url, timeout=45)
    verificar("%s (%d ms)" % (nome, ms), ok, detalhe)

print("\n" + "=" * 60)
if falhas:
    print("%d verificacao(oes) falharam:" % len(falhas))
    for f in falhas:
        print("  - %s" % f)
    sys.exit(1)
print("Todas as verificacoes passaram.")
sys.exit(0)
