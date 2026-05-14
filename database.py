# database.py -- Camada de persistencia do Sistema de Gestao Pecuaria
# Suporta PostgreSQL (Supabase) e SQLite (fallback local)

import os
import hashlib
import secrets
from contextlib import contextmanager
from datetime import date as _date, timedelta as _td

# ── Planos do sistema ───────────────────────────────────────────────────────
PLANOS_FAZENDEIRO = {
    'trial':      dict(nome='Trial 30 dias',  limite_animais=50,   preco=0),
    'pequeno':    dict(nome='Pequeno',         limite_animais=50,   preco=39),
    'medio':      dict(nome='Medio',           limite_animais=200,  preco=79),
    'grande':     dict(nome='Grande',          limite_animais=500,  preco=139),
    'enterprise': dict(nome='Enterprise',      limite_animais=9999, preco=199),
}
PLANOS_VETERINARIO = {
    'trial':        dict(nome='Trial 30 dias', limite_fazendas=2,   preco=0),
    'starter':      dict(nome='Starter',       limite_fazendas=5,   preco=49),
    'profissional': dict(nome='Profissional',  limite_fazendas=10,  preco=89),
    'expert':       dict(nome='Expert',        limite_fazendas=20,  preco=149),
    'ilimitado':    dict(nome='Ilimitado',     limite_fazendas=999, preco=249),
}

# ── Detectar qual banco usar ────────────────────────────────────────────────
def _usar_postgres():
    try:
        import psycopg2
    except ImportError:
        return False
    try:
        import streamlit as st
        db = st.secrets.get("database", {})
        url = db.get("url", "")
        return url.startswith("postgresql://") or url.startswith("postgres://")
    except Exception:
        return False

def _diagnostico_banco():
    try:
        import psycopg2
        psycopg2_ok = True
    except ImportError:
        return "psycopg2 NAO instalado - usando SQLite"
    try:
        import streamlit as st
        db = st.secrets.get("database", {})
        url = db.get("url", "")
        if not url:
            return "Secret [database][url] nao encontrado - usando SQLite"
        if not (url.startswith("postgresql://") or url.startswith("postgres://")):
            return f"URL invalida: {url[:30]}... - usando SQLite"
        return f"PostgreSQL OK: {url[:40]}..."
    except Exception as e:
        return f"Erro ao ler secrets: {e} - usando SQLite"

def _get_pg_url():
    try:
        import streamlit as st
        return st.secrets["database"]["url"]
    except Exception:
        return os.environ.get("DATABASE_URL", "")

def _date_add(dias, sinal="+"):
    if _usar_postgres():
        op = "+" if sinal == "+" else "-"
        return f"CURRENT_DATE {op} INTERVAL '{abs(dias)} days'"
    else:
        op = "+" if sinal == "+" else "-"
        return f"date('now','{op}{abs(dias)} days')"

def _cast_date(campo):
    # No PostgreSQL campos TEXT precisam de cast para comparar com datas
    if _usar_postgres():
        return f"({campo})::date"
    else:
        return f"date({campo})"

# ── Conexao ─────────────────────────────────────────────────────────────────
# Pool de conexoes para PostgreSQL (reutiliza conexoes em vez de abrir/fechar)
_pg_pool = None

def _get_pool():
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    try:
        import psycopg2.pool
        url = _get_pg_url()
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(1, 5, url, connect_timeout=15)
        return _pg_pool
    except Exception:
        return None

@contextmanager
def _conexao():
    if _usar_postgres():
        import psycopg2
        pool = _get_pool()
        if pool:
            conn = pool.getconn()
            conn.autocommit = False
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                pool.putconn(conn)
        else:
            # Fallback sem pool
            url = _get_pg_url()
            conn = psycopg2.connect(url, connect_timeout=15)
            conn.autocommit = False
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    else:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pecuaria.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

def _ph():
    # placeholder: %s para postgres, ? para sqlite
    return "%s" if _usar_postgres() else "?"

def _fetch(cur):
    # normalizar rows para list of dicts/tuples
    rows = cur.fetchall()
    if not rows:
        return []
    if _usar_postgres():
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    else:
        return [dict(row) for row in rows]

def _fetchone(cur):
    row = cur.fetchone()
    if not row:
        return None
    if _usar_postgres():
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    else:
        return dict(row)

# ── Inicializar banco ────────────────────────────────────────────────────────
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
        # Banco ja inicializado - apenas migrar colunas novas
        _migrar_banco()
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
    print("Banco inicializado com sucesso.")
    _migrar_banco()


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
                    except Exception:
                        pass
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
                except Exception:
                    pass
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
                except Exception:
                    pass
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
                except Exception:
                    pass
        conn.commit()


# ── LOTES ────────────────────────────────────────────────────────────────────
def adicionar_lote(nome, descricao, data_entrada, qtd_comprada, qtd_recebida, transporte, owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO lotes (nome,descricao,data_entrada,qtd_comprada,qtd_recebida,transporte,owner_id)"
                f" VALUES({p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (nome, descricao, data_entrada, qtd_comprada, qtd_recebida, transporte, owner_id),
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO lotes (nome,descricao,data_entrada,qtd_comprada,qtd_recebida,transporte,owner_id)"
                f" VALUES({p},{p},{p},{p},{p},{p},{p})",
                (nome, descricao, data_entrada, qtd_comprada, qtd_recebida, transporte, owner_id),
            )
            return cur.lastrowid

def listar_lotes(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if owner_id is not None:
            # Comparacao direta: so retorna lotes onde owner_id = valor exato
            # Nao usa COALESCE para evitar que lotes sem owner_id vazem
            cur.execute(
                f"SELECT id,nome,descricao,data_entrada,qtd_comprada,qtd_recebida,transporte"
                f" FROM lotes WHERE owner_id={p}"
                f" ORDER BY data_entrada DESC,id DESC",
                (owner_id,),
            )
        else:
            cur.execute(
                "SELECT id,nome,descricao,data_entrada,qtd_comprada,qtd_recebida,transporte"
                " FROM lotes ORDER BY data_entrada DESC,id DESC"
            )
        rows = _fetch(cur)
        return [(r["id"],r["nome"],r["descricao"],r["data_entrada"],r["qtd_comprada"],r["qtd_recebida"],r["transporte"]) for r in rows]

def obter_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id,nome,descricao,data_entrada,qtd_comprada,qtd_recebida,transporte FROM lotes WHERE id={p}", (lote_id,))
        r = _fetchone(cur)
        return (r["id"],r["nome"],r["descricao"],r["data_entrada"],r["qtd_comprada"],r["qtd_recebida"],r["transporte"]) if r else None

def atualizar_lote(lote_id, nome, descricao, data_entrada, qtd_comprada, qtd_recebida, transporte, preco_por_animal=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1", (lote_id,))
        ativos = cur.fetchone()[0]
        cur.execute(
            f"UPDATE lotes SET nome={p},descricao={p},data_entrada={p},qtd_comprada={p},qtd_recebida={p},transporte={p} WHERE id={p}",
            (nome, descricao, data_entrada, qtd_comprada, ativos, transporte, lote_id),
        )
        if preco_por_animal is not None:
            cur.execute(f"UPDATE lotes SET preco_por_animal={p} WHERE id={p}", (preco_por_animal, lote_id))

def excluir_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM lotes WHERE id={p}", (lote_id,))


# ── ANIMAIS ──────────────────────────────────────────────────────────────────
def adicionar_animal(identificacao, idade, lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO animais (identificacao,idade,lote_id) VALUES({p},{p},{p}) RETURNING id",
                (identificacao, idade, lote_id),
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO animais (identificacao,idade,lote_id) VALUES({p},{p},{p})",
                (identificacao, idade, lote_id),
            )
            return cur.lastrowid

def listar_animais(incluir_inativos=False):
    with _conexao() as conn:
        cur = conn.cursor()
        sql = "SELECT id,identificacao,idade,lote_id FROM animais"
        if not incluir_inativos:
            sql += " WHERE COALESCE(ativo,1)=1"
        sql += " ORDER BY id"
        cur.execute(sql)
        rows = _fetch(cur)
        return [(r["id"],r["identificacao"],r["idade"],r["lote_id"]) for r in rows]

def listar_animais_por_lote(lote_id, incluir_inativos=False):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if incluir_inativos:
            cur.execute(f"SELECT id,identificacao,idade,lote_id FROM animais WHERE lote_id={p} ORDER BY id", (lote_id,))
        else:
            cur.execute(f"SELECT id,identificacao,idade,lote_id FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1 ORDER BY id", (lote_id,))
        rows = _fetch(cur)
        return [(r["id"],r["identificacao"],r["idade"],r["lote_id"]) for r in rows]

def contar_animais_no_lote(lote_id, incluir_inativos=False):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if incluir_inativos:
            cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p}", (lote_id,))
        else:
            cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1", (lote_id,))
        return cur.fetchone()[0]

def atualizar_animal_detalhes(animal_id, peso_alvo=None, observacoes=None, foto_path=None):
    p = _ph()
    campos, vals = [], []
    if peso_alvo   is not None: campos.append(f"peso_alvo={p}");   vals.append(peso_alvo)
    if observacoes is not None: campos.append(f"observacoes={p}"); vals.append(observacoes)
    if foto_path   is not None: campos.append(f"foto_path={p}");   vals.append(foto_path)
    if not campos: return
    vals.append(animal_id)
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE animais SET {', '.join(campos)} WHERE id={p}", vals)

def obter_animal(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,identificacao,idade,lote_id,"
            f"COALESCE(sexo,'indefinido') as sexo,COALESCE(raca,'') as raca,"
            f"COALESCE(peso_entrada,0) as peso_entrada,COALESCE(peso_alvo,0) as peso_alvo,"
            f"COALESCE(observacoes,'') as observacoes,foto_path FROM animais WHERE id={p}",
            (animal_id,),
        )
        r = _fetchone(cur)
        return (r["id"],r["identificacao"],r["idade"],r["lote_id"],r["sexo"],r["raca"],r["peso_entrada"],r["peso_alvo"],r["observacoes"],r["foto_path"]) if r else None

def atualizar_animal(animal_id, identificacao, idade):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE animais SET identificacao={p},idade={p} WHERE id={p}", (identificacao, idade, animal_id))

def excluir_animal(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM animais WHERE id={p}", (animal_id,))


# ── PESAGENS ─────────────────────────────────────────────────────────────────
# Status válidos para animais
STATUS_ANIMAL = ['ATIVO', 'VENDIDO', 'MORTO', 'TRANSFERIDO', 'DESCARTADO']

def atualizar_status_animal(animal_id, status):
    p = _ph()
    ativo = 1 if status == 'ATIVO' else 0
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE animais SET status={p}, ativo={p} WHERE id={p}",
            (status, ativo, animal_id),
        )

def listar_animais_por_status(lote_id, status=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if status:
            cur.execute(
                f"SELECT id,identificacao,idade,lote_id,COALESCE(status,'ATIVO') as status"
                f" FROM animais WHERE lote_id={p} AND COALESCE(status,'ATIVO')={p} ORDER BY id",
                (lote_id, status),
            )
        else:
            cur.execute(
                f"SELECT id,identificacao,idade,lote_id,COALESCE(status,'ATIVO') as status"
                f" FROM animais WHERE lote_id={p} ORDER BY id",
                (lote_id,),
            )
        rows = _fetch(cur)
        return [(r['id'],r['identificacao'],r['idade'],r['lote_id'],r['status']) for r in rows]

def contagem_status_animais(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COALESCE(status,'ATIVO') as status, COUNT(*) as total"
            f" FROM animais WHERE lote_id={p} GROUP BY COALESCE(status,'ATIVO')",
            (lote_id,),
        )
        rows = _fetch(cur)
        base = {s: 0 for s in STATUS_ANIMAL}
        for r in rows:
            base[r['status']] = r['total']
        return base


# Status válidos para lotes
STATUS_LOTE = ['ATIVO', 'ENCERRADO', 'QUARENTENA', 'VENDIDO', 'CRITICO']

def atualizar_status_lote(lote_id, status):
    p = _ph()
    ativo = 1 if status == 'ATIVO' else 0
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE lotes SET status={p}, ativo={p} WHERE id={p}",
            (status, ativo, lote_id),
        )

def listar_lotes_por_status(status=None, owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        base = (
            "SELECT id,nome,descricao,data_entrada,qtd_comprada,qtd_recebida,transporte,"
            "COALESCE(status,'ATIVO') as status FROM lotes WHERE 1=1"
        )
        params = []
        if owner_id is not None:
            base += f" AND owner_id={p}"
            params += [owner_id]
        if status:
            base += f" AND COALESCE(status,'ATIVO')={p}"
            params.append(status)
        base += " ORDER BY data_entrada DESC"
        cur.execute(base, params)
        rows = _fetch(cur)
        return [(r['id'],r['nome'],r['descricao'],r['data_entrada'],
                 r['qtd_comprada'],r['qtd_recebida'],r['transporte'],r['status']) for r in rows]


def adicionar_pesagem(animal_id, peso, data):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO pesagens (animal_id,peso,data) VALUES({p},{p},{p}) RETURNING id", (animal_id, peso, data))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO pesagens (animal_id,peso,data) VALUES({p},{p},{p})", (animal_id, peso, data))
            return cur.lastrowid

def listar_pesagens(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id,animal_id,peso,data FROM pesagens WHERE animal_id={p} ORDER BY data ASC,id ASC", (animal_id,))
        rows = _fetch(cur)
        return [(r["id"],r["animal_id"],r["peso"],r["data"]) for r in rows]

def atualizar_pesagem(pesagem_id, peso, data):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE pesagens SET peso={p},data={p} WHERE id={p}", (peso, data, pesagem_id))

def excluir_pesagem(pesagem_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM pesagens WHERE id={p}", (pesagem_id,))

def listar_pesagens_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT p.id,a.lote_id,p.peso,p.data,a.identificacao,a.id as animal_id FROM pesagens p JOIN animais a ON a.id=p.animal_id WHERE a.lote_id={p} ORDER BY p.data ASC",
            (lote_id,),
        )
        rows = _fetch(cur)
        return [(r["id"],r["lote_id"],r["peso"],r["data"],r["identificacao"],r["animal_id"]) for r in rows]


# ── OCORRENCIAS ──────────────────────────────────────────────────────────────
def adicionar_ocorrencia(animal_id, data, tipo, descricao, gravidade, custo, dias_recuperacao, status):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO ocorrencias (animal_id,data,tipo,descricao,gravidade,custo,dias_recuperacao,status) VALUES({p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (animal_id, data, tipo, descricao, gravidade, custo, dias_recuperacao, status),
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO ocorrencias (animal_id,data,tipo,descricao,gravidade,custo,dias_recuperacao,status) VALUES({p},{p},{p},{p},{p},{p},{p},{p})",
                (animal_id, data, tipo, descricao, gravidade, custo, dias_recuperacao, status),
            )
            return cur.lastrowid

def listar_ocorrencias(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,animal_id,data,tipo,descricao,gravidade,custo,dias_recuperacao,status FROM ocorrencias WHERE animal_id={p} ORDER BY data ASC,id ASC",
            (animal_id,),
        )
        rows = _fetch(cur)
        return [(r["id"],r["animal_id"],r["data"],r["tipo"],r["descricao"],r["gravidade"],r["custo"],r["dias_recuperacao"],r["status"]) for r in rows]

def atualizar_ocorrencia(ocorrencia_id, tipo, descricao, gravidade, custo, dias_recuperacao, status, data=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if data:
            cur.execute(
                f"UPDATE ocorrencias SET tipo={p},descricao={p},gravidade={p},custo={p},dias_recuperacao={p},status={p},data={p} WHERE id={p}",
                (tipo, descricao, gravidade, custo, dias_recuperacao, status, data, ocorrencia_id),
            )
        else:
            cur.execute(
                f"UPDATE ocorrencias SET tipo={p},descricao={p},gravidade={p},custo={p},dias_recuperacao={p},status={p} WHERE id={p}",
                (tipo, descricao, gravidade, custo, dias_recuperacao, status, ocorrencia_id),
            )

def excluir_ocorrencia(ocorrencia_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM ocorrencias WHERE id={p}", (ocorrencia_id,))

def listar_ocorrencias_em_tratamento():
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT o.id,o.animal_id,a.identificacao,l.nome,o.data,o.tipo,o.descricao,o.gravidade,o.custo,o.dias_recuperacao,o.status"
            " FROM ocorrencias o JOIN animais a ON a.id=o.animal_id JOIN lotes l ON l.id=a.lote_id"
            " WHERE o.status='Em tratamento' ORDER BY o.data ASC"
        )
        rows = _fetch(cur)
        return [tuple(r.values()) for r in rows]

def listar_tratamentos_vencidos(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        hoje = str(_date.today())
        filtro_owner = f" AND l.owner_id={p}" if owner_id is not None else ""
        params = (owner_id,) if owner_id is not None else ()
        cur.execute(
            "SELECT o.id,o.animal_id,a.identificacao,l.nome,o.data,o.tipo,o.descricao,o.gravidade,o.custo,o.dias_recuperacao,o.status"
            " FROM ocorrencias o JOIN animais a ON a.id=o.animal_id JOIN lotes l ON l.id=a.lote_id"
            f" WHERE o.status='Em tratamento' AND o.dias_recuperacao > 0{filtro_owner}",
            params,
        )
        rows = _fetch(cur)
        import datetime
        vencidos = []
        for r in rows:
            try:
                dt_oc = datetime.datetime.strptime(str(r["data"])[:10], "%Y-%m-%d").date()
                dt_alta = dt_oc + datetime.timedelta(days=int(r["dias_recuperacao"] or 0))
                if dt_alta < _date.today():
                    vencidos.append(tuple(r.values()))
            except Exception:
                pass
        return vencidos


# ── USUARIOS ─────────────────────────────────────────────────────────────────
def _hash_senha(senha, salt):
    return hashlib.sha256((salt + senha).encode()).hexdigest()

def criar_usuario(nome, email, senha, perfil="fazendeiro", fazenda_id=None, owner_id=None):
    p = _ph()
    salt = secrets.token_hex(16)
    h = _hash_senha(senha, salt)
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO usuarios (nome,email,senha_hash,salt,perfil,fazenda_id,owner_id)"
                f" VALUES({p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (nome, email, h, salt, perfil, fazenda_id, owner_id),
            )
            uid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO usuarios (nome,email,senha_hash,salt,perfil,fazenda_id,owner_id)"
                f" VALUES({p},{p},{p},{p},{p},{p},{p})",
                (nome, email, h, salt, perfil, fazenda_id, owner_id),
            )
            uid = cur.lastrowid
        # Se nao tem owner_id definido (primeiro admin), ele e dono de si mesmo
        if owner_id is None and perfil == 'admin':
            cur.execute(f"UPDATE usuarios SET owner_id={p} WHERE id={p}", (uid, uid))
        return uid

def autenticar_usuario(email, senha):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id,nome,email,senha_hash,salt,perfil,fazenda_id,ativo,COALESCE(owner_id,id) as owner_id FROM usuarios WHERE email={p}", (email,))
        r = _fetchone(cur)
    if not r or not r["ativo"]: return None
    if _hash_senha(senha, r["salt"]) != r["senha_hash"]: return None
    owner = r.get("owner_id") or r["id"]
    return dict(id=r["id"], nome=r["nome"], email=r["email"],
                perfil=r["perfil"], fazenda_id=r["fazenda_id"],
                owner_id=owner)

def listar_usuarios():
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id,nome,email,perfil,fazenda_id FROM usuarios WHERE ativo=1 ORDER BY nome")
        rows = _fetch(cur)
        return [(r["id"],r["nome"],r["email"],r["perfil"],r["fazenda_id"]) for r in rows]

def usuario_existe():
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM usuarios")
        return cur.fetchone()[0] > 0

def alterar_senha(usuario_id, nova_senha):
    p = _ph()
    salt = secrets.token_hex(16)
    h = _hash_senha(nova_senha, salt)
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE usuarios SET senha_hash={p},salt={p} WHERE id={p}", (h, salt, usuario_id))


# ── TRIAL / PLANO ─────────────────────────────────────────────────────────────
TRIAL_DIAS = 30

def ativar_trial(usuario_id):
    p = _ph()
    hoje   = str(_date.today())
    expira = str(_date.today() + _td(days=TRIAL_DIAS))
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE usuarios SET trial_inicio={p},plano='trial',plano_expira={p} WHERE id={p}", (hoje, expira, usuario_id))

def obter_status_plano(usuario_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT plano,trial_inicio,plano_expira,ativo FROM usuarios WHERE id={p}", (usuario_id,))
        r = _fetchone(cur)
    if not r:
        return dict(plano="expirado", dias_restantes=0, trial_inicio=None, plano_expira=None, pode_exportar=False, ativo=False)
    plano        = r["plano"] or "trial"
    trial_inicio = r["trial_inicio"]
    plano_expira = r["plano_expira"]
    ativo        = bool(r["ativo"])
    hoje = _date.today()
    if plano == "trial" and not trial_inicio:
        ativar_trial(usuario_id)
        trial_inicio = str(hoje)
        plano_expira = str(hoje + _td(days=TRIAL_DIAS))
    dias_restantes = (_date.fromisoformat(str(plano_expira)[:10]) - hoje).days if plano_expira else 0
    if plano == "pago":
        status, pode_exportar = "pago", True
    elif dias_restantes > 0:
        status, pode_exportar = "trial", False
    else:
        status, pode_exportar = "expirado", False
    return dict(plano=status, dias_restantes=dias_restantes, trial_inicio=trial_inicio,
                plano_expira=plano_expira, pode_exportar=pode_exportar, ativo=ativo)

def converter_para_pago(usuario_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE usuarios SET plano='pago',plano_expira=NULL WHERE id={p}", (usuario_id,))

def listar_usuarios_trial_expirando(dias=7):
    p = _ph()
    limite = str(_date.today() + _td(days=dias))
    hoje   = str(_date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,nome,email,plano_expira FROM usuarios WHERE plano='trial' AND plano_expira IS NOT NULL AND plano_expira>={p} AND plano_expira<={p} ORDER BY plano_expira",
            (hoje, limite),
        )
        rows = _fetch(cur)
        return [(r["id"],r["nome"],r["email"],r["plano_expira"]) for r in rows]


# ── PLANOS E VETERINARIO ────────────────────────────────────────────────────

def definir_plano_usuario(usuario_id, perfil, plano_nome, admin_id):
    p = _ph()
    if perfil == 'veterinario':
        cfg = PLANOS_VETERINARIO.get(plano_nome, PLANOS_VETERINARIO['trial'])
        limite_f = cfg['limite_fazendas']
        limite_a = 0
    else:
        cfg = PLANOS_FAZENDEIRO.get(plano_nome, PLANOS_FAZENDEIRO['trial'])
        limite_f = 0
        limite_a = cfg['limite_animais']
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE usuarios SET plano={p}, plano_nome={p},"
            f" limite_animais={p}, limite_fazendas={p},"
            f" status_conta='ativo' WHERE id={p}",
            ('pago', plano_nome, limite_a, limite_f, usuario_id),
        )
        conn.commit()
    registrar_auditoria(admin_id, 'definir_plano', 'usuarios', usuario_id, plano_nome)

def obter_limites_usuario(usuario_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT perfil, plano, COALESCE(plano_nome,'trial') as plano_nome,"
            f" COALESCE(limite_animais,50) as limite_animais,"
            f" COALESCE(limite_fazendas,2) as limite_fazendas,"
            f" COALESCE(status_conta,'pendente') as status_conta"
            f" FROM usuarios WHERE id={p}",
            (usuario_id,),
        )
        return _fetchone(cur)

def verificar_limite_animais(owner_id):
    limites = obter_limites_usuario(owner_id)
    if not limites: return dict(ok=False, atual=0, limite=0, msg='Usuario nao encontrado')
    if limites['perfil'] == 'admin': return dict(ok=True, atual=0, limite=9999, msg='Admin sem limite')
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM animais a JOIN lotes l ON l.id=a.lote_id"
            f" WHERE l.owner_id={p} AND COALESCE(a.ativo,1)=1",
            (owner_id,),
        )
        atual = cur.fetchone()[0]
    limite = limites['limite_animais']
    return dict(ok=atual < limite, atual=atual, limite=limite,
                msg=f'{atual}/{limite} animais' if atual < limite else f'Limite atingido ({limite} animais)')

def verificar_limite_fazendas(vet_id):
    limites = obter_limites_usuario(vet_id)
    if not limites: return dict(ok=False, atual=0, limite=0, msg='Usuario nao encontrado')
    if limites['perfil'] == 'admin': return dict(ok=True, atual=0, limite=9999, msg='Admin sem limite')
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM vet_fazenda_acesso WHERE vet_id={p} AND status='aprovado'",
            (vet_id,),
        )
        atual = cur.fetchone()[0]
    limite = limites['limite_fazendas']
    return dict(ok=atual < limite, atual=atual, limite=limite,
                msg=f'{atual}/{limite} fazendas' if atual < limite else f'Limite atingido ({limite} fazendas)')

# ── Acesso veterinario-fazenda ───────────────────────────────────────────────

def solicitar_acesso_vet(vet_id, owner_id):
    p = _ph()
    from datetime import date as _d
    with _conexao() as conn:
        cur = conn.cursor()
        # Verificar se ja existe
        cur.execute(
            f"SELECT id,status FROM vet_fazenda_acesso WHERE vet_id={p} AND owner_id={p}",
            (vet_id, owner_id),
        )
        existente = _fetchone(cur)
        if existente:
            return dict(ok=False, msg=f'Solicitacao ja existe com status: {existente["status"]}')
        # Verificar limite de fazendas do vet
        lim = verificar_limite_fazendas(vet_id)
        if not lim['ok']:
            return dict(ok=False, msg=lim['msg'])
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO vet_fazenda_acesso (vet_id,owner_id,status,data_request)"
                f" VALUES({p},{p},'pendente',{p}) RETURNING id",
                (vet_id, owner_id, str(_d.today())),
            )
        else:
            cur.execute(
                f"INSERT INTO vet_fazenda_acesso (vet_id,owner_id,status,data_request)"
                f" VALUES({p},{p},'pendente',{p})",
                (vet_id, owner_id, str(_d.today())),
            )
        conn.commit()
    return dict(ok=True, msg='Solicitacao enviada ao administrador')

def aprovar_acesso_vet(vet_id, owner_id, admin_id, aprovar=True):
    p = _ph()
    from datetime import date as _d
    status = 'aprovado' if aprovar else 'rejeitado'
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE vet_fazenda_acesso SET status={p}, aprovado_por={p},"
            f" data_aprovacao={p} WHERE vet_id={p} AND owner_id={p}",
            (status, admin_id, str(_d.today()), vet_id, owner_id),
        )
        conn.commit()
    registrar_auditoria(admin_id, f'acesso_vet_{status}', 'vet_fazenda_acesso', vet_id,
                        f'owner_id={owner_id}')
    return dict(ok=True, msg=f'Acesso {status}')

def revogar_acesso_vet(vet_id, owner_id, admin_id):
    return aprovar_acesso_vet(vet_id, owner_id, admin_id, aprovar=False)

def listar_acessos_vet(vet_id=None, owner_id=None, status=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        sql = (
            "SELECT v.id, v.vet_id, uv.nome as vet_nome, uv.email as vet_email,"
            " v.owner_id, uf.nome as fazenda_nome, uf.email as fazenda_email,"
            " v.status, v.data_request, v.data_aprovacao"
            " FROM vet_fazenda_acesso v"
            " JOIN usuarios uv ON uv.id=v.vet_id"
            " JOIN usuarios uf ON uf.id=v.owner_id"
            " WHERE 1=1"
        )
        params = []
        if vet_id:   sql += f" AND v.vet_id={p}";   params.append(vet_id)
        if owner_id: sql += f" AND v.owner_id={p}"; params.append(owner_id)
        if status:   sql += f" AND v.status={p}";   params.append(status)
        sql += " ORDER BY v.data_request DESC"
        cur.execute(sql, params)
        rows = _fetch(cur)
        return [tuple(r.values()) for r in rows]

def listar_fazendas_do_vet(vet_id):
    # Retorna owner_ids das fazendas aprovadas para o veterinario
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT owner_id FROM vet_fazenda_acesso WHERE vet_id={p} AND status='aprovado'",
            (vet_id,),
        )
        rows = cur.fetchall()
        return [r[0] for r in rows]

def listar_lotes_vet(vet_id):
    # Lotes de todas as fazendas aprovadas para o veterinario
    fazendas = listar_fazendas_do_vet(vet_id)
    if not fazendas:
        return []
    todos = []
    for fid in fazendas:
        todos.extend(listar_lotes(owner_id=fid))
    return todos

def listar_solicitacoes_pendentes():
    return listar_acessos_vet(status='pendente')

def aprovar_conta_usuario(usuario_id, admin_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE usuarios SET status_conta='ativo' WHERE id={p}",
            (usuario_id,),
        )
        conn.commit()
    registrar_auditoria(admin_id, 'aprovar_conta', 'usuarios', usuario_id, 'aprovado')


# ── FAZENDAS ──────────────────────────────────────────────────────────────────
def adicionar_fazenda(nome, cidade="", estado=""):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO fazendas (nome,cidade,estado) VALUES({p},{p},{p}) RETURNING id", (nome, cidade, estado))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO fazendas (nome,cidade,estado) VALUES({p},{p},{p})", (nome, cidade, estado))
            return cur.lastrowid

def listar_fazendas():
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id,nome,cidade,estado FROM fazendas ORDER BY nome")
        rows = _fetch(cur)
        return [(r["id"],r["nome"],r["cidade"],r["estado"]) for r in rows]


# ── VACINAS ───────────────────────────────────────────────────────────────────
def adicionar_vacina_agenda(lote_id, nome_vacina, data_prevista, observacao=""):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO vacinas_agenda (lote_id,nome_vacina,data_prevista,observacao) VALUES({p},{p},{p},{p}) RETURNING id", (lote_id, nome_vacina, data_prevista, observacao))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO vacinas_agenda (lote_id,nome_vacina,data_prevista,observacao) VALUES({p},{p},{p},{p})", (lote_id, nome_vacina, data_prevista, observacao))
            return cur.lastrowid

def registrar_vacina_realizada(vacina_id, data_realizada):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE vacinas_agenda SET data_realizada={p},status='realizado' WHERE id={p}", (data_realizada, vacina_id))

def listar_vacinas_agenda(lote_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if lote_id:
            cur.execute(f"SELECT id,lote_id,nome_vacina,data_prevista,data_realizada,status,observacao FROM vacinas_agenda WHERE lote_id={p} ORDER BY data_prevista", (lote_id,))
        else:
            cur.execute("SELECT id,lote_id,nome_vacina,data_prevista,data_realizada,status,observacao FROM vacinas_agenda ORDER BY data_prevista")
        rows = _fetch(cur)
        return [(r["id"],r["lote_id"],r["nome_vacina"],r["data_prevista"],r["data_realizada"],r["status"],r["observacao"]) for r in rows]

def listar_vacinas_pendentes(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if owner_id is not None:
            cur.execute(
                f"SELECT v.id,v.lote_id,l.nome,v.nome_vacina,v.data_prevista,v.status,v.observacao"
                f" FROM vacinas_agenda v JOIN lotes l ON l.id=v.lote_id"
                f" WHERE v.status='pendente' AND l.owner_id={p} ORDER BY v.data_prevista",
                (owner_id,),
            )
        else:
            cur.execute(
                "SELECT v.id,v.lote_id,l.nome,v.nome_vacina,v.data_prevista,v.status,v.observacao"
                " FROM vacinas_agenda v JOIN lotes l ON l.id=v.lote_id"
                " WHERE v.status='pendente' ORDER BY v.data_prevista"
            )
        rows = _fetch(cur)
        return [(r["id"],r["lote_id"],r["nome"],r["nome_vacina"],r["data_prevista"],r["status"],r["observacao"]) for r in rows]

def adicionar_medicamento(nome, unidade, estoque_atual, estoque_minimo, validade, custo_unitario, owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO medicamentos (nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario,owner_id)"
                f" VALUES({p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (nome, unidade, estoque_atual, estoque_minimo, validade, custo_unitario, owner_id),
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO medicamentos (nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario,owner_id)"
                f" VALUES({p},{p},{p},{p},{p},{p},{p})",
                (nome, unidade, estoque_atual, estoque_minimo, validade, custo_unitario, owner_id),
            )
            return cur.lastrowid

def listar_medicamentos(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if owner_id is not None:
            cur.execute(
                f"SELECT id,nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario"
                f" FROM medicamentos WHERE owner_id={p} ORDER BY nome",
                (owner_id,),
            )
        else:
            cur.execute(
                "SELECT id,nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario"
                " FROM medicamentos ORDER BY nome"
            )
        rows = _fetch(cur)
        return [(r["id"],r["nome"],r["unidade"],r["estoque_atual"],r["estoque_minimo"],r["validade"],r["custo_unitario"]) for r in rows]

def atualizar_estoque(medicamento_id, quantidade):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE medicamentos SET estoque_atual=GREATEST(0,estoque_atual-{p}) WHERE id={p}" if _usar_postgres() else f"UPDATE medicamentos SET estoque_atual=MAX(0,estoque_atual-{p}) WHERE id={p}", (quantidade, medicamento_id))

def registrar_uso_medicamento(medicamento_id, animal_id, data_uso, quantidade, ocorrencia_id=None):
    p = _ph()
    atualizar_estoque(medicamento_id, quantidade)
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO medicamentos_uso (medicamento_id,animal_id,ocorrencia_id,data_uso,quantidade) VALUES({p},{p},{p},{p},{p}) RETURNING id", (medicamento_id, animal_id, ocorrencia_id, data_uso, quantidade))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO medicamentos_uso (medicamento_id,animal_id,ocorrencia_id,data_uso,quantidade) VALUES({p},{p},{p},{p},{p})", (medicamento_id, animal_id, ocorrencia_id, data_uso, quantidade))
            return cur.lastrowid

def listar_medicamentos_criticos(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        filtro = f" AND owner_id={p}" if owner_id is not None else ""
        params = (owner_id,) if owner_id is not None else ()
        cur.execute(
            f"SELECT id,nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario FROM medicamentos"
            f" WHERE estoque_atual<=estoque_minimo OR (validade IS NOT NULL AND {_cast_date('validade')}<={_date_add(30)})"
            f"{filtro}",
            params,
        )
        rows = _fetch(cur)
        return [(r["id"],r["nome"],r["unidade"],r["estoque_atual"],r["estoque_minimo"],r["validade"],r["custo_unitario"]) for r in rows]

def verificar_carencia(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT mu.data_uso,m.nome,m.carencia_dias FROM medicamentos_uso mu JOIN medicamentos m ON m.id=mu.medicamento_id WHERE mu.animal_id={p} AND m.carencia_dias>0",
            (animal_id,),
        )
        rows = _fetch(cur)
    if not rows:
        return dict(em_carencia=False, medicamentos=[], liberado_em=None)
    import datetime
    meds = []
    for r in rows:
        try:
            dt = datetime.datetime.strptime(str(r["data_uso"])[:10], "%Y-%m-%d").date()
            libera = dt + datetime.timedelta(days=int(r["carencia_dias"]))
            if libera >= _date.today():
                meds.append(dict(medicamento=r["nome"], uso=r["data_uso"], carencia_dias=r["carencia_dias"], libera_em=str(libera)))
        except Exception:
            pass
    if not meds:
        return dict(em_carencia=False, medicamentos=[], liberado_em=None)
    liberado_em = max(m["libera_em"] for m in meds)
    return dict(em_carencia=True, medicamentos=meds, liberado_em=liberado_em)


# ── REPRODUCAO ────────────────────────────────────────────────────────────────
def adicionar_reproducao(animal_id, tipo_cobertura, data_cio=None, data_diagnostico=None, resultado="pendente", data_parto_previsto=None, observacao=""):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO reproducao (animal_id,data_cio,tipo_cobertura,data_diagnostico,resultado,data_parto_previsto,observacao) VALUES({p},{p},{p},{p},{p},{p},{p}) RETURNING id", (animal_id, data_cio, tipo_cobertura, data_diagnostico, resultado, data_parto_previsto, observacao))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO reproducao (animal_id,data_cio,tipo_cobertura,data_diagnostico,resultado,data_parto_previsto,observacao) VALUES({p},{p},{p},{p},{p},{p},{p})", (animal_id, data_cio, tipo_cobertura, data_diagnostico, resultado, data_parto_previsto, observacao))
            return cur.lastrowid

def atualizar_reproducao(repro_id, resultado, data_parto_real=None, data_diagnostico=None, data_parto_previsto=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE reproducao SET resultado={p},data_parto_real=COALESCE({p},data_parto_real),data_diagnostico=COALESCE({p},data_diagnostico),data_parto_previsto=COALESCE({p},data_parto_previsto) WHERE id={p}",
            (resultado, data_parto_real, data_diagnostico, data_parto_previsto, repro_id),
        )

def listar_reproducao(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id,animal_id,data_cio,tipo_cobertura,data_diagnostico,resultado,data_parto_previsto,data_parto_real,observacao FROM reproducao WHERE animal_id={p} ORDER BY data_cio DESC", (animal_id,))
        rows = _fetch(cur)
        return [(r["id"],r["animal_id"],r["data_cio"],r["tipo_cobertura"],r["data_diagnostico"],r["resultado"],r["data_parto_previsto"],r["data_parto_real"],r["observacao"]) for r in rows]

def listar_partos_previstos(owner_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        filtro_owner = f" AND l.owner_id={p}" if owner_id is not None else ""
        params = (owner_id,) if owner_id is not None else ()
        cur.execute(
            f"SELECT r.id,a.identificacao,l.nome,r.data_parto_previsto,r.tipo_cobertura"
            f" FROM reproducao r JOIN animais a ON a.id=r.animal_id JOIN lotes l ON l.id=a.lote_id"
            f" WHERE r.resultado='positivo' AND r.data_parto_real IS NULL"
            f" AND {_cast_date('r.data_parto_previsto')}<={_date_add(30)}{filtro_owner}"
            f" ORDER BY r.data_parto_previsto",
            params,
        )
        rows = _fetch(cur)
        return [(r["id"],r["identificacao"],r["nome"],r["data_parto_previsto"],r["tipo_cobertura"]) for r in rows]

def taxa_prenhez_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(DISTINCT r.animal_id) FROM reproducao r JOIN animais a ON a.id=r.animal_id WHERE a.lote_id={p}", (lote_id,))
        total = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(DISTINCT r.animal_id) FROM reproducao r JOIN animais a ON a.id=r.animal_id WHERE a.lote_id={p} AND r.resultado='positivo'", (lote_id,))
        positivas = cur.fetchone()[0]
    return dict(total=total, positivas=positivas, taxa=(positivas/total*100) if total > 0 else 0)


# ── PIQUETES ──────────────────────────────────────────────────────────────────
def adicionar_piquete(nome, area_ha, capacidade_ua, fazenda_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO piquetes (nome,area_ha,capacidade_ua,fazenda_id) VALUES({p},{p},{p},{p}) RETURNING id", (nome, area_ha, capacidade_ua, fazenda_id))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO piquetes (nome,area_ha,capacidade_ua,fazenda_id) VALUES({p},{p},{p},{p})", (nome, area_ha, capacidade_ua, fazenda_id))
            return cur.lastrowid

def listar_piquetes(fazenda_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if fazenda_id:
            cur.execute(f"SELECT id,fazenda_id,nome,area_ha,capacidade_ua FROM piquetes WHERE fazenda_id={p} ORDER BY nome", (fazenda_id,))
        else:
            cur.execute("SELECT id,fazenda_id,nome,area_ha,capacidade_ua FROM piquetes ORDER BY nome")
        rows = _fetch(cur)
        return [(r["id"],r["fazenda_id"],r["nome"],r["area_ha"],r["capacidade_ua"]) for r in rows]

def alocar_lote_piquete(piquete_id, lote_id, data_entrada):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO piquetes_historico (piquete_id,lote_id,entrada) VALUES({p},{p},{p}) RETURNING id", (piquete_id, lote_id, data_entrada))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO piquetes_historico (piquete_id,lote_id,entrada) VALUES({p},{p},{p})", (piquete_id, lote_id, data_entrada))
            return cur.lastrowid

def liberar_piquete(piquete_id, data_saida):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE piquetes_historico SET saida={p} WHERE piquete_id={p} AND saida IS NULL", (data_saida, piquete_id))

def historico_piquete(piquete_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT ph.id,l.nome,ph.entrada,ph.saida FROM piquetes_historico ph JOIN lotes l ON l.id=ph.lote_id WHERE ph.piquete_id={p} ORDER BY ph.entrada DESC", (piquete_id,))
        rows = _fetch(cur)
        return [(r["id"],r["nome"],r["entrada"],r["saida"]) for r in rows]


# ── MORTALIDADE ───────────────────────────────────────────────────────────────
def registrar_morte(animal_id, data, causa, descricao="", custo_perda=0.0):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT lote_id FROM animais WHERE id={p}", (animal_id,))
        r = cur.fetchone()
        lote_id = r[0] if r else None
        cur.execute(f"UPDATE animais SET ativo=0 WHERE id={p}", (animal_id,))
        if _usar_postgres():
            cur.execute(f"INSERT INTO mortalidade (animal_id,data,causa,descricao,custo_perda) VALUES({p},{p},{p},{p},{p}) RETURNING id", (animal_id, data, causa, descricao, custo_perda))
            mid = cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO mortalidade (animal_id,data,causa,descricao,custo_perda) VALUES({p},{p},{p},{p},{p})", (animal_id, data, causa, descricao, custo_perda))
            mid = cur.lastrowid
    if lote_id:
        atualizar_qtd_lote(lote_id)
    return mid

def listar_mortalidade(lote_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if lote_id:
            cur.execute(f"SELECT m.id,m.animal_id,a.identificacao,m.data,m.causa,m.descricao,m.custo_perda FROM mortalidade m JOIN animais a ON a.id=m.animal_id WHERE a.lote_id={p} ORDER BY m.data DESC", (lote_id,))
        else:
            cur.execute("SELECT m.id,m.animal_id,a.identificacao,m.data,m.causa,m.descricao,m.custo_perda FROM mortalidade m JOIN animais a ON a.id=m.animal_id ORDER BY m.data DESC")
        rows = _fetch(cur)
        return [(r["id"],r["animal_id"],r["identificacao"],r["data"],r["causa"],r["descricao"],r["custo_perda"]) for r in rows]

def taxa_mortalidade_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p}", (lote_id,))
        total = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM mortalidade m JOIN animais a ON a.id=m.animal_id WHERE a.lote_id={p}", (lote_id,))
        mortos = cur.fetchone()[0]
    return dict(total=total, mortos=mortos, taxa=round((mortos/total*100) if total > 0 else 0, 2))


# ── AUDITORIA ─────────────────────────────────────────────────────────────────
def registrar_auditoria(usuario_id, acao, tabela="", registro_id=None, detalhe=""):
    p = _ph()
    from datetime import datetime
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO auditoria (usuario_id,acao,tabela,registro_id,detalhe,data_hora) VALUES({p},{p},{p},{p},{p},{p})",
            (usuario_id, acao, tabela, registro_id, detalhe, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )

def listar_auditoria(limite=100, usuario_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if usuario_id:
            cur.execute(f"SELECT a.id,u.nome,a.acao,a.tabela,a.registro_id,a.detalhe,a.data_hora FROM auditoria a JOIN usuarios u ON u.id=a.usuario_id WHERE a.usuario_id={p} ORDER BY a.id DESC LIMIT {p}", (usuario_id, limite))
        else:
            cur.execute(f"SELECT a.id,u.nome,a.acao,a.tabela,a.registro_id,a.detalhe,a.data_hora FROM auditoria a JOIN usuarios u ON u.id=a.usuario_id ORDER BY a.id DESC LIMIT {p}", (limite,))
        rows = _fetch(cur)
        return [(r["id"],r["nome"],r["acao"],r["tabela"],r["registro_id"],r["detalhe"],r["data_hora"]) for r in rows]


# ── GTA / SISBOV ──────────────────────────────────────────────────────────────
def registrar_gta(lote_id, numero_gta, data_emissao, origem, destino, quantidade, finalidade="Abate", observacao=""):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO gta (lote_id,numero_gta,data_emissao,origem,destino,quantidade,finalidade,observacao) VALUES({p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id", (lote_id, numero_gta, data_emissao, origem, destino, quantidade, finalidade, observacao))
            gta_id = cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO gta (lote_id,numero_gta,data_emissao,origem,destino,quantidade,finalidade,observacao) VALUES({p},{p},{p},{p},{p},{p},{p},{p})", (lote_id, numero_gta, data_emissao, origem, destino, quantidade, finalidade, observacao))
            gta_id = cur.lastrowid
        if finalidade in ("Abate", "Venda"):
            cur.execute(f"SELECT id FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1 ORDER BY id DESC LIMIT {p}", (lote_id, quantidade))
            rows = cur.fetchall()
            for row in rows:
                aid = row[0] if _usar_postgres() else row[0]
                cur.execute(f"UPDATE animais SET ativo=0 WHERE id={p}", (aid,))
    atualizar_qtd_lote(lote_id)
    return gta_id

def listar_gta(lote_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if lote_id:
            cur.execute(f"SELECT g.id,g.lote_id,l.nome,g.numero_gta,g.data_emissao,g.origem,g.destino,g.quantidade,g.finalidade,g.observacao FROM gta g JOIN lotes l ON l.id=g.lote_id WHERE g.lote_id={p} ORDER BY g.data_emissao DESC", (lote_id,))
        else:
            cur.execute("SELECT g.id,g.lote_id,l.nome,g.numero_gta,g.data_emissao,g.origem,g.destino,g.quantidade,g.finalidade,g.observacao FROM gta g JOIN lotes l ON l.id=g.lote_id ORDER BY g.data_emissao DESC")
        rows = _fetch(cur)
        return [(r["id"],r["lote_id"],r["nome"],r["numero_gta"],r["data_emissao"],r["origem"],r["destino"],r["quantidade"],r["finalidade"],r["observacao"]) for r in rows]

def registrar_sisbov(animal_id, numero_sisbov, data_certificacao):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO sisbov (animal_id,numero_sisbov,data_certificacao) VALUES({p},{p},{p}) ON CONFLICT (animal_id) DO UPDATE SET numero_sisbov=EXCLUDED.numero_sisbov,data_certificacao=EXCLUDED.data_certificacao RETURNING id", (animal_id, numero_sisbov, data_certificacao))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT OR REPLACE INTO sisbov (animal_id,numero_sisbov,data_certificacao) VALUES({p},{p},{p})", (animal_id, numero_sisbov, data_certificacao))
            return cur.lastrowid

def obter_sisbov(animal_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id,animal_id,numero_sisbov,data_certificacao FROM sisbov WHERE animal_id={p}", (animal_id,))
        r = _fetchone(cur)
        return (r["id"],r["animal_id"],r["numero_sisbov"],r["data_certificacao"]) if r else None


# ── SCORE DE SAUDE ────────────────────────────────────────────────────────────
def calcular_score_saude(animal_id):
    import pandas as pd
    pesagens = listar_pesagens(animal_id)
    gmd = 0.0
    if len(pesagens) >= 2:
        df = pd.DataFrame(pesagens, columns=["id","aid","peso","data"])
        df["data"] = pd.to_datetime(df["data"])
        df = df.sort_values("data")
        dias = (df["data"].iloc[-1] - df["data"].iloc[0]).days
        if dias > 0:
            gmd = (df["peso"].iloc[-1] - df["peso"].iloc[0]) / dias
    pts_gmd = 50 if gmd>=1.2 else 45 if gmd>=1.0 else 38 if gmd>=0.8 else 30 if gmd>=0.6 else 20 if gmd>=0.4 else 10 if gmd>=0.0 else 0
    ocs = listar_ocorrencias(animal_id)
    pen = min(35, sum(1 for o in ocs if o[5]=="Alta")*15 + sum(1 for o in ocs if o[5]=="Media")*7 + sum(1 for o in ocs if o[5]=="Baixa")*3)
    pts_oc = max(0, 35 - pen)
    repros = listar_reproducao(animal_id)
    pts_rep = 5 if repros and repros[0][5]=="negativo" else 10 if repros and repros[0][5]=="pendente" else 15
    score = pts_gmd + pts_oc + pts_rep
    classif = "Excelente" if score>=80 else "Bom" if score>=60 else "Regular" if score>=40 else "Critico"
    return dict(score=score, classificacao=classif,
                detalhes=dict(pts_gmd=pts_gmd, pts_ocorrencias=pts_oc, pts_reproducao=pts_rep, gmd=round(gmd,3), n_ocorrencias=len(ocs)))


# ── PREVISAO DE ABATE ─────────────────────────────────────────────────────────
def calcular_previsao_abate(animal_id):
    import pandas as pd
    from datetime import date as dt
    animal = obter_animal(animal_id)
    if not animal: return {}
    peso_alvo = animal[7]
    pesagens  = listar_pesagens(animal_id)
    if len(pesagens) < 2 or peso_alvo <= 0:
        return dict(erro="Necessario >= 2 pesagens e peso alvo definido")
    df = pd.DataFrame(pesagens, columns=["id","aid","peso","data"])
    df["data"] = pd.to_datetime(df["data"])
    df = df.sort_values("data")
    peso_atual = df["peso"].iloc[-1]
    dias_hist  = (df["data"].iloc[-1] - df["data"].iloc[0]).days
    if dias_hist == 0: return dict(erro="Datas de pesagem identicas")
    gmd = (peso_atual - df["peso"].iloc[0]) / dias_hist
    if gmd <= 0: return dict(erro="GMD negativo")
    if peso_atual >= peso_alvo:
        return dict(gmd=round(gmd,3), peso_atual=peso_atual, peso_alvo=peso_alvo, dias_restantes=0, data_prevista=str(dt.today()), confianca="pronto")
    dias_rest = int((peso_alvo - peso_atual) / gmd)
    data_prev = dt.today() + _td(days=dias_rest)
    confianca = "alta" if len(pesagens)>=5 else "media" if len(pesagens)>=3 else "baixa"
    return dict(gmd=round(gmd,3), peso_atual=round(peso_atual,1), peso_alvo=round(peso_alvo,1),
                dias_restantes=dias_rest, data_prevista=str(data_prev), confianca=confianca)


# ── VENDAS / MARGEM ───────────────────────────────────────────────────────────
def registrar_venda_lote(lote_id, data_venda, preco_venda_kg, peso_total_kg, frigorific="", observacao=""):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO vendas_lote (lote_id,data_venda,preco_venda_kg,peso_total_kg,frigorific,observacao) VALUES({p},{p},{p},{p},{p},{p}) RETURNING id", (lote_id, data_venda, preco_venda_kg, peso_total_kg, frigorific, observacao))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO vendas_lote (lote_id,data_venda,preco_venda_kg,peso_total_kg,frigorific,observacao) VALUES({p},{p},{p},{p},{p},{p})", (lote_id, data_venda, preco_venda_kg, peso_total_kg, frigorific, observacao))
            return cur.lastrowid

def calcular_margem_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        lote = obter_lote(lote_id)
        if not lote: return {}
        cur.execute(f"SELECT COALESCE(preco_por_animal,0) FROM lotes WHERE id={p}", (lote_id,))
        preco_animal = cur.fetchone()[0]
        custo_compra = preco_animal * lote[5]
        cur.execute(f"SELECT preco_venda_kg,peso_total_kg,data_venda,frigorific FROM vendas_lote WHERE lote_id={p} ORDER BY id DESC LIMIT 1", (lote_id,))
        venda = cur.fetchone()
        receita_real = (venda[0]*venda[1]) if venda else 0.0
        animais = listar_animais_por_lote(lote_id)
        custo_san = sum(o[6] for a in animais for o in listar_ocorrencias(a[0]) if o[6])
        margem = receita_real - custo_compra - custo_san
        margem_pct = (margem/custo_compra*100) if custo_compra > 0 else 0
    return dict(custo_compra=round(custo_compra,2), receita_real=round(receita_real,2),
                custo_sanitario=round(custo_san,2), margem=round(margem,2), margem_pct=round(margem_pct,1),
                data_venda=venda[2] if venda else None, frigorific=venda[3] if venda else "",
                venda_registrada=venda is not None)

def listar_vendas_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id,lote_id,data_venda,preco_venda_kg,peso_total_kg,frigorific,observacao FROM vendas_lote WHERE lote_id={p} ORDER BY data_venda DESC", (lote_id,))
        rows = _fetch(cur)
        return [(r["id"],r["lote_id"],r["data_venda"],r["preco_venda_kg"],r["peso_total_kg"],r["frigorific"],r["observacao"]) for r in rows]


# ── COTACOES ──────────────────────────────────────────────────────────────────
def salvar_cotacao(data, preco, fonte="manual"):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(f"INSERT INTO cotacoes (data,preco,fonte) VALUES({p},{p},{p}) ON CONFLICT (data) DO UPDATE SET preco=EXCLUDED.preco,fonte=EXCLUDED.fonte RETURNING id", (data, preco, fonte))
            return cur.fetchone()[0]
        else:
            cur.execute(f"INSERT INTO cotacoes (data,preco,fonte) VALUES({p},{p},{p}) ON CONFLICT(data) DO UPDATE SET preco=excluded.preco,fonte=excluded.fonte", (data, preco, fonte))
            return cur.lastrowid

def listar_cotacoes(dias=30):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if dias <= 0:
            cur.execute("SELECT id,data,preco,fonte FROM cotacoes ORDER BY data ASC")
        else:
            cur.execute(
                f"SELECT id,data,preco,fonte FROM cotacoes WHERE {_cast_date('data')}>={_date_add(dias, chr(45))} ORDER BY data ASC"
            )
        rows = _fetch(cur)
        return [(r["id"],r["data"],r["preco"],r["fonte"]) for r in rows]

def obter_ultima_cotacao():
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id,data,preco,fonte FROM cotacoes ORDER BY data DESC LIMIT 1")
        r = _fetchone(cur)
        return (r["id"],r["data"],r["preco"],r["fonte"]) if r else None


# ── GMD TEMPORAL ──────────────────────────────────────────────────────────────
def calcular_gmd_temporal(lote_id, janela_dias=14):
    import pandas as pd
    animais = listar_animais_por_lote(lote_id)
    todos = [{"animal_id":a[0],"peso":p[2],"data":p[3]} for a in animais for p in listar_pesagens(a[0])]
    if len(todos) < 2: return []
    df = pd.DataFrame(todos)
    df["data"] = pd.to_datetime(df["data"])
    df = df.sort_values("data")
    resultado = []
    data_atual = df["data"].min() + pd.Timedelta(days=janela_dias)
    while data_atual <= df["data"].max():
        janela = df[df["data"] <= data_atual]
        gmds = []
        for aid in janela["animal_id"].unique():
            sub = janela[janela["animal_id"]==aid].sort_values("data")
            if len(sub) >= 2:
                dias = (sub["data"].iloc[-1]-sub["data"].iloc[0]).days
                if dias > 0:
                    g = (sub["peso"].iloc[-1]-sub["peso"].iloc[0])/dias
                    if 0 < g <= 2: gmds.append(g)
        if gmds: resultado.append((str(data_atual.date()), round(sum(gmds)/len(gmds),4)))
        data_atual += pd.Timedelta(days=janela_dias)
    return resultado


# ── IMPORTACAO CSV ─────────────────────────────────────────────────────────────
def importar_pesagens_csv(linhas, lote_id):
    ok = erros = criados = 0
    msgs = []
    existentes = {a[1]:a[0] for a in listar_animais_por_lote(lote_id)}
    for i, linha in enumerate(linhas, 1):
        try:
            ident = str(linha.get("identificacao","")).strip()
            peso  = float(str(linha.get("peso","0")).replace(",","."))
            data  = str(linha.get("data","")).strip()
            if not ident or not data or peso <= 0:
                erros += 1; msgs.append(f"Linha {i}: invalido"); continue
            if ident not in existentes:
                existentes[ident] = adicionar_animal(ident, 0, lote_id); criados += 1
            adicionar_pesagem(existentes[ident], peso, data); ok += 1
        except Exception as e:
            erros += 1; msgs.append(f"Linha {i}: {e}")
    if criados > 0:
        atualizar_qtd_lote(lote_id)
    return dict(importados=ok, erros=erros, animais_criados=criados, mensagens=msgs)

def importar_animais_csv(linhas, lote_id):
    ok = erros = 0; msgs = []
    existentes = {a[1] for a in listar_animais_por_lote(lote_id)}
    for i, linha in enumerate(linhas, 1):
        try:
            ident = str(linha.get("identificacao","")).strip()
            if not ident: erros+=1; msgs.append(f"Linha {i}: vazio"); continue
            if ident in existentes: erros+=1; msgs.append(f"Linha {i}: {ident} existe"); continue
            idade = int(float(str(linha.get("idade",0)).replace(",",".") or 0))
            aid = adicionar_animal(ident, idade, lote_id)
            pa = float(str(linha.get("peso_alvo",0)).replace(",",".") or 0)
            ob = str(linha.get("observacoes",""))
            atualizar_animal_detalhes(aid, peso_alvo=pa if pa>0 else None, observacoes=ob if ob else None)
            existentes.add(ident); ok += 1
        except Exception as e:
            erros+=1; msgs.append(f"Linha {i}: {e}")
    if ok > 0:
        atualizar_qtd_lote(lote_id)
    return dict(importados=ok, erros=erros, mensagens=msgs)


# ── CONSISTENCIA DE LOTE ──────────────────────────────────────────────────────
def atualizar_qtd_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1", (lote_id,))
        n = cur.fetchone()[0]
        cur.execute(f"UPDATE lotes SET qtd_recebida={p} WHERE id={p}", (n, lote_id))
    return n

def resumo_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p} AND COALESCE(ativo,1)=1", (lote_id,))
        ativos = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM mortalidade m JOIN animais a ON a.id=m.animal_id WHERE a.lote_id={p}", (lote_id,))
        mortos = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p}", (lote_id,))
        total = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*),COALESCE(SUM(quantidade),0) FROM gta WHERE lote_id={p}", (lote_id,))
        gtas = cur.fetchone()
        cur.execute(f"SELECT COALESCE(SUM(o.custo),0) FROM ocorrencias o JOIN animais a ON a.id=o.animal_id WHERE a.lote_id={p}", (lote_id,))
        custo = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM ocorrencias o JOIN animais a ON a.id=o.animal_id WHERE a.lote_id={p}", (lote_id,))
        ocorr = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM vacinas_agenda WHERE lote_id={p} AND status='pendente'", (lote_id,))
        vac_pend = cur.fetchone()[0]
    return dict(total_animais=total, ativos=ativos, mortos=mortos,
                gtas_emitidas=gtas[0], animais_saida_gta=int(gtas[1]),
                ocorrencias=ocorr, custo_sanitario=round(float(custo),2), vacinas_pendentes=vac_pend)

def transferir_animal(animal_id, lote_destino_id, motivo='', usuario_id=None):
    p = _ph()
    from datetime import date as _d
    with _conexao() as conn:
        cur = conn.cursor()
        # Buscar lote atual
        cur.execute(f"SELECT lote_id FROM animais WHERE id={p}", (animal_id,))
        r = cur.fetchone()
        if not r:
            return dict(ok=False, msg='Animal nao encontrado')
        lote_origem_id = r[0]
        if lote_origem_id == lote_destino_id:
            return dict(ok=False, msg='Animal ja esta neste lote')
        # Mover o animal
        cur.execute(
            f"UPDATE animais SET lote_id={p}, status='ATIVO', ativo=1 WHERE id={p}",
            (lote_destino_id, animal_id),
        )
        # Registrar movimentacao
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO movimentacoes_animais (animal_id,lote_origem,lote_destino,data,motivo,usuario_id)"
                f" VALUES({p},{p},{p},{p},{p},{p}) RETURNING id",
                (animal_id, lote_origem_id, lote_destino_id, str(_d.today()), motivo, usuario_id),
            )
        else:
            cur.execute(
                f"INSERT INTO movimentacoes_animais (animal_id,lote_origem,lote_destino,data,motivo,usuario_id)"
                f" VALUES({p},{p},{p},{p},{p},{p})",
                (animal_id, lote_origem_id, lote_destino_id, str(_d.today()), motivo, usuario_id),
            )
        conn.commit()
    # Atualizar contagens de ambos os lotes
    atualizar_qtd_lote(lote_origem_id)
    atualizar_qtd_lote(lote_destino_id)
    return dict(ok=True, msg='Animal transferido com sucesso',
                lote_origem=lote_origem_id, lote_destino=lote_destino_id)

def listar_movimentacoes(animal_id=None, lote_id=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if animal_id:
            cur.execute(
                f"SELECT m.id,m.animal_id,a.identificacao,"
                f"lo.nome as lote_origem,ld.nome as lote_destino,m.data,m.motivo"
                f" FROM movimentacoes_animais m"
                f" JOIN animais a ON a.id=m.animal_id"
                f" JOIN lotes lo ON lo.id=m.lote_origem"
                f" JOIN lotes ld ON ld.id=m.lote_destino"
                f" WHERE m.animal_id={p} ORDER BY m.data DESC",
                (animal_id,),
            )
        elif lote_id:
            cur.execute(
                f"SELECT m.id,m.animal_id,a.identificacao,"
                f"lo.nome as lote_origem,ld.nome as lote_destino,m.data,m.motivo"
                f" FROM movimentacoes_animais m"
                f" JOIN animais a ON a.id=m.animal_id"
                f" JOIN lotes lo ON lo.id=m.lote_origem"
                f" JOIN lotes ld ON ld.id=m.lote_destino"
                f" WHERE m.lote_origem={p} OR m.lote_destino={p} ORDER BY m.data DESC",
                (lote_id, lote_id),
            )
        else:
            cur.execute(
                "SELECT m.id,m.animal_id,a.identificacao,"
                "lo.nome as lote_origem,ld.nome as lote_destino,m.data,m.motivo"
                " FROM movimentacoes_animais m"
                " JOIN animais a ON a.id=m.animal_id"
                " JOIN lotes lo ON lo.id=m.lote_origem"
                " JOIN lotes ld ON ld.id=m.lote_destino"
                " ORDER BY m.data DESC LIMIT 100"
            )
        rows = _fetch(cur)
        return [(r['id'],r['animal_id'],r['identificacao'],
                 r['lote_origem'],r['lote_destino'],r['data'],r['motivo']) for r in rows]


def gerar_insights_lote(lote_id):
    import pandas as pd
    from datetime import date as _d
    insights = []
    animais = listar_animais_por_lote(lote_id)
    if not animais:
        return insights

    # 1. Queda de GMD
    gmds = []
    for a in animais:
        ps = listar_pesagens(a[0])
        if len(ps) >= 2:
            df = pd.DataFrame(ps, columns=['id','aid','peso','data'] + (['ident'] if ps and len(ps[0]) > 4 else []))
            df['data'] = pd.to_datetime(df['data'])
            df = df.sort_values('data')
            dias = (df['data'].iloc[-1] - df['data'].iloc[0]).days
            if dias > 0:
                g = (df['peso'].iloc[-1] - df['peso'].iloc[0]) / dias
                gmds.append(g)
    if gmds:
        gmd_medio = sum(gmds) / len(gmds)
        if gmd_medio < 0:
            insights.append(dict(tipo='critico', titulo='GMD negativo',
                descricao=f'Media do lote: {gmd_medio:.3f} kg/dia. Animais perdendo peso.',
                acao='Revisar alimentacao e saude do lote'))
        elif gmd_medio < 0.5:
            insights.append(dict(tipo='aviso', titulo='GMD abaixo do esperado',
                descricao=f'Media do lote: {gmd_medio:.3f} kg/dia. Esperado acima de 0.8.',
                acao='Avaliar dieta e condicao sanitaria'))

    # 2. Mortalidade elevada
    from database import taxa_mortalidade_lote
    mort = taxa_mortalidade_lote(lote_id)
    if mort['taxa'] >= 5:
        insights.append(dict(tipo='critico', titulo='Mortalidade elevada',
            descricao=f'{mort["mortos"]} mortes ({mort["taxa"]}% do lote).',
            acao='Investigar causa e acionar veterinario'))
    elif mort['taxa'] >= 2:
        insights.append(dict(tipo='aviso', titulo='Mortalidade acima do normal',
            descricao=f'{mort["mortos"]} mortes ({mort["taxa"]}% do lote).',
            acao='Monitorar de perto'))

    # 3. Vacinas atrasadas
    from database import listar_vacinas_agenda
    vacs = listar_vacinas_agenda(lote_id)
    atrasadas = [v for v in vacs if v[5] == 'pendente' and str(v[3]) < str(_d.today())]
    if len(atrasadas) >= 3:
        insights.append(dict(tipo='critico', titulo='Vacinas muito atrasadas',
            descricao=f'{len(atrasadas)} vacinas pendentes em atraso.',
            acao='Agendar vacinacao urgente'))
    elif len(atrasadas) > 0:
        insights.append(dict(tipo='aviso', titulo='Vacinas em atraso',
            descricao=f'{len(atrasadas)} vacina(s) pendente(s) atrasada(s).',
            acao='Verificar calendario sanitario'))

    # 4. Custo sanitario elevado
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COALESCE(SUM(o.custo),0) FROM ocorrencias o"
            f" JOIN animais a ON a.id=o.animal_id WHERE a.lote_id={p}",
            (lote_id,),
        )
        custo_san = float(cur.fetchone()[0] or 0)
    rs = resumo_lote(lote_id)
    if rs['ativos'] > 0:
        custo_por_animal = custo_san / rs['ativos']
        if custo_por_animal > 500:
            insights.append(dict(tipo='critico', titulo='Custo sanitario muito alto',
                descricao=f'R$ {custo_por_animal:.0f}/animal. Total: R$ {custo_san:.0f}.',
                acao='Revisar protocolo sanitario'))
        elif custo_por_animal > 200:
            insights.append(dict(tipo='aviso', titulo='Custo sanitario elevado',
                descricao=f'R$ {custo_por_animal:.0f}/animal. Total: R$ {custo_san:.0f}.',
                acao='Monitorar gastos com saude'))

    # 5. Animais sem pesagem
    sem_pesagem = sum(1 for a in animais if len(listar_pesagens(a[0])) == 0)
    if sem_pesagem > 0:
        insights.append(dict(tipo='info', titulo='Animais sem pesagem',
            descricao=f'{sem_pesagem} animal(is) sem nenhuma pesagem registrada.',
            acao='Registrar pesagem inicial'))

    # 6. Lote saudavel
    if not insights:
        insights.append(dict(tipo='positivo', titulo='Lote saudavel',
            descricao='Nenhum alerta identificado. Continue monitorando.',
            acao=None))

    return insights


# ── QUERIES AGREGADAS (elimina N+1) ─────────────────────────────────────────

def listar_pesagens_todos_animais(lote_id):
    # Uma unica query retorna todas as pesagens de todos os animais do lote
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT p.id,p.animal_id,p.peso,p.data,a.identificacao"
            f" FROM pesagens p JOIN animais a ON a.id=p.animal_id"
            f" WHERE a.lote_id={p} AND COALESCE(a.ativo,1)=1"
            f" ORDER BY p.animal_id,p.data ASC",
            (lote_id,),
        )
        rows = _fetch(cur)
        return [(r['id'],r['animal_id'],r['peso'],r['data'],r['identificacao']) for r in rows]

def listar_ocorrencias_todos_animais(lote_id):
    # Uma unica query retorna todas as ocorrencias de todos os animais do lote
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT o.id,o.animal_id,o.data,o.tipo,o.descricao,"
            f"o.gravidade,o.custo,o.dias_recuperacao,o.status,a.identificacao"
            f" FROM ocorrencias o JOIN animais a ON a.id=o.animal_id"
            f" WHERE a.lote_id={p}"
            f" ORDER BY o.animal_id,o.data ASC",
            (lote_id,),
        )
        rows = _fetch(cur)
        return [(r['id'],r['animal_id'],r['data'],r['tipo'],r['descricao'],
                 r['gravidade'],r['custo'],r['dias_recuperacao'],r['status'],r['identificacao']) for r in rows]

def calcular_gmds_lote(lote_id):
    # Calcula GMD de todos os animais do lote com uma unica query
    import pandas as pd
    rows = listar_pesagens_todos_animais(lote_id)
    if not rows:
        return {}
    df = pd.DataFrame(rows, columns=['id','animal_id','peso','data','ident'])
    df['data'] = pd.to_datetime(df['data'])
    resultado = {}
    for aid, grp in df.groupby('animal_id'):
        grp = grp.sort_values('data')
        if len(grp) >= 2:
            dias = (grp['data'].iloc[-1] - grp['data'].iloc[0]).days
            if dias > 0:
                gmd = (grp['peso'].iloc[-1] - grp['peso'].iloc[0]) / dias
                resultado[aid] = round(gmd, 4)
    return resultado

def resumo_dashboard(owner_id=None):
    # KPIs do Home filtrados por owner_id
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if owner_id is not None:
            cur.execute(f"SELECT COUNT(*) FROM lotes WHERE owner_id={p}", (owner_id,))
        else:
            cur.execute("SELECT COUNT(*) FROM lotes")
        n_lotes = cur.fetchone()[0]

        if owner_id is not None:
            cur.execute(
                f"SELECT COUNT(*) FROM animais a JOIN lotes l ON l.id=a.lote_id"
                f" WHERE l.owner_id={p} AND COALESCE(a.ativo,1)=1",
                (owner_id,),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM animais WHERE COALESCE(ativo,1)=1")
        n_animais = cur.fetchone()[0]

        if owner_id is not None:
            cur.execute(
                f"SELECT COUNT(*) FROM mortalidade m JOIN animais a ON a.id=m.animal_id"
                f" JOIN lotes l ON l.id=a.lote_id WHERE l.owner_id={p}",
                (owner_id,),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM mortalidade")
        n_mortes = cur.fetchone()[0]

        if owner_id is not None:
            cur.execute(
                f"SELECT COUNT(*) FROM vacinas_agenda v"
                f" WHERE v.lote_id IN (SELECT id FROM lotes WHERE owner_id={p})"
                f" AND v.status='pendente'",
                (owner_id,),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM vacinas_agenda WHERE status='pendente'")
        n_vac = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM medicamentos WHERE estoque_atual<=estoque_minimo")
        n_meds = cur.fetchone()[0]

    return dict(lotes=n_lotes, animais=n_animais, mortes=n_mortes,
                vacinas_pendentes=n_vac, meds_criticos=n_meds)

def calcular_scores_lote(lote_id):
    # Calcula score de todos os animais do lote de forma agregada
    import pandas as pd
    animais = listar_animais_por_lote(lote_id)
    if not animais:
        return {}

    pesagens = listar_pesagens_todos_animais(lote_id)
    ocorrencias = listar_ocorrencias_todos_animais(lote_id)

    # Agrupar por animal_id
    pes_por_animal = {}
    for row in pesagens:
        aid = row[1]
        pes_por_animal.setdefault(aid, []).append(row)

    oc_por_animal = {}
    for row in ocorrencias:
        aid = row[1]
        oc_por_animal.setdefault(aid, []).append(row)

    scores = {}
    for a in animais:
        aid = a[0]
        ps = pes_por_animal.get(aid, [])
        ocs = oc_por_animal.get(aid, [])

        # GMD
        gmd = 0.0
        if len(ps) >= 2:
            df = pd.DataFrame(ps, columns=['id','aid','peso','data'] + (['ident'] if ps and len(ps[0]) > 4 else []))
            df['data'] = pd.to_datetime(df['data'])
            df = df.sort_values('data')
            dias = (df['data'].iloc[-1] - df['data'].iloc[0]).days
            if dias > 0:
                gmd = (df['peso'].iloc[-1] - df['peso'].iloc[0]) / dias

        pts_gmd = (50 if gmd>=1.2 else 45 if gmd>=1.0 else 38 if gmd>=0.8
                   else 30 if gmd>=0.6 else 20 if gmd>=0.4 else 10 if gmd>=0 else 0)
        pen = min(35, sum(15 if o[5]=='Alta' else 7 if o[5]=='Media' else 3 for o in ocs))
        pts_oc = max(0, 35 - pen)
        score = pts_gmd + pts_oc + 15
        classif = ("Excelente" if score>=80 else "Bom" if score>=60
                   else "Regular" if score>=40 else "Critico")
        scores[aid] = dict(score=score, classificacao=classif, gmd=round(gmd,3),
                           n_ocorrencias=len(ocs))
    return scores


# ── IA E PREDICAO ────────────────────────────────────────────────────────────

def calcular_risco_sanitario(lote_id):
    """
    Calcula score de risco sanitário 0-100 do lote.
    Fatores: mortalidade, ocorrencias graves, vacinas atrasadas, GMD negativo.
    Retorna: dict(score, nivel, fatores, recomendacoes)
    """
    import pandas as pd
    from datetime import date as _d

    score = 0
    fatores = []
    recomendacoes = []

    animais = listar_animais_por_lote(lote_id)
    if not animais:
        return dict(score=0, nivel='Sem dados', fatores=[], recomendacoes=[])

    total = len(animais)

    # ── Fator 1: Mortalidade ──────────────────────────────────────────────────
    mort = taxa_mortalidade_lote(lote_id)
    taxa_mort = mort['taxa']
    if taxa_mort >= 5:
        score += 35
        fatores.append(f"Mortalidade critica: {taxa_mort}%")
        recomendacoes.append("Acionar veterinario imediatamente")
    elif taxa_mort >= 3:
        score += 20
        fatores.append(f"Mortalidade elevada: {taxa_mort}%")
        recomendacoes.append("Investigar causa das mortes")
    elif taxa_mort >= 1:
        score += 10
        fatores.append(f"Mortalidade acima do normal: {taxa_mort}%")

    # ── Fator 2: Ocorrencias graves ───────────────────────────────────────────
    ocs = listar_ocorrencias_todos_animais(lote_id)
    graves = [o for o in ocs if o[5] == 'Alta' and o[8] == 'Em tratamento']
    medias = [o for o in ocs if o[5] == 'Media' and o[8] == 'Em tratamento']

    if len(graves) >= 3:
        score += 25
        fatores.append(f"{len(graves)} ocorrencias graves em tratamento")
        recomendacoes.append("Revisar protocolo sanitario urgente")
    elif len(graves) > 0:
        score += 15
        fatores.append(f"{len(graves)} ocorrencia(s) grave(s)")
        recomendacoes.append("Monitorar animais com ocorrencias graves")

    if len(medias) >= 5:
        score += 10
        fatores.append(f"{len(medias)} ocorrencias medias em tratamento")

    # ── Fator 3: GMD negativo ou muito baixo ─────────────────────────────────
    gmds = list(calcular_gmds_lote(lote_id).values())
    if gmds:
        gmd_medio = sum(gmds) / len(gmds)
        negativos = sum(1 for g in gmds if g < 0)
        pct_neg = negativos / len(gmds) * 100
        if pct_neg >= 30:
            score += 20
            fatores.append(f"{pct_neg:.0f}% dos animais com GMD negativo")
            recomendacoes.append("Revisar alimentacao e saude do lote")
        elif gmd_medio < 0.3:
            score += 10
            fatores.append(f"GMD medio muito baixo: {gmd_medio:.3f} kg/dia")
            recomendacoes.append("Avaliar dieta e condicao corporal")

    # ── Fator 4: Vacinas atrasadas ────────────────────────────────────────────
    vacs = listar_vacinas_agenda(lote_id)
    hoje = str(_d.today())
    atrasadas = [v for v in vacs if v[5] == 'pendente' and str(v[4]) < hoje]
    if len(atrasadas) >= 5:
        score += 15
        fatores.append(f"{len(atrasadas)} vacinas muito atrasadas")
        recomendacoes.append("Agendar vacinacao com urgencia")
    elif len(atrasadas) > 0:
        score += 7
        fatores.append(f"{len(atrasadas)} vacina(s) em atraso")
        recomendacoes.append("Verificar calendario sanitario")

    # ── Fator 5: Animais sem pesagem ─────────────────────────────────────────
    pes_map = {}
    for p in listar_pesagens_todos_animais(lote_id):
        pes_map.setdefault(p[1], []).append(p)
    sem_peso = sum(1 for a in animais if a[0] not in pes_map)
    pct_sem = sem_peso / total * 100
    if pct_sem >= 50:
        score += 5
        fatores.append(f"{pct_sem:.0f}% dos animais sem pesagem")
        recomendacoes.append("Registrar pesagem inicial dos animais")

    # ── Nivel de risco ────────────────────────────────────────────────────────
    score = min(100, score)
    if score >= 70:   nivel = 'Critico'
    elif score >= 40: nivel = 'Alto'
    elif score >= 20: nivel = 'Medio'
    elif score >= 5:  nivel = 'Baixo'
    else:             nivel = 'Saudavel'

    if not fatores:
        fatores = ['Nenhum fator de risco identificado']
    if not recomendacoes:
        recomendacoes = ['Manter monitoramento regular']

    return dict(score=score, nivel=nivel, fatores=fatores,
                recomendacoes=recomendacoes, mortalidade=taxa_mort,
                ocorrencias_graves=len(graves), gmds=gmds)


def prever_abate(lote_id, peso_alvo_kg=450.0, preco_kg=10.0, custo_diario=12.0):
    """
    Prevê data e resultado financeiro do abate para cada animal do lote.
    Retorna lista de dicts por animal com previsao.
    """
    import pandas as pd
    from datetime import date as _d, timedelta as _td

    animais = listar_animais_por_lote(lote_id)
    if not animais:
        return []

    pes_todos = listar_pesagens_todos_animais(lote_id)
    pes_map = {}
    for p in pes_todos:
        pes_map.setdefault(p[1], []).append(p)

    resultado = []
    hoje = _d.today()

    for a in animais:
        aid, ident = a[0], a[1]
        ps = sorted(pes_map.get(aid, []), key=lambda x: x[3])

        if len(ps) < 2:
            resultado.append(dict(
                animal_id=aid, identificacao=ident,
                peso_atual=ps[0][2] if ps else None,
                gmd=None, dias_restantes=None,
                data_prevista=None, receita_prevista=None,
                custo_estimado=None, margem_estimada=None,
                status='Sem dados suficientes'
            ))
            continue

        df = pd.DataFrame(ps, columns=['id','aid','peso','data'] + (['ident'] if ps and len(ps[0]) > 4 else []))
        df['data'] = pd.to_datetime(df['data'])
        df = df.sort_values('data')
        dias_total = (df['data'].iloc[-1] - df['data'].iloc[0]).days
        peso_atual = float(df['peso'].iloc[-1])

        if dias_total <= 0:
            gmd = 0.0
        else:
            gmd = (peso_atual - float(df['peso'].iloc[0])) / dias_total

        if gmd <= 0:
            resultado.append(dict(
                animal_id=aid, identificacao=ident,
                peso_atual=peso_atual, gmd=round(gmd, 3),
                dias_restantes=None, data_prevista=None,
                receita_prevista=None, custo_estimado=None,
                margem_estimada=None, status='GMD negativo'
            ))
            continue

        kg_faltando = max(0, peso_alvo_kg - peso_atual)
        dias_rest = int(kg_faltando / gmd) if gmd > 0 else 9999
        data_prev = hoje + _td(days=dias_rest)
        receita = peso_alvo_kg * preco_kg
        custo = custo_diario * dias_rest
        margem = receita - custo

        if dias_rest == 0:
            status = 'Pronto para abate'
        elif dias_rest <= 30:
            status = 'Proximo do abate'
        elif dias_rest <= 90:
            status = 'Em engorda'
        else:
            status = 'Inicio de engorda'

        resultado.append(dict(
            animal_id=aid, identificacao=ident,
            peso_atual=round(peso_atual, 1), gmd=round(gmd, 3),
            dias_restantes=dias_rest,
            data_prevista=str(data_prev),
            receita_prevista=round(receita, 2),
            custo_estimado=round(custo, 2),
            margem_estimada=round(margem, 2),
            status=status
        ))

    return sorted(resultado, key=lambda x: x['dias_restantes'] or 9999)


def detectar_anomalias_peso(lote_id):
    """
    Detecta animais com comportamento anormal de peso.
    Retorna lista de alertas com animal e descricao.
    """
    import pandas as pd

    alertas = []
    pes_todos = listar_pesagens_todos_animais(lote_id)
    animais = listar_animais_por_lote(lote_id)
    nomes = {a[0]: a[1] for a in animais}

    pes_map = {}
    for p in pes_todos:
        pes_map.setdefault(p[1], []).append(p)

    gmds_todos = []
    for aid, ps in pes_map.items():
        if len(ps) >= 2:
            df = pd.DataFrame(ps, columns=['id','aid','peso','data'] + (['ident'] if ps and len(ps[0]) > 4 else []))
            df['data'] = pd.to_datetime(df['data'])
            df = df.sort_values('data')
            dias = (df['data'].iloc[-1] - df['data'].iloc[0]).days
            if dias > 0:
                gmd = (df['peso'].iloc[-1] - df['peso'].iloc[0]) / dias
                gmds_todos.append(gmd)

    if not gmds_todos:
        return []

    media_gmd = sum(gmds_todos) / len(gmds_todos)
    desvio = (sum((g - media_gmd)**2 for g in gmds_todos) / len(gmds_todos)) ** 0.5

    for aid, ps in pes_map.items():
        if len(ps) < 2:
            continue
        df = pd.DataFrame(ps, columns=['id','aid','peso','data'] + (['ident'] if ps and len(ps[0]) > 4 else []))
        df['data'] = pd.to_datetime(df['data'])
        df = df.sort_values('data')
        dias = (df['data'].iloc[-1] - df['data'].iloc[0]).days
        if dias <= 0:
            continue
        gmd = (df['peso'].iloc[-1] - df['peso'].iloc[0]) / dias
        ident = nomes.get(aid, f'ID {aid}')

        # GMD muito abaixo da media (mais de 2 desvios)
        if desvio > 0 and gmd < media_gmd - 2 * desvio:
            alertas.append(dict(
                animal_id=aid, identificacao=ident,
                tipo='GMD anomalo',
                descricao=f'GMD {gmd:.3f} kg/d muito abaixo da media {media_gmd:.3f} kg/d do lote',
                gravidade='Alta'
            ))
        # Perda de peso recente (ultima pesagem menor que penultima)
        if len(df) >= 2:
            if float(df['peso'].iloc[-1]) < float(df['peso'].iloc[-2]):
                perda = float(df['peso'].iloc[-2]) - float(df['peso'].iloc[-1])
                alertas.append(dict(
                    animal_id=aid, identificacao=ident,
                    tipo='Perda de peso',
                    descricao=f'Perdeu {perda:.1f} kg na ultima pesagem',
                    gravidade='Media' if perda < 10 else 'Alta'
                ))

    return alertas


def resumo_ia_fazenda(owner_id=None):
    """
    Resumo de IA para todos os lotes da fazenda.
    Retorna lista de lotes com score de risco e previsao de abate.
    """
    lotes = listar_lotes(owner_id=owner_id)
    resultado = []
    for l in lotes:
        lid = l[0]
        try:
            risco = calcular_risco_sanitario(lid)
            animais = listar_animais_por_lote(lid)
            rs = resumo_lote(lid)
            resultado.append(dict(
                lote_id=lid, lote_nome=l[1],
                risco_score=risco['score'],
                risco_nivel=risco['nivel'],
                animais_ativos=rs['ativos'],
                principal_risco=risco['fatores'][0] if risco['fatores'] else '',
            ))
        except Exception:
            pass
    return sorted(resultado, key=lambda x: x['risco_score'], reverse=True)


def kpis_executivos(owner_id=None, lote_ids=None):
    """
    KPIs consolidados para o Dashboard Executivo.
    Retorna metricas financeiras, sanitarias e produtivas da fazenda.
    lote_ids: lista de IDs especifica (para vet com fazendas aprovadas)
    """
    import pandas as pd
    from datetime import date as _d, timedelta as _td

    if lote_ids is not None:
        # Buscar lotes pelo ID diretamente
        lotes = [l for l in listar_lotes(owner_id=None) if l[0] in lote_ids]
    else:
        lotes = listar_lotes(owner_id=owner_id)
    if not lotes:
        return {}

    ids_lotes = [l[0] for l in lotes]

    # ── Contagens basicas ─────────────────────────────────────────────────────
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        placeholders = ','.join([str(p)] * len(ids_lotes)) if _usar_postgres() else ','.join(['?'] * len(ids_lotes))

        cur.execute(f"SELECT COUNT(*) FROM animais a JOIN lotes l ON l.id=a.lote_id WHERE l.id IN ({placeholders}) AND COALESCE(a.ativo,1)=1", ids_lotes)
        total_animais = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM mortalidade m JOIN animais a ON a.id=m.animal_id JOIN lotes l ON l.id=a.lote_id WHERE l.id IN ({placeholders})", ids_lotes)
        total_mortes = cur.fetchone()[0]

        cur.execute(f"SELECT COALESCE(SUM(o.custo),0) FROM ocorrencias o JOIN animais a ON a.id=o.animal_id JOIN lotes l ON l.id=a.lote_id WHERE l.id IN ({placeholders})", ids_lotes)
        custo_sanitario = float(cur.fetchone()[0] or 0)

        cur.execute(f"SELECT COUNT(*) FROM vacinas_agenda v WHERE v.lote_id IN ({placeholders}) AND v.status='pendente'", ids_lotes)
        vacinas_pend = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM ocorrencias o JOIN animais a ON a.id=o.animal_id JOIN lotes l ON l.id=a.lote_id WHERE l.id IN ({placeholders}) AND o.status='Em tratamento'", ids_lotes)
        em_tratamento = cur.fetchone()[0]

    # ── GMD medio geral ───────────────────────────────────────────────────────
    todos_gmds = []
    for lid in ids_lotes:
        gmds = calcular_gmds_lote(lid)
        todos_gmds.extend(g for g in gmds.values() if g > 0)

    gmd_geral = sum(todos_gmds) / len(todos_gmds) if todos_gmds else 0

    # ── Taxa de mortalidade geral ─────────────────────────────────────────────
    total_cabecas = sum(listar_lotes(owner_id=owner_id)[i][4] or 0 for i in range(len(lotes)))
    taxa_mort_geral = round(total_mortes / max(total_cabecas, 1) * 100, 2)

    # ── Risco medio dos lotes ─────────────────────────────────────────────────
    riscos = []
    for lid in ids_lotes:
        try:
            r = calcular_risco_sanitario(lid)
            riscos.append(r['score'])
        except Exception:
            pass
    risco_medio = round(sum(riscos) / len(riscos), 1) if riscos else 0

    # ── Lote mais critico ─────────────────────────────────────────────────────
    resumo_r = resumo_ia_fazenda(owner_id=owner_id)
    lote_critico = resumo_r[0] if resumo_r else None

    # ── Evolucao de animais (ultimos 6 meses) ────────────────────────────────
    evolucao = []
    hoje = _d.today()
    for m in range(5, -1, -1):
        mes_ref = hoje.replace(day=1) - _td(days=m*30)
        mes_str = mes_ref.strftime('%b/%y')
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM animais a JOIN lotes l ON l.id=a.lote_id"
                f" WHERE l.id IN ({placeholders})"
                f" AND COALESCE(a.ativo,1)=1",
                ids_lotes,
            )
            n = cur.fetchone()[0]
        evolucao.append({'mes': mes_str, 'animais': n})

    return dict(
        total_lotes=len(lotes),
        total_animais=total_animais,
        total_mortes=total_mortes,
        taxa_mortalidade=taxa_mort_geral,
        custo_sanitario=custo_sanitario,
        custo_por_animal=round(custo_sanitario / max(total_animais, 1), 2),
        vacinas_pendentes=vacinas_pend,
        em_tratamento=em_tratamento,
        gmd_geral=round(gmd_geral, 3),
        risco_medio=risco_medio,
        lote_critico=lote_critico,
        evolucao_animais=evolucao,
        n_lotes_alto_risco=sum(1 for r in riscos if r >= 40),
    )


def sincronizar_todos_lotes():
    lotes = listar_lotes()
    resultados = []
    for l in lotes:
        n = atualizar_qtd_lote(l[0])
        resultados.append((l[0], l[1], n))
    return resultados
