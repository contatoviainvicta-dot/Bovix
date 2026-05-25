"""Testes do sistema de migrations versionadas."""
import pytest


def test_migrations_aplicadas_no_boot(db_temp):
    """Apos inicializar_banco, todas as migrations estao aplicadas."""
    from database import _MIGRATIONS, _versoes_aplicadas

    aplicadas = _versoes_aplicadas()
    esperadas = {v for v, _, _ in _MIGRATIONS}

    assert esperadas.issubset(aplicadas), \
        f"Faltam migrations: {esperadas - aplicadas}"


def test_migrations_idempotentes(db_temp):
    """Chamar aplicar_migrations multiplas vezes nao quebra."""
    n1 = db_temp.aplicar_migrations()
    n2 = db_temp.aplicar_migrations()
    n3 = db_temp.aplicar_migrations()

    # Primeira ja aplicou tudo no fixture, segundas chamadas devem retornar 0
    assert n2 == 0
    assert n3 == 0


def test_tabela_schema_version_existe(db_temp):
    """Tabela de controle de versao foi criada."""
    p = db_temp._ph()
    with db_temp._conexao() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM _schema_version")
        n = cur.fetchone()[0]
    assert n > 0


def test_tabelas_vet_existem(db_temp):
    """Apos migrations, todas as tabelas do modulo vet existem."""
    tabelas_esperadas = [
        "receitas", "protocolos_sanitarios", "protocolo_itens",
        "visitas_tecnicas", "relatorios_visita", "carencias_ativas",
        "exames_laboratoriais", "monitoramento_pos_tratamento",
        "honorarios_vet", "honorarios_itens", "mensagens_vet",
        "campanhas_vacinacao", "campanha_lotes", "fazendas_coords",
    ]
    for t in tabelas_esperadas:
        with db_temp._conexao() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            # Nao precisa ter dados, so existir
            _ = cur.fetchone()
