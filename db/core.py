# db/core.py -- Fundacao da camada de persistencia
# Conexao, pool, helpers de query e cache.
# Todos os modulos de dominio fazem: from db.core import *

# database.py -- Camada de persistencia do Sistema de Gestao Pecuaria
# Suporta PostgreSQL (Supabase) e SQLite (fallback local)

import os
import hashlib
import secrets
from contextlib import contextmanager
from datetime import date as _date, timedelta as _td

# ── Planos do sistema ───────────────────────────────────────────────────────
PLANOS_FAZENDEIRO = {
    'trial':        dict(nome='Trial 30 dias',  limite_animais=50,    preco=0,
                        descricao='30 dias gratis, ate 50 animais'),
    'starter':      dict(nome='Starter',         limite_animais=100,   preco=89,
                        descricao='Ate 100 animais, suporte por email'),
    'profissional': dict(nome='Profissional',    limite_animais=500,   preco=189,
                        descricao='Ate 500 animais, relatorios avancados'),
    'premium':      dict(nome='Premium',         limite_animais=2000,  preco=389,
                        descricao='Ate 2000 animais, IA completa'),
    'enterprise':   dict(nome='Enterprise',      limite_animais=99999, preco=789,
                        descricao='Ilimitado, multi-fazenda, suporte prioritario'),
}
PLANOS_VETERINARIO = {
    'trial':        dict(nome='Trial 30 dias',   limite_fazendas=2,   preco=0,
                        descricao='30 dias gratis, ate 2 fazendas'),
    'vet_solo':     dict(nome='Vet Solo',         limite_fazendas=5,   preco=119,
                        descricao='Ate 5 fazendas'),
    'vet_pro':      dict(nome='Vet Pro',          limite_fazendas=999, preco=249,
                        descricao='Fazendas ilimitadas + receituario digital'),
}

# Mensagens de upgrade por plano (fazendeiro)
UPGRADE_MSG_FAZENDEIRO = {
    'trial':        'Faca upgrade para o plano Starter (R$ 89/mes) e gerencie ate 100 animais.',
    'starter':      'Faca upgrade para o plano Profissional (R$ 189/mes) e gerencie ate 500 animais.',
    'profissional': 'Faca upgrade para o plano Premium (R$ 389/mes) e gerencie ate 2.000 animais.',
    'premium':      'Faca upgrade para o plano Enterprise (R$ 789/mes) para animais ilimitados e multi-fazenda.',
    'enterprise':   'Voce ja tem o plano maximo.',
}
UPGRADE_MSG_VETERINARIO = {
    'trial':    'Faca upgrade para o Vet Solo (R$ 119/mes) e gerencie ate 5 fazendas.',
    'vet_solo': 'Faca upgrade para o Vet Pro (R$ 249/mes) para fazendas ilimitadas + receituario digital.',
    'vet_pro':  'Voce ja tem o plano maximo.',
}

# Planos detalhados (usados em obter_plano, emails)
_PLANOS = {
    "free": {
        "nome":            "Free",
        "preco":           0,
        "limite_animais":  50,
        "limite_fazendas": 1,
        "modulo_vet":      False,
        "descricao":       "Ate 50 animais, 1 fazenda, funcoes basicas",
    },
    "pro": {
        "nome":            "Pro",
        "preco":           99,
        "limite_animais":  500,
        "limite_fazendas": 3,
        "modulo_vet":      False,
        "descricao":       "Ate 500 animais, 3 fazendas, relatorios avancados",
    },
    "vet": {
        "nome":            "Vet",
        "preco":           199,
        "limite_animais":  2000,
        "limite_fazendas": 10,
        "modulo_vet":      True,
        "descricao":       "Ilimitado para vets, ate 10 fazendas atendidas",
    },
    "enterprise": {
        "nome":            "Enterprise",
        "preco":           0,
        "limite_animais":  999999,
        "limite_fazendas": 999,
        "modulo_vet":      True,
        "descricao":       "Personalizado, suporte dedicado",
    },
}



# ── Loggers centralizados ───────────────────────────────────────────────────
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
        _log_war.debug('excecao tratada: %s', exc_info=True)
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
    url = ""
    try:
        import streamlit as st
        # Tentar múltiplos formatos de secrets
        _sec = st.secrets
        if "database" in _sec and "url" in _sec["database"]:
            url = _sec["database"]["url"]
        elif "DATABASE_URL" in _sec:
            url = _sec["DATABASE_URL"]
        elif "SUPABASE_DB_URL" in _sec:
            url = _sec["SUPABASE_DB_URL"]
    except Exception:
        pass
    # Fallback para variáveis de ambiente
    if not url:
        url = (os.environ.get("DATABASE_URL")
               or os.environ.get("SUPABASE_DB_URL", ""))
    # Supabase: preferir transaction pooler (porta 6543)
    if url and "pooler.supabase.com:5432" in url:
        url = url.replace(":5432/", ":6543/")
    return url

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
# Pool de conexoes para PostgreSQL
# Supabase session mode: max 15 conexoes totais
# Usamos max=3 por worker para suportar ate 5 workers simultaneos
_pg_pool  = None
_pool_lock = None

def _get_pool_lock():
    global _pool_lock
    if _pool_lock is None:
        import threading
        _pool_lock = threading.Lock()
    return _pool_lock

def _get_pool():
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    with _get_pool_lock():
        if _pg_pool is not None:  # double-check após lock
            return _pg_pool
        try:
            import psycopg2.pool
            url = _get_pg_url()
            if not url:
                return None
            # Transaction mode (porta 6543): sem limite de sessão
            # Pool maior para suportar telas com múltiplas queries simultâneas
            _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                2, 8, url, connect_timeout=10,
                keepalives=1, keepalives_idle=30,
                keepalives_interval=5, keepalives_count=3,
            )
            _log_db.info("Pool PostgreSQL criado (min=2, max=8)")
            return _pg_pool
        except Exception as e:
            _log_war.warning("Falha ao criar pool Postgres: %s", e)
            return None

def _fechar_pool():
    """Fecha o pool ao encerrar — chamar no finally do app."""
    global _pg_pool
    if _pg_pool:
        try:
            _pg_pool.closeall()
        except Exception:
            pass
        _pg_pool = None

@contextmanager
def _conexao():
    if _usar_postgres():
        import psycopg2, psycopg2.pool, time as _time_conn
        pool = _get_pool()
        conn = None

        if pool:
            # Tentar obter conexão do pool com retry
            _tentativas = 2
            for _t in range(_tentativas):
                try:
                    conn = pool.getconn()
                    break
                except psycopg2.pool.PoolError:
                    if _t < _tentativas - 1:
                        _time_conn.sleep(0.2)
                    else:
                        _log_war.debug(
                            "Pool ocupado — usando conexão direta"
                        )
                        conn = None

        if conn is None:
            # Fallback: conexão direta sem pool
            url = _get_pg_url()
            if url:
                try:
                    conn = psycopg2.connect(url, connect_timeout=10)
                except Exception as e:
                    _log_err.error("Falha de conexão direta: %s", e)
                    raise RuntimeError(
                        "Banco de dados temporariamente indisponível. "
                        "Tente novamente em instantes."
                    ) from e

        if conn is None:
            raise RuntimeError("Banco de dados indisponível.")

        conn.autocommit = False
        _via_pool = pool and conn in getattr(pool, '_used', {})
        try:
            yield conn
            conn.commit()
        except Exception:
            try: conn.rollback()
            except Exception: pass
            raise
        finally:
            try:
                if pool and _via_pool:
                    # Resetar estado da conexão antes de devolver ao pool
                    try:
                        if conn.status != 0:  # 0 = STATUS_READY
                            conn.rollback()
                    except Exception:
                        pass
                    pool.putconn(conn)
                else:
                    conn.close()
            except Exception:
                pass
    else:
        import sqlite3
        # Permitir override do caminho para testes isolados
        db_path = os.environ.get("AUROQUE_DB_PATH") or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "pecuaria.db"
        )
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

# ── CACHE DE DADOS (TTL 60s) ─────────────────────────────────
import functools as _functools
import time as _time

_cache_store = {}

def _cached(fn, ttl=60):
    """Decorator de cache simples com TTL para funções de listagem."""
    @_functools.wraps(fn)
    def wrapper(*args, **kwargs):
        key = (fn.__name__, args, tuple(sorted(kwargs.items())))
        now = _time.time()
        if key in _cache_store:
            val, ts = _cache_store[key]
            if now - ts < ttl:
                return val
        result = fn(*args, **kwargs)
        _cache_store[key] = (result, now)
        return result
    return wrapper


def invalidar_cache(prefixo=None):
    """Invalida cache — chamar após escrita no banco."""
    global _cache_store
    if prefixo:
        _cache_store = {k: v for k, v in _cache_store.items()
                       if not str(k[0]).startswith(prefixo)}
    else:
        _cache_store = {}


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
