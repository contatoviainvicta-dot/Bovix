# db/schema.py -- Migrations, schema e inicializacao do banco
# Depende de db.core para conexao e helpers.
# Reexportado por database.py para manter compatibilidade.

from db.core import (
    _conexao, _ph, _fetch, _fetchone, _usar_postgres,
)

# ── Inicializar banco ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════
# SISTEMA DE MIGRATIONS VERSIONADAS
# ═══════════════════════════════════════════════════════════════════════════
try:
    from bovix_logging import get_logger
    _log_db  = get_logger("bovix.db.migrations")
    _log_err = get_logger("bovix.db.error")
    _log_war = get_logger("bovix.db.warning")
except ImportError:
    import logging
    _log_db  = logging.getLogger("bovix.db.migrations")
    _log_err = logging.getLogger("bovix.db.error")
    _log_war = logging.getLogger("bovix.db.warning")

# Cada migration tem: version (int), nome, SQL. Aplicadas em ordem.
# IMPORTANTE: nunca alterar uma migration existente — sempre criar nova.
_MIGRATIONS = [
    (1, "tabelas_base_vet", [
        """CREATE TABLE IF NOT EXISTS receitas (
            id              {pk},
            vet_id          INTEGER NOT NULL,
            fazenda_owner_id INTEGER NOT NULL,
            animal_id       INTEGER DEFAULT NULL,
            lote_id         INTEGER DEFAULT NULL,
            data_emissao    TEXT NOT NULL,
            medicamento     TEXT NOT NULL,
            dose            TEXT NOT NULL,
            via             TEXT NOT NULL,
            duracao         TEXT NOT NULL,
            carencia_dias   INTEGER DEFAULT 0,
            observacoes     TEXT DEFAULT '',
            crmv_emissao    TEXT DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS protocolos_sanitarios (
            id              {pk},
            vet_id          INTEGER NOT NULL,
            nome            TEXT NOT NULL,
            categoria       TEXT NOT NULL,
            data_criacao    TEXT NOT NULL,
            ativo           INTEGER DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS protocolo_itens (
            id              {pk},
            protocolo_id    INTEGER NOT NULL,
            tipo            TEXT NOT NULL,
            descricao       TEXT NOT NULL,
            dia_aplicacao   INTEGER DEFAULT 0,
            observacoes     TEXT DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS visitas_tecnicas (
            id              {pk},
            vet_id          INTEGER NOT NULL,
            fazenda_owner_id INTEGER NOT NULL,
            data_visita     TEXT NOT NULL,
            objetivo        TEXT NOT NULL,
            duracao_min     INTEGER DEFAULT 60,
            status          TEXT NOT NULL DEFAULT 'agendada',
            observacoes     TEXT DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS relatorios_visita (
            id              {pk},
            visita_id       INTEGER DEFAULT NULL,
            vet_id          INTEGER NOT NULL,
            fazenda_owner_id INTEGER NOT NULL,
            data_relatorio  TEXT NOT NULL,
            animais_inspecionados INTEGER DEFAULT 0,
            achados         TEXT DEFAULT '',
            tratamentos     TEXT DEFAULT '',
            recomendacoes   TEXT DEFAULT '',
            proxima_visita  TEXT DEFAULT NULL,
            observacoes     TEXT DEFAULT '',
            crmv_emissao    TEXT DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS carencias_ativas (
            id              {pk},
            animal_id       INTEGER NOT NULL,
            medicamento     TEXT NOT NULL,
            data_aplicacao  TEXT NOT NULL,
            carencia_dias   INTEGER NOT NULL,
            data_liberacao  TEXT NOT NULL,
            ativo           INTEGER DEFAULT 1
        )""",
    ]),
    (2, "tabelas_exames_monitor", [
        """CREATE TABLE IF NOT EXISTS exames_laboratoriais (
            id              {pk},
            animal_id       INTEGER NOT NULL,
            vet_id          INTEGER NOT NULL,
            data_coleta     TEXT NOT NULL,
            tipo_exame      TEXT NOT NULL,
            laboratorio     TEXT DEFAULT '',
            resultado       TEXT DEFAULT '',
            interpretacao   TEXT DEFAULT '',
            status          TEXT DEFAULT 'aguardando',
            alerta          INTEGER DEFAULT 0,
            anexo_url       TEXT DEFAULT NULL,
            criado_em       TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS monitoramento_pos_tratamento (
            id              {pk},
            animal_id       INTEGER NOT NULL,
            vet_id          INTEGER NOT NULL,
            receita_id      INTEGER DEFAULT NULL,
            descricao       TEXT NOT NULL,
            data_inicio     TEXT NOT NULL,
            data_retorno    TEXT NOT NULL,
            status          TEXT DEFAULT 'ativo',
            evolucoes       TEXT DEFAULT '[]',
            alerta_enviado  INTEGER DEFAULT 0
        )""",
    ]),
    (3, "tabelas_financeiro_vet", [
        """CREATE TABLE IF NOT EXISTS honorarios_vet (
            id              {pk},
            vet_id          INTEGER NOT NULL,
            fazenda_owner_id INTEGER NOT NULL,
            visita_id       INTEGER DEFAULT NULL,
            data_lancamento TEXT NOT NULL,
            descricao       TEXT NOT NULL,
            tipo            TEXT NOT NULL DEFAULT 'consulta',
            valor           REAL NOT NULL DEFAULT 0,
            status          TEXT NOT NULL DEFAULT 'pendente',
            data_pagamento  TEXT DEFAULT NULL,
            forma_pagamento TEXT DEFAULT NULL,
            observacoes     TEXT DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS honorarios_itens (
            id              {pk},
            honorario_id    INTEGER NOT NULL,
            descricao       TEXT NOT NULL,
            quantidade      REAL NOT NULL DEFAULT 1,
            valor_unitario  REAL NOT NULL DEFAULT 0,
            valor_total     REAL NOT NULL DEFAULT 0
        )""",
    ]),
    (4, "tabelas_comunic_camp_coords", [
        """CREATE TABLE IF NOT EXISTS mensagens_vet (
            id              {pk},
            remetente_id    INTEGER NOT NULL,
            destinatario_id INTEGER NOT NULL,
            assunto         TEXT NOT NULL DEFAULT '',
            corpo           TEXT NOT NULL,
            lida            INTEGER NOT NULL DEFAULT 0,
            criado_em       TEXT NOT NULL,
            tipo            TEXT NOT NULL DEFAULT 'mensagem'
        )""",
        """CREATE TABLE IF NOT EXISTS campanhas_vacinacao (
            id              {pk},
            vet_id          INTEGER NOT NULL,
            nome            TEXT NOT NULL,
            vacina          TEXT NOT NULL,
            safra           TEXT NOT NULL,
            data_inicio     TEXT NOT NULL,
            data_fim        TEXT NOT NULL,
            meta_cobertura  REAL NOT NULL DEFAULT 100,
            status          TEXT NOT NULL DEFAULT 'ativa',
            observacoes     TEXT DEFAULT '',
            criado_em       TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS campanha_lotes (
            id              {pk},
            campanha_id     INTEGER NOT NULL,
            lote_id         INTEGER NOT NULL,
            meta_animais    INTEGER NOT NULL DEFAULT 0,
            vacinados       INTEGER NOT NULL DEFAULT 0,
            status          TEXT NOT NULL DEFAULT 'pendente',
            data_execucao   TEXT DEFAULT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS fazendas_coords (
            id              {pk},
            owner_id        INTEGER NOT NULL UNIQUE,
            latitude        REAL NOT NULL,
            longitude       REAL NOT NULL,
            cidade          TEXT DEFAULT '',
            estado          TEXT DEFAULT ''
        )""",
    ]),
    (5, "colunas_extras_vacinas_agenda", [
        "ALTER TABLE vacinas_agenda ADD COLUMN IF NOT EXISTS medicamento_id INTEGER DEFAULT NULL",
        "ALTER TABLE vacinas_agenda ADD COLUMN IF NOT EXISTS quantidade_dose REAL DEFAULT 0",
        "ALTER TABLE vacinas_agenda ADD COLUMN IF NOT EXISTS agendado_por INTEGER DEFAULT NULL",
        "ALTER TABLE vacinas_agenda ADD COLUMN IF NOT EXISTS confirmado_por INTEGER DEFAULT NULL",
        "ALTER TABLE vacinas_agenda ADD COLUMN IF NOT EXISTS animal_id INTEGER DEFAULT NULL",
    ]),
    (6, "coluna_crmv_usuarios", [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS crmv TEXT DEFAULT NULL",
    ]),
    (7, "planos_e_notificacoes", [
        # Colunas de plano na tabela usuarios
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS plano TEXT DEFAULT 'free'",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS plano_nome TEXT DEFAULT 'Free'",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS plano_expira TEXT DEFAULT NULL",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS limite_animais INTEGER DEFAULT 50",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS limite_fazendas INTEGER DEFAULT 1",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS trial_inicio TEXT DEFAULT NULL",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS status_conta TEXT DEFAULT 'ativo'",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS onboarding_completo INTEGER DEFAULT 0",
        # Tabela de log de emails
        """CREATE TABLE IF NOT EXISTS email_log (
            id              {pk},
            destinatario    TEXT NOT NULL,
            assunto         TEXT NOT NULL,
            corpo           TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pendente',
            erro            TEXT DEFAULT NULL,
            criado_em       TEXT NOT NULL,
            enviado_em      TEXT DEFAULT NULL
        )""",
        # Tabela de configuracoes do sistema
        """CREATE TABLE IF NOT EXISTS config_sistema (
            chave  TEXT PRIMARY KEY,
            valor  TEXT NOT NULL,
            tipo   TEXT NOT NULL DEFAULT 'string',
            descricao TEXT DEFAULT ''
        )""",
    ]),
    (8, "onboarding_steps", [
        """CREATE TABLE IF NOT EXISTS onboarding_log (
            id          {pk},
            user_id     INTEGER NOT NULL,
            passo       TEXT NOT NULL,
            completo    INTEGER NOT NULL DEFAULT 0,
            criado_em   TEXT NOT NULL
        )""",
    ]),
    (10, "admin_painel", [
        # Log de acessos para rastrear usuarios ativos
        """CREATE TABLE IF NOT EXISTS access_log (
            id          {pk},
            user_id     INTEGER NOT NULL,
            rota        TEXT NOT NULL DEFAULT '',
            ip          TEXT DEFAULT '',
            criado_em   TEXT NOT NULL
        )""",
        # Ajuste manual de MRR
        """CREATE TABLE IF NOT EXISTS mrr_ajustes (
            id          {pk},
            mes_ref     TEXT NOT NULL,
            valor       REAL NOT NULL DEFAULT 0,
            descricao   TEXT DEFAULT '',
            criado_em   TEXT NOT NULL
        )""",
        # Log de erros da aplicacao
        """CREATE TABLE IF NOT EXISTS error_log (
            id          {pk},
            user_id     INTEGER DEFAULT NULL,
            rota        TEXT DEFAULT '',
            mensagem    TEXT NOT NULL,
            stack_trace TEXT DEFAULT '',
            criado_em   TEXT NOT NULL
        )""",
        # Coluna last_login na tabela usuarios
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS last_login TEXT DEFAULT NULL",
    ]),
    (9, "custos_lote_e_dre", [
        """CREATE TABLE IF NOT EXISTS custos_lote (
            id              {pk},
            lote_id         INTEGER NOT NULL,
            categoria       TEXT NOT NULL DEFAULT 'outros',
            descricao       TEXT NOT NULL,
            valor           REAL NOT NULL DEFAULT 0,
            data_lancamento TEXT NOT NULL,
            observacoes     TEXT DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS dre_entradas (
            id          {pk},
            owner_id    INTEGER NOT NULL,
            descricao   TEXT NOT NULL,
            valor       REAL NOT NULL DEFAULT 0,
            categoria   TEXT NOT NULL DEFAULT 'venda',
            data_ref    TEXT NOT NULL,
            lote_id     INTEGER DEFAULT NULL
        )""",
    ]),
    (11, "status_conta_e_last_login", [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS status_conta TEXT DEFAULT 'ativo'",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS last_login TEXT DEFAULT NULL",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT NULL",
    ]),
    (12, "ciclo_venda_lote", [
        "ALTER TABLE lotes ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ATIVO'",
        "ALTER TABLE lotes ADD COLUMN IF NOT EXISTS data_venda TEXT DEFAULT NULL",
        "ALTER TABLE lotes ADD COLUMN IF NOT EXISTS preco_arroba REAL DEFAULT 0",
        "ALTER TABLE lotes ADD COLUMN IF NOT EXISTS peso_venda_total REAL DEFAULT 0",
        "ALTER TABLE lotes ADD COLUMN IF NOT EXISTS frigorifico TEXT DEFAULT NULL",
        "ALTER TABLE lotes ADD COLUMN IF NOT EXISTS gta_numero TEXT DEFAULT NULL",
        "ALTER TABLE lotes ADD COLUMN IF NOT EXISTS obs_venda TEXT DEFAULT NULL",
        "ALTER TABLE lotes ADD COLUMN IF NOT EXISTS receita_venda REAL DEFAULT 0",
    ]),
    (13, "tabela_vendas_animais", [
        "ALTER TABLE custos_lote ADD COLUMN IF NOT EXISTS owner_id INTEGER DEFAULT NULL",
        """CREATE TABLE IF NOT EXISTS vendas_animais (
            id            {pk},
            animal_id     INTEGER NOT NULL,
            lote_id       INTEGER NOT NULL,
            owner_id      INTEGER DEFAULT NULL,
            data_venda    TEXT NOT NULL,
            peso_abate    REAL DEFAULT 0,
            preco_arroba  REAL DEFAULT 0,
            receita       REAL DEFAULT 0,
            frigorifico   TEXT DEFAULT '',
            gta_numero    TEXT DEFAULT '',
            obs           TEXT DEFAULT ''
        )"""
    ]),
]


def _criar_tabela_schema_version():
    """Cria tabela de controle de versao do schema."""
    pk = "SERIAL PRIMARY KEY" if _usar_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS _schema_version (
                version    INTEGER PRIMARY KEY,
                nome       TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
        """)
        conn.commit()


def _versoes_aplicadas():
    """Retorna conjunto de versions ja aplicadas."""
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute("SELECT version FROM _schema_version")
            return {r[0] for r in cur.fetchall()}
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return set()


def _registrar_versao(version, nome):
    """Marca uma migration como aplicada."""
    from datetime import datetime
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO _schema_version (version, nome, applied_at) "
            f"VALUES ({p}, {p}, {p})",
            (version, nome, datetime.utcnow().isoformat())
        )
        conn.commit()


def aplicar_migrations():
    """Aplica todas as migrations pendentes. Chamada uma vez no boot."""
    _criar_tabela_schema_version()
    aplicadas = _versoes_aplicadas()
    pk_type = "SERIAL PRIMARY KEY" if _usar_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"

    n_aplicadas = 0
    for version, nome, sqls in _MIGRATIONS:
        if version in aplicadas:
            continue
        _log_db.info("Aplicando migration %d: %s", version, nome)
        try:
            for sql_template in sqls:
                sql = sql_template.replace("{pk}", pk_type)
                # SQLite nao suporta ADD COLUMN IF NOT EXISTS
                if not _usar_postgres() and "ADD COLUMN IF NOT EXISTS" in sql:
                    sql = sql.replace("ADD COLUMN IF NOT EXISTS", "ADD COLUMN")
                try:
                    with _conexao() as conn:
                        cur = conn.cursor()
                        cur.execute(sql)
                        conn.commit()
                except Exception as e:
                    # ALTER TABLE pode falhar se coluna ja existe no SQLite
                    if "ADD COLUMN" in sql.upper() and "duplicate" in str(e).lower():
                        continue
                    if "ADD COLUMN" in sql.upper() and "already exists" in str(e).lower():
                        continue
                    _log_db.warning("SQL falhou em migration %d: %s — %s",
                                   version, sql[:60], e)
            _registrar_versao(version, nome)
            n_aplicadas += 1
            _log_db.info("Migration %d aplicada com sucesso", version)
        except Exception as e:
            _log_db.error("Erro ao aplicar migration %d: %s", version, e)
            raise
    return n_aplicadas


# Compatibilidade retroativa: funcoes antigas viram no-op
# (migrations rodam uma vez no boot, nao precisam mais ser chamadas)
def _garantir_tabelas_vet():
    """No-op apos migrations. Mantida para compatibilidade."""
    pass


def _garantir_colunas_vacinas_agenda():
    """No-op apos migrations. Mantida para compatibilidade."""
    pass


def _garantir_coluna_crmv():
    """No-op apos migrations. Mantida para compatibilidade."""
    pass


def inicializar_banco():
    pg = _usar_postgres()

    # Verificar se banco ja foi inicializado (economiza 23 queries)
    with _conexao() as conn:
        cur = conn.cursor()
        if pg:
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='lotes'")
        else:
            cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='lotes'")
        ja_existe = cur.fetchone()[0] > 0

    if ja_existe:
        # Banco ja inicializado - apenas migrar colunas novas + migrations versionadas
        _migrar_banco()
        try:
            aplicar_migrations()
        except Exception as _e_mig:
            _log_db.error("Falha ao aplicar migrations: %s", _e_mig)
        return

    serial = "SERIAL" if pg else "INTEGER"
    auto   = "" if pg else "AUTOINCREMENT"
    pk     = f"{serial} PRIMARY KEY" if pg else f"INTEGER PRIMARY KEY {auto}"

    with _conexao() as conn:
        cur = conn.cursor()

        tabelas = f"""
            CREATE TABLE IF NOT EXISTS lotes (
                id            {pk},
                nome          TEXT    NOT NULL,
                descricao     TEXT    DEFAULT '',
                data_entrada  TEXT    NOT NULL,
                qtd_comprada  INTEGER NOT NULL DEFAULT 0,
                qtd_recebida  INTEGER NOT NULL DEFAULT 0,
                transporte    TEXT    DEFAULT '',
                tipo_alimentacao TEXT DEFAULT 'Pasto',
                tipo_dieta    TEXT DEFAULT 'Capim',
                preco_por_animal REAL DEFAULT 0,
                fazenda_id    INTEGER DEFAULT NULL,
                data_venda    TEXT DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS animais (
                id            {pk},
                identificacao TEXT    NOT NULL,
                idade         INTEGER NOT NULL DEFAULT 0,
                lote_id       INTEGER NOT NULL,
                sexo          TEXT    DEFAULT 'indefinido',
                raca          TEXT    DEFAULT '',
                peso_entrada  REAL    DEFAULT 0,
                peso_alvo     REAL    DEFAULT 0,
                observacoes   TEXT    DEFAULT '',
                foto_path     TEXT    DEFAULT NULL,
                ativo         INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS pesagens (
                id        {pk},
                animal_id INTEGER NOT NULL,
                peso      REAL    NOT NULL,
                data      TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ocorrencias (
                id               {pk},
                animal_id        INTEGER NOT NULL,
                data             TEXT    NOT NULL,
                tipo             TEXT    NOT NULL,
                descricao        TEXT    DEFAULT '',
                gravidade        TEXT    NOT NULL DEFAULT 'Baixa',
                custo            REAL    DEFAULT 0.0,
                dias_recuperacao INTEGER DEFAULT 0,
                status           TEXT    NOT NULL DEFAULT 'Em tratamento'
            );
            CREATE TABLE IF NOT EXISTS fazendas (
                id     {pk},
                nome   TEXT NOT NULL,
                cidade TEXT DEFAULT '',
                estado TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS usuarios (
                id         {pk},
                nome       TEXT NOT NULL,
                email      TEXT NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL,
                salt       TEXT NOT NULL,
                perfil     TEXT NOT NULL DEFAULT 'fazendeiro',
                fazenda_id INTEGER DEFAULT NULL,
                ativo      INTEGER NOT NULL DEFAULT 1,
                trial_inicio TEXT DEFAULT NULL,
                plano        TEXT DEFAULT 'trial',
                plano_expira TEXT DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS vacinas_agenda (
                id             {pk},
                lote_id        INTEGER NOT NULL,
                nome_vacina    TEXT    NOT NULL,
                data_prevista  TEXT    NOT NULL,
                data_realizada TEXT    DEFAULT NULL,
                status         TEXT    NOT NULL DEFAULT 'pendente',
                observacao     TEXT    DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS medicamentos (
                id             {pk},
                nome           TEXT NOT NULL,
                unidade        TEXT NOT NULL DEFAULT 'dose',
                estoque_atual  REAL NOT NULL DEFAULT 0,
                estoque_minimo REAL NOT NULL DEFAULT 0,
                validade       TEXT DEFAULT NULL,
                custo_unitario REAL NOT NULL DEFAULT 0.0,
                carencia_dias  INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS medicamentos_uso (
                id             {pk},
                medicamento_id INTEGER NOT NULL,
                animal_id      INTEGER NOT NULL,
                ocorrencia_id  INTEGER DEFAULT NULL,
                data_uso       TEXT NOT NULL,
                quantidade     REAL NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS reproducao (
                id                  {pk},
                animal_id           INTEGER NOT NULL,
                data_cio            TEXT    DEFAULT NULL,
                tipo_cobertura      TEXT    NOT NULL DEFAULT 'IATF',
                data_diagnostico    TEXT    DEFAULT NULL,
                resultado           TEXT    DEFAULT 'pendente',
                data_parto_previsto TEXT    DEFAULT NULL,
                data_parto_real     TEXT    DEFAULT NULL,
                observacao          TEXT    DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS piquetes (
                id            {pk},
                fazenda_id    INTEGER DEFAULT NULL,
                nome          TEXT NOT NULL,
                area_ha       REAL DEFAULT 0,
                capacidade_ua REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS piquetes_historico (
                id         {pk},
                piquete_id INTEGER NOT NULL,
                lote_id    INTEGER NOT NULL,
                entrada    TEXT NOT NULL,
                saida      TEXT DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS mortalidade (
                id          {pk},
                animal_id   INTEGER NOT NULL,
                data        TEXT NOT NULL,
                causa       TEXT NOT NULL DEFAULT 'Doenca',
                descricao   TEXT DEFAULT '',
                custo_perda REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS auditoria (
                id          {pk},
                usuario_id  INTEGER NOT NULL,
                acao        TEXT NOT NULL,
                tabela      TEXT DEFAULT '',
                registro_id INTEGER DEFAULT NULL,
                detalhe     TEXT DEFAULT '',
                data_hora   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS gta (
                id            {pk},
                lote_id       INTEGER NOT NULL,
                numero_gta    TEXT NOT NULL,
                data_emissao  TEXT NOT NULL,
                origem        TEXT DEFAULT '',
                destino       TEXT DEFAULT '',
                quantidade    INTEGER DEFAULT 0,
                finalidade    TEXT DEFAULT 'Abate',
                observacao    TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS sisbov (
                id                 {pk},
                animal_id          INTEGER NOT NULL UNIQUE,
                numero_sisbov      TEXT NOT NULL,
                data_certificacao  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS vendas_lote (
                id             {pk},
                lote_id        INTEGER NOT NULL,
                data_venda     TEXT NOT NULL,
                preco_venda_kg REAL NOT NULL DEFAULT 0,
                peso_total_kg  REAL NOT NULL DEFAULT 0,
                frigorific     TEXT DEFAULT '',
                observacao     TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS cotacoes (
                id     {pk},
                data   TEXT NOT NULL UNIQUE,
                preco  REAL NOT NULL,
                fonte  TEXT DEFAULT 'manual'
            );
        """

        for stmt in tabelas.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)

        conn.commit()

    # Aplicar migrations versionadas
    try:
        aplicar_migrations()
    except Exception as _e_mig:
        _log_db.error("Falha ao aplicar migrations no boot: %s", _e_mig)
    print("Banco inicializado com sucesso.")
    _migrar_banco()
    _garantir_colunas_vacinas_agenda()
    _garantir_coluna_crmv()
    _garantir_tabelas_vet()


def _migrar_banco():
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                "SELECT table_name, column_name FROM information_schema.columns"
                " WHERE table_schema='public' AND table_name IN"
                " ('lotes','animais','movimentacoes_animais','usuarios')"
            )
            rows = cur.fetchall()
            existentes = {(r[0], r[1]) for r in rows}

            if ('movimentacoes_animais','id') not in existentes:
                cur.execute("""CREATE TABLE IF NOT EXISTS movimentacoes_animais (
                    id SERIAL PRIMARY KEY, animal_id INTEGER NOT NULL,
                    lote_origem INTEGER NOT NULL, lote_destino INTEGER NOT NULL,
                    data TEXT NOT NULL, motivo TEXT DEFAULT '', usuario_id INTEGER DEFAULT NULL
                )""")

            # Colunas de isolamento e status
            for tabela, coluna, definicao in [
                ('lotes',    'status',      "TEXT DEFAULT 'ATIVO'"),
                ('lotes',    'ativo',       'INTEGER DEFAULT 1'),
                ('lotes',    'deletado_em', 'TEXT DEFAULT NULL'),
                ('lotes',    'owner_id',    'INTEGER DEFAULT NULL'),
                ('animais',  'status',      "TEXT DEFAULT 'ATIVO'"),
                ('animais',  'deletado_em', 'TEXT DEFAULT NULL'),
                ('usuarios', 'owner_id',    'INTEGER DEFAULT NULL'),
                ('medicamentos', 'owner_id',    'INTEGER DEFAULT NULL'),
            ]:
                if (tabela, coluna) not in existentes:
                    try:
                        cur.execute(
                            f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS {coluna} {definicao}"
                        )
                    except Exception as _ew:
                        _log_war.debug("excecao ignorada: %s", _ew)
        else:
            for tabela, coluna, definicao in [
                ('lotes',    'status',      "TEXT DEFAULT 'ATIVO'"),
                ('lotes',    'ativo',       'INTEGER DEFAULT 1'),
                ('lotes',    'deletado_em', 'TEXT DEFAULT NULL'),
                ('lotes',    'owner_id',    'INTEGER DEFAULT NULL'),
                ('animais',  'status',      "TEXT DEFAULT 'ATIVO'"),
                ('animais',  'deletado_em', 'TEXT DEFAULT NULL'),
                ('usuarios', 'owner_id',    'INTEGER DEFAULT NULL'),
                ('medicamentos', 'owner_id',    'INTEGER DEFAULT NULL'),
            ]:
                try:
                    cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
                except Exception as _ew:
                    _log_war.debug("excecao ignorada: %s", _ew)
            cur.execute("""CREATE TABLE IF NOT EXISTS movimentacoes_animais (
                id INTEGER PRIMARY KEY AUTOINCREMENT, animal_id INTEGER NOT NULL,
                lote_origem INTEGER NOT NULL, lote_destino INTEGER NOT NULL,
                data TEXT NOT NULL, motivo TEXT DEFAULT '', usuario_id INTEGER DEFAULT NULL
            )""")
        conn.commit()

        # Tabela de acesso veterinario-fazenda
        if _usar_postgres():
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vet_fazenda_acesso (
                    id            SERIAL PRIMARY KEY,
                    vet_id        INTEGER NOT NULL,
                    owner_id      INTEGER NOT NULL,
                    status        TEXT NOT NULL DEFAULT 'pendente',
                    aprovado_por  INTEGER DEFAULT NULL,
                    data_request  TEXT NOT NULL,
                    data_aprovacao TEXT DEFAULT NULL,
                    UNIQUE(vet_id, owner_id)
                )
            """)
            for col, defn in [
                ('plano_nome',      "TEXT DEFAULT 'trial'"),
                ('limite_animais',  'INTEGER DEFAULT 50'),
                ('limite_fazendas', 'INTEGER DEFAULT 2'),
                ('status_conta',    "TEXT DEFAULT 'pendente'"),
            ]:
                try:
                    cur.execute(
                        f"ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS {col} {defn}"
                    )
                except Exception as _ew:
                    _log_war.debug("excecao ignorada: %s", _ew)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vet_fazenda_acesso (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    vet_id        INTEGER NOT NULL,
                    owner_id      INTEGER NOT NULL,
                    status        TEXT NOT NULL DEFAULT 'pendente',
                    aprovado_por  INTEGER DEFAULT NULL,
                    data_request  TEXT NOT NULL,
                    data_aprovacao TEXT DEFAULT NULL,
                    UNIQUE(vet_id, owner_id)
                )
            """)
            for col, defn in [
                ('plano_nome',      "TEXT DEFAULT 'trial'"),
                ('limite_animais',  'INTEGER DEFAULT 50'),
                ('limite_fazendas', 'INTEGER DEFAULT 2'),
                ('status_conta',    "TEXT DEFAULT 'pendente'"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {defn}")
                except Exception as _ew:
                    _log_war.debug("excecao ignorada: %s", _ew)
        conn.commit()
