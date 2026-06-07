# database.py -- Camada de persistencia (AGREGADOR)
# A fundacao (conexao, pool, _ph, _fetch, cache, planos) foi movida para db/core.py
# Este arquivo mantem migrations, schema e funcoes de dominio.
# Importacoes existentes (from database import ...) continuam funcionando.

import os
import hashlib
import secrets
from contextlib import contextmanager
from datetime import date as _date, timedelta as _td

# Importar toda a fundacao do core
from db.core import *
from db.core import (
    _usar_postgres, _diagnostico_banco, _get_pg_url, _date_add, _cast_date,
    _get_pool_lock, _get_pool, _fechar_pool, _conexao, _cached,
    _ph, _fetch, _fetchone,
    PLANOS_FAZENDEIRO, PLANOS_VETERINARIO,
    UPGRADE_MSG_FAZENDEIRO, UPGRADE_MSG_VETERINARIO,
)


# ── Schema e migrations (movidos para db/schema.py) ──────────────────────────
from db.schema import (
    _MIGRATIONS, _log_db, _log_err, _log_war,
    _criar_tabela_schema_version, _versoes_aplicadas, _registrar_versao,
    aplicar_migrations, _garantir_tabelas_vet,
    _garantir_colunas_vacinas_agenda, _garantir_coluna_crmv,
    inicializar_banco, _migrar_banco,
)

# ── Pesagens e GMD (movidos para db/pesagens.py) ─────────────────────────────
from db.pesagens import (
    adicionar_pesagem, listar_pesagens, atualizar_pesagem, excluir_pesagem,
    listar_pesagens_lote, calcular_gmd_temporal, listar_pesagens_todos_animais,
    calcular_gmds_lote, _gmd_animal, importar_pesagens_csv,
)

# ── Vendas (movidos para db/vendas.py) ───────────────────────────────────────
from db.vendas import (
    marcar_animal_vendido, registrar_receita_parcial, venda_parcial_lote,
    listar_vendas_lote, registrar_venda_lote, marcar_em_venda,
    cancelar_venda_lote, listar_lotes_historico, obter_resumo_venda_lote,
    listar_animais_vendidos_lote, listar_todas_vendas,
)

# ── Animais (movidos para db/animais.py) ─────────────────────────────────────
from db.animais import (
    STATUS_ANIMAL,
    listar_animais, listar_animais_por_lote, adicionar_animal, obter_animal,
    atualizar_animal, excluir_animal, atualizar_status_animal,
    listar_animais_por_status, contagem_status_animais, importar_animais_csv,
)

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
            cur.execute(
                f"SELECT id,nome,descricao,data_entrada,qtd_comprada,"
                f"qtd_recebida,transporte,"
                f"COALESCE(tipo_alimentacao,''),COALESCE(tipo_dieta,''),"
                f"COALESCE(preco_por_animal,0),COALESCE(data_venda,''),"
                f"COALESCE(owner_id,0),"
                f"COALESCE(status,'ATIVO') "
                f"FROM lotes WHERE owner_id={p} "
                f"AND COALESCE(ativo,1)=1 "
                f"AND UPPER(COALESCE(status,'ATIVO')) "
                f"NOT IN ('VENDIDO','ARQUIVADO','ENCERRADO') "
                f"ORDER BY data_entrada DESC,id DESC",
                (owner_id,),
            )
        else:
            cur.execute(
                "SELECT id,nome,descricao,data_entrada,qtd_comprada,"
                "qtd_recebida,transporte,"
                "COALESCE(tipo_alimentacao,''),COALESCE(tipo_dieta,''),"
                "COALESCE(preco_por_animal,0),COALESCE(data_venda,''),"
                "COALESCE(owner_id,0) "
                "FROM lotes ORDER BY data_entrada DESC,id DESC"
            )
        # Usar fetchall() com indices posicionais para evitar KeyError
        rows = cur.fetchall()
        return [
            (r[0],r[1],r[2],r[3],r[4],r[5],r[6],
             r[7],r[8],float(r[9] or 0),str(r[10] or ''),r[11],
             str(r[12] or 'ATIVO'))
            for r in rows
        ]

def obter_lote(lote_id):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,nome,descricao,data_entrada,qtd_comprada,qtd_recebida,"
            f"transporte,"
            f"COALESCE(tipo_alimentacao,''),COALESCE(tipo_dieta,''),"
            f"COALESCE(preco_por_animal,0),COALESCE(data_venda,''),"
            f"COALESCE(owner_id,0) "
            f"FROM lotes WHERE id={p}",
            (lote_id,)
        )
        r = cur.fetchone()
        if not r:
            return None
        return (
            r[0],r[1],r[2],r[3],r[4],r[5],r[6],
            r[7],r[8],float(r[9] or 0),str(r[10] or ''),r[11]
        )

def atualizar_lote(lote_id, nome, descricao, data_entrada, qtd_comprada, qtd_recebida, transporte, preco_por_animal=None):
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM animais "
            f"WHERE lote_id={p} "
            f"AND COALESCE(ativo,1)=1 "
            f"AND UPPER(COALESCE(status,'ATIVO')) NOT IN ('VENDIDO','MORTO','DESCARTADO')",
            (lote_id,)
        )
        ativos = cur.fetchone()[0]
        cur.execute(
            f"UPDATE lotes SET nome={p},descricao={p},data_entrada={p},qtd_comprada={p},qtd_recebida={p},transporte={p} WHERE id={p}",
            (nome, descricao, data_entrada, qtd_comprada, ativos, transporte, lote_id),
        )
        if preco_por_animal is not None:
            cur.execute(f"UPDATE lotes SET preco_por_animal={p} WHERE id={p}", (preco_por_animal, lote_id))

def excluir_lote(lote_id):
    """Exclui lote com cada passo em transacao independente."""
    p = _ph()

    # Passo 1: buscar animais
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id FROM animais WHERE lote_id={p}", (lote_id,))
        aids = [r[0] for r in cur.fetchall()]

    # Passo 2: excluir registros dos animais
    for aid in aids:
        for tbl in ['pesagens', 'ocorrencias', 'medicamentos_uso']:
            try:
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(f"DELETE FROM {tbl} WHERE animal_id={p}", (aid,))
                    conn.commit()
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM animais WHERE lote_id={p}", (lote_id,))
            conn.commit()
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    for tbl in ['vacinas_agenda', 'reproducao', 'vendas_lote']:
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(f"DELETE FROM {tbl} WHERE lote_id={p}", (lote_id,))
                conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM lotes WHERE id={p}", (lote_id,))
        conn.commit()

def buscar_animal_global(termo, owner_id):
    """Busca animal por identificacao ou nome em todos os lotes do owner."""
    if not termo or not owner_id:
        return []
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT a.id, a.identificacao, a.raca, a.sexo, "
                f"l.nome as lote_nome "
                f"FROM animais a "
                f"JOIN lotes l ON l.id = a.lote_id "
                f"WHERE l.owner_id = {p} "
                f"AND a.ativo = 1 "
                f"AND (LOWER(a.identificacao) LIKE LOWER({p}) "
                f"     OR LOWER(COALESCE(a.nome,'')) LIKE LOWER({p})) "
                f"ORDER BY a.identificacao "
                f"LIMIT 10",
                (owner_id, f"%{termo}%", f"%{termo}%")
            )
            rows = cur.fetchall()
        return [
            dict(id=r[0], identificacao=r[1],
                 raca=r[2], sexo=r[3], lote_nome=r[4])
            for r in rows
        ]
    except Exception as _e:
        _log_war.debug("buscar_animal_global: %s", _e)
        return []


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

@lambda _f: _cached(_f, ttl=30)
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
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
        return vencidos


# ── USUARIOS ─────────────────────────────────────────────────────────────────
def _hash_senha(senha, salt):
    """Hash legado SHA256. Mantido para verificacao de senhas antigas."""
    return hashlib.sha256((salt + senha).encode()).hexdigest()


# ─── BCRYPT — novo sistema de hash ───────────────────────────────────────────
def _bcrypt_hash(senha):
    """Gera hash bcrypt com salt embutido. Retorna string."""
    try:
        import bcrypt
        h = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=12))
        return h.decode("utf-8")
    except ImportError:
        # Fallback se bcrypt nao estiver instalado
        import secrets
        s = secrets.token_hex(16)
        return f"SHA256${s}${_hash_senha(senha, s)}"


def _bcrypt_verify(senha, hash_armazenado):
    """Verifica senha contra hash bcrypt. Retorna bool."""
    if not hash_armazenado:
        return False
    try:
        import bcrypt
        # Bcrypt hashes comecam com $2a$, $2b$, $2y$
        if hash_armazenado.startswith("$2"):
            return bcrypt.checkpw(
                senha.encode("utf-8"),
                hash_armazenado.encode("utf-8")
            )
    except ImportError:
        pass
    # Fallback SHA256 ($SHA256$salt$hash)
    if hash_armazenado.startswith("SHA256$"):
        try:
            _, salt, hash_esperado = hash_armazenado.split("$", 2)
            return _hash_senha(senha, salt) == hash_esperado
        except Exception:
            _log_war.debug('excecao tratada: %s', exc_info=True)
            return False
    return False


def _is_bcrypt_hash(hash_str):
    """Detecta se string e hash bcrypt."""
    return bool(hash_str) and str(hash_str).startswith("$2")

def email_valido(email):
    """Valida formato de email."""
    import re as _re
    padrao = r".+@.+[.].+"
    return bool(_re.match(padrao, (email or "").strip()))


def email_ja_cadastrado(email):
    """Verifica se o email já existe no banco."""
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM usuarios WHERE email={p}",
                (email.strip().lower(),)
            )
            r = cur.fetchone()
            return (r[0] if r else 0) > 0
    except Exception as _e:
        _log_war.debug("email_ja_cadastrado: %s", _e)
        return False


def auto_registrar_usuario(nome, email, senha, perfil="fazendeiro"):
    """Registra novo usuário com trial de 14 dias.
    Retorna: (sucesso: bool, mensagem: str, user_id: int|None)
    """
    from datetime import date, timedelta

    # Validações
    if not nome or len(nome.strip()) < 2:
        return False, "Nome deve ter pelo menos 2 caracteres.", None
    if not email_valido(email):
        return False, "E-mail inválido. Verifique o formato.", None
    if not senha or len(senha) < 6:
        return False, "Senha deve ter pelo menos 6 caracteres.", None
    if email_ja_cadastrado(email.strip().lower()):
        return False, "Este e-mail já está cadastrado. Faça login.", None

    # Datas do trial
    hoje        = date.today()
    trial_fim   = hoje + timedelta(days=14)

    p = _ph()
    try:
        h    = _bcrypt_hash(senha)
        salt = ""
        nome_limpo  = nome.strip()
        email_limpo = email.strip().lower()

        with _conexao() as conn:
            cur = conn.cursor()
            if _usar_postgres():
                cur.execute(
                    f"INSERT INTO usuarios "
                    f"(nome,email,senha_hash,salt,perfil,ativo,"
                    f" trial_inicio,plano,plano_expira) "
                    f"VALUES({p},{p},{p},{p},{p},1,{p},{p},{p}) "
                    f"RETURNING id",
                    (nome_limpo, email_limpo, h, salt, perfil,
                     str(hoje), "trial", str(trial_fim)),
                )
                uid = cur.fetchone()[0]
            else:
                cur.execute(
                    f"INSERT INTO usuarios "
                    f"(nome,email,senha_hash,salt,perfil,ativo,"
                    f" trial_inicio,plano,plano_expira) "
                    f"VALUES({p},{p},{p},{p},{p},1,{p},{p},{p})",
                    (nome_limpo, email_limpo, h, salt, perfil,
                     str(hoje), "trial", str(trial_fim)),
                )
                uid = cur.lastrowid
            # Atualizar status_conta separadamente (coluna pode ser nova)
            try:
                cur.execute(
                    f"UPDATE usuarios SET status_conta='trial' WHERE id={p}",
                    (uid,)
                )
            except Exception:
                pass
            # owner_id = si mesmo
            cur.execute(
                f"UPDATE usuarios SET owner_id={p} WHERE id={p}",
                (uid, uid)
            )
            conn.commit()

        _log_db.info(
            "Novo usuário registrado: id=%s email=%s trial_ate=%s",
            uid, email_limpo, trial_fim
        )
        return True, f"Conta criada! Seu trial gratuito vai até {trial_fim.strftime('%d/%m/%Y')}.", uid

    except Exception as _e:
        _log_err.error("auto_registrar_usuario: %s", _e)
        return False, f"Erro ao criar conta: {_e}", None


def criar_usuario(nome, email, senha, perfil="fazendeiro", fazenda_id=None, owner_id=None):
    """Cria usuario com hash bcrypt (sistema novo)."""
    p = _ph()
    h = _bcrypt_hash(senha)
    salt = ""  # bcrypt embute salt no hash
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

def obter_nome_usuario(user_id):
    """Retorna o nome do usuario pelo id."""
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT nome FROM usuarios WHERE id={p}", (user_id,))
        r = cur.fetchone()
        return r[0] if r else f"Fazenda {user_id}"


def autenticar_usuario(email, senha):
    from datetime import datetime, date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,nome,email,senha_hash,salt,perfil,fazenda_id,ativo,"
            f"COALESCE(owner_id,id) as owner_id,"
            f"plano,plano_expira,"
            f"COALESCE(status_conta,'ativo') as status_conta "
            f"FROM usuarios WHERE LOWER(email)=LOWER({p})",
            (email,)
        )
        r = _fetchone(cur)

    if not r or not r["ativo"]:
        return None

    # Verificar senha — suporta bcrypt (novo) e SHA256 (legado)
    _hash_db = r.get("senha_hash", "")
    _salt_db = r.get("salt", "")
    _senha_ok = False

    if _hash_db.startswith("$2b$") or _hash_db.startswith("$2a$"):
        # Hash bcrypt puro
        try:
            import bcrypt as _bcrypt
            _senha_ok = _bcrypt.checkpw(
                senha.encode("utf-8"), _hash_db.encode("utf-8")
            )
        except Exception:
            _senha_ok = False
    elif _hash_db.startswith("SHA256$"):
        # Fallback bcrypt sem lib: SHA256$salt$hash
        try:
            _, _s, _h = _hash_db.split("$", 2)
            _senha_ok = (_hash_senha(senha, _s) == _h)
        except Exception:
            _senha_ok = False
    else:
        # Hash SHA256 legado
        _senha_ok = (_hash_senha(senha, _salt_db) == _hash_db)

    if not _senha_ok:
        return None

    # ── Verificar expiração do plano ──────────────────────────────
    plano_expira  = r.get("plano_expira")
    status_conta  = r.get("status_conta", "ativo")
    plano_atual   = r.get("plano", "free")
    plano_expirado = False

    if plano_expira and plano_atual not in ("free",):
        try:
            data_exp = date.fromisoformat(str(plano_expira)[:10])
            if date.today() > data_exp:
                plano_expirado = True
                _log_war.warning(
                    "Login com plano expirado: user_id=%s plano=%s expirou=%s",
                    r["id"], plano_atual, plano_expira
                )
                # Atualizar status no banco
                try:
                    _p2 = _ph()
                    with _conexao() as conn:
                        cur2 = conn.cursor()
                        cur2.execute(
                            f"UPDATE usuarios SET status_conta='expirado',"
                            f"plano='free' WHERE id={_p2}",
                            (r["id"],)
                        )
                        conn.commit()
                    plano_atual  = "free"
                    status_conta = "expirado"
                except Exception as _eu:
                    _log_war.warning("Erro ao atualizar plano expirado: %s", _eu)
        except (ValueError, TypeError):
            pass

    # Registrar last_login e access_log
    try:
        _now = datetime.utcnow().isoformat()
        _p2  = _ph()
        with _conexao() as conn:
            cur2 = conn.cursor()
            cur2.execute(
                f"UPDATE usuarios SET last_login={_p2} WHERE id={_p2}",
                (_now, r["id"])
            )
            conn.commit()
        with _conexao() as conn:
            cur2 = conn.cursor()
            cur2.execute(
                f"INSERT INTO access_log (user_id,rota,criado_em) "
                f"VALUES({_p2},{_p2},{_p2})",
                (r["id"], "login", _now)
            )
            conn.commit()
    except Exception as _ew:
        _log_err.error("erro em autenticar_usuario: %s", _ew)

    owner = r.get("owner_id") or r["id"]
    return dict(
        id=r["id"], nome=r["nome"], email=r["email"],
        perfil=r["perfil"], fazenda_id=r["fazenda_id"],
        owner_id=owner,
        plano=plano_atual,
        status_conta=status_conta,
        plano_expirado=plano_expirado,
    )

@lambda _f: _cached(_f, ttl=60)
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
    h = _bcrypt_hash(nova_senha)
    salt = ""
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

def verificar_limite_animais(owner_id, n_novos=0):
    """Verifica limite de animais. n_novos: quantos serão adicionados."""
    limites = obter_limites_usuario(owner_id)
    if not limites:
        return dict(ok=False, pode=False, atual=0, limite=0, disponiveis=0,
                    msg='Usuario nao encontrado', upgrade='')
    if limites['perfil'] == 'admin':
        return dict(ok=True, pode=True, atual=0, limite=99999, disponiveis=99999,
                    msg='Admin sem limite', upgrade='')
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM animais a JOIN lotes l ON l.id=a.lote_id"
            f" WHERE l.owner_id={p} AND COALESCE(a.ativo,1)=1",
            (owner_id,),
        )
        atual = cur.fetchone()[0]
    limite    = limites['limite_animais']
    disponiv  = max(0, limite - atual)
    pode      = (atual + n_novos) <= limite
    plano_k   = limites.get('plano_nome', 'trial')
    upgrade   = UPGRADE_MSG_FAZENDEIRO.get(plano_k, '')
    if pode:
        msg = f'{atual}/{limite} animais ({disponiv} disponiveis)'
    else:
        msg = (f'Limite atingido: {atual}/{limite} animais. '
               f'Voce tentou adicionar {n_novos} mas so ha {disponiv} vagas. {upgrade}')
    return dict(ok=pode, pode=pode, atual=atual, limite=limite,
                disponiveis=disponiv, msg=msg, upgrade=upgrade)

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
def adicionar_vacina_agenda(lote_id, nome_vacina, data_prevista, observacao="",
                           medicamento_id=None, quantidade_dose=0,
                           agendado_por=None, animal_id=None):
    """Agenda vacina. Verifica colunas existentes antes de inserir."""
    p = _ph()

    # Descobrir colunas existentes na tabela
    _cols_existentes = set()
    if _usar_postgres():
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='vacinas_agenda' AND table_schema='public'"
                )
                _cols_existentes = {r[0] for r in cur.fetchall()}
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    cols   = ["lote_id", "nome_vacina", "data_prevista", "observacao"]
    vals   = [lote_id, nome_vacina, str(data_prevista), observacao or ""]

    # Colunas extras - incluir apenas se existirem no banco
    extras = [
        ("medicamento_id",  medicamento_id),
        ("quantidade_dose", float(quantidade_dose or 0)),
        ("agendado_por",    agendado_por),
        ("animal_id",       animal_id),
    ]
    for col, val in extras:
        if not _usar_postgres() or col in _cols_existentes:
            cols.append(col)
            vals.append(val)

    placeholders = ",".join([p] * len(cols))
    cols_str     = ",".join(cols)

    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO vacinas_agenda ({cols_str}) "
                f"VALUES({placeholders}) RETURNING id",
                tuple(vals)
            )
            vid = cur.fetchone()[0]
            conn.commit()
            return vid
        else:
            cur.execute(
                f"INSERT INTO vacinas_agenda ({cols_str}) VALUES({placeholders})",
                tuple(vals)
            )
            return cur.lastrowid

def registrar_vacina_realizada(vacina_id, data_realizada,
                               confirmado_por=None, obs_extra="",
                               animal_id_override=None):
    """Confirma vacina: atualiza agenda, baixa no estoque de quem agendou,
    e registra ocorrencia Vacinacao nos animais do lote."""
    p = _ph()

    # Descobrir colunas existentes
    _cols = set()
    if _usar_postgres():
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='vacinas_agenda' AND table_schema='public'"
                )
                _cols = {r[0] for r in cur.fetchall()}
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    _extras_disp = [c for c in
                    ["medicamento_id","quantidade_dose","agendado_por","animal_id"]
                    if not _cols or c in _cols]
    sel_extras_str = ("," + ",".join(_extras_disp)) if _extras_disp else ""

    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT lote_id,nome_vacina{sel_extras_str} "
            f"FROM vacinas_agenda WHERE id={p}",
            (vacina_id,)
        )
        row = cur.fetchone()

    if not row:
        return False

    # Mapear por posicao baseada nas colunas realmente buscadas
    _row_cols = ["lote_id","nome_vacina"] + _extras_disp
    _row_map  = {c: row[i] for i, c in enumerate(_row_cols)}

    lote_id   = _row_map["lote_id"]
    nome_vac  = _row_map["nome_vacina"]
    med_id    = _row_map.get("medicamento_id")
    qtd_dose  = float(_row_map.get("quantidade_dose") or 0)
    animal_id = _row_map.get("animal_id")

    # Marcar como realizada
    set_extra = ""
    set_vals  = [data_realizada]
    if ("confirmado_por" in _cols or not _cols) and confirmado_por:
        set_extra = f",confirmado_por={p}"
        set_vals.append(confirmado_por)
    set_vals.append(vacina_id)

    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE vacinas_agenda SET data_realizada={p},"
            f"status='realizado'{set_extra} WHERE id={p}",
            tuple(set_vals)
        )
        conn.commit()

    # Dar baixa no estoque do medicamento vinculado
    if med_id and qtd_dose > 0:
        try:
            atualizar_estoque(med_id, qtd_dose)
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    obs_ocorr = f"Vacinacao: {nome_vac}"
    if obs_extra:
        obs_ocorr += f" | {obs_extra}"

    # animal_id_override permite redefinir o alvo na confirmacao
    _animal_alvo = animal_id_override if animal_id_override is not None else animal_id
    animais_lote = listar_animais_por_lote(lote_id)
    alvos = [_animal_alvo] if _animal_alvo else [a[0] for a in animais_lote]
    for aid in alvos:
        adicionar_ocorrencia(
            animal_id=aid, data=data_realizada,
            tipo="Vacinacao", descricao=obs_ocorr,
            gravidade="Baixa", custo=0,
            dias_recuperacao=0, status="Resolvido"
        )

    invalidar_cache("listar_animais")
    invalidar_cache("listar_lotes")
    return True

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
    if owner_id is None:
        return None
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
        try:
            # IMPORTANTE: parenteses para que AND owner_id se aplique a toda a condicao
            cur.execute(
                f"SELECT id,nome,unidade,estoque_atual,estoque_minimo,validade,custo_unitario FROM medicamentos"
                f" WHERE (estoque_atual<=estoque_minimo OR (validade IS NOT NULL AND {_cast_date('validade')}<={_date_add(30)}))"
                f"{filtro}",
                params,
            )
            rows = _fetch(cur)
            return [(r["id"],r["nome"],r["unidade"],r["estoque_atual"],r["estoque_minimo"],r["validade"],r["custo_unitario"]) for r in rows]
        except Exception:
            try: conn.rollback()
            except: pass
            return []

def verificar_carencia(animal_id):
    """Verifica carencia do animal em medicamentos_uso E carencias_ativas."""
    import datetime
    p  = _ph()
    hoje = datetime.date.today()
    meds = []

    # Fonte 1: medicamentos_uso (registro de uso de estoque)
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT mu.data_uso,m.nome,m.carencia_dias "
                f"FROM medicamentos_uso mu "
                f"JOIN medicamentos m ON m.id=mu.medicamento_id "
                f"WHERE mu.animal_id={p} AND m.carencia_dias>0",
                (animal_id,),
            )
            for r in _fetch(cur):
                try:
                    dt = datetime.datetime.strptime(
                        str(r["data_uso"])[:10], "%Y-%m-%d").date()
                    libera = dt + datetime.timedelta(days=int(r["carencia_dias"]))
                    if libera >= hoje:
                        meds.append(dict(
                            medicamento=r["nome"],
                            uso=str(r["data_uso"]),
                            carencia_dias=r["carencia_dias"],
                            libera_em=str(libera)
                        ))
                except Exception as _ew:
                    _log_war.debug("excecao ignorada: %s", _ew)
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT medicamento,data_aplicacao,carencia_dias,data_liberacao "
                f"FROM carencias_ativas "
                f"WHERE animal_id={p} AND ativo=1 AND data_liberacao >= {p}",
                (animal_id, str(hoje)),
            )
            for r in cur.fetchall():
                meds.append(dict(
                    medicamento=r[0],
                    uso=str(r[1]),
                    carencia_dias=r[2],
                    libera_em=str(r[3])
                ))
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

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
def lote_ja_vendido(lote_id):
    """Verifica se lote ja foi vendido (sem animais ativos)."""
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p} AND ativo=1",(lote_id,))
            ativos = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM animais WHERE lote_id={p}",(lote_id,))
            total = cur.fetchone()[0]
            return total > 0 and ativos == 0
        except Exception:
            _log_war.debug('excecao tratada: %s', exc_info=True)
            return False


# ── CICLO DE VIDA: VENDA E ENCERRAMENTO ──────────────────────
def encerrar_lote(lote_id, data_encerramento=None, motivo="venda_total"):
    """Encerra lote: marca todos animais como VENDIDO e lote como encerrado."""
    from datetime import date
    p  = _ph()
    dt = str(data_encerramento or date.today())

    # Marcar todos os animais ativos como vendidos
    animais = listar_animais_por_lote(lote_id)
    for a in animais:
        if a and len(a) > 0:
            try:
                marcar_animal_vendido(a[0], data_venda=dt)
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE lotes SET status='encerrado', ativo=0, "
            f"data_venda={p} WHERE id={p}",
            (dt, lote_id)
        )
        conn.commit()
    invalidar_cache("listar_lotes")
    return True



def listar_animais_por_lote_status(lote_id, status=None):
    """Lista animais do lote filtrado por status (None=todos, VENDIDO, ATIVO)."""
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if status == 'VENDIDO':
            cur.execute(
                f"SELECT id,identificacao,raca,sexo,idade,peso_entrada,"
                f"peso_alvo,status,ativo FROM animais "
                f"WHERE lote_id={p} AND status='VENDIDO' ORDER BY identificacao",
                (lote_id,)
            )
        elif status == 'ATIVO':
            cur.execute(
                f"SELECT id,identificacao,raca,sexo,idade,peso_entrada,"
                f"peso_alvo,status,ativo FROM animais "
                f"WHERE lote_id={p} AND ativo=1 AND status!='VENDIDO' "
                f"ORDER BY identificacao",
                (lote_id,)
            )
        else:
            cur.execute(
                f"SELECT id,identificacao,raca,sexo,idade,peso_entrada,"
                f"peso_alvo,status,ativo FROM animais "
                f"WHERE lote_id={p} ORDER BY identificacao",
                (lote_id,)
            )
        return cur.fetchall()




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
# ── CICLO DE VIDA DO LOTE ─────────────────────────────────────────────────────

# ── IMPORTACAO CSV ─────────────────────────────────────────────────────────────


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

    # ── Fator 2: Ocorrencias dos ultimos 60 dias ─────────────────────────────
    ocs = listar_ocorrencias_todos_animais(lote_id)
    from datetime import date as _dt, timedelta as _td2
    limite_60 = str(_dt.today() - _td2(days=60))
    # o[2] = data_ocorrencia
    ocs_recentes = [o for o in ocs if o[2] and str(o[2]) >= limite_60]
    graves_at  = [o for o in ocs_recentes if o[5] == 'Alta' and o[8] == 'Em tratamento']
    graves_tot = [o for o in ocs_recentes if o[5] == 'Alta']
    medias_at  = [o for o in ocs_recentes if o[5] == 'Media' and o[8] == 'Em tratamento']
    medias_tot = [o for o in ocs_recentes if o[5] == 'Media']

    if len(graves_at) >= 3:
        score += 30
        fatores.append(f"{len(graves_at)} ocorrencias graves em tratamento")
        recomendacoes.append("Revisar protocolo sanitario urgente")
    elif len(graves_at) > 0:
        score += 20
        fatores.append(f"{len(graves_at)} ocorrencia(s) grave(s) ativa(s)")
        recomendacoes.append("Monitorar animais com ocorrencias graves")
    elif len(graves_tot) >= 2:
        score += 10
        fatores.append(f"{len(graves_tot)} ocorrencias graves nos ultimos 60 dias")

    if len(medias_at) >= 5:
        score += 12
        fatores.append(f"{len(medias_at)} ocorrencias medias em tratamento")
    elif len(medias_at) > 0:
        score += 6
        fatores.append(f"{len(medias_at)} ocorrencia(s) media(s) ativa(s)")
    elif len(medias_tot) >= 3:
        score += 4
        fatores.append(f"{len(medias_tot)} ocorrencias medias nos ultimos 60 dias")

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
                ocorrencias_graves=len(graves_tot), gmds=gmds)


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
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    return sorted(resultado, key=lambda x: x['risco_score'], reverse=True)


def _garantir_tabela_login_tentativas():
    """Cria tabela de tentativas de login se nao existir."""
    with _conexao() as conn:
        cur = conn.cursor()
        try:
            if _usar_postgres():
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS login_tentativas (
                        id SERIAL PRIMARY KEY,
                        email TEXT NOT NULL,
                        tentativa_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS login_tentativas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        tentativa_em DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)


def registrar_tentativa_login(email):
    """Registra uma tentativa falha de login."""
    _garantir_tabela_login_tentativas()
    with _conexao() as conn:
        cur = conn.cursor()
        p = _ph()
        try:
            cur.execute(
                f"INSERT INTO login_tentativas (email) VALUES ({p})",
                (email.lower().strip(),)
            )
            conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)


def verificar_bloqueio_login(email):
    """Verifica se email esta bloqueado (5+ tentativas nos ultimos 10 min).
    Retorna (bloqueado, tentativas, segundos_restantes)"""
    _garantir_tabela_login_tentativas()
    with _conexao() as conn:
        cur = conn.cursor()
        p = _ph()
        try:
            if _usar_postgres():
                cur.execute(
                    f"SELECT tentativa_em FROM login_tentativas "
                    f"WHERE email={p} "
                    f"AND tentativa_em > NOW() - INTERVAL '10 minutes' "
                    f"ORDER BY tentativa_em ASC",
                    (email.lower().strip(),)
                )
            else:
                cur.execute(
                    f"SELECT tentativa_em FROM login_tentativas "
                    f"WHERE email={p} "
                    f"AND tentativa_em > datetime('now','-10 minutes') "
                    f"ORDER BY tentativa_em ASC",
                    (email.lower().strip(),)
                )
            rows = cur.fetchall()
            n = len(rows)
            if n >= 5:
                # Calcular segundos restantes ate liberar
                from datetime import datetime as _dtm, timezone as _tz
                try:
                    primeira = rows[0][0]
                    if isinstance(primeira, str):
                        primeira = _dtm.fromisoformat(primeira.replace('Z',''))
                    if hasattr(primeira, 'tzinfo') and primeira.tzinfo:
                        agora = _dtm.now(_tz.utc)
                    else:
                        agora = _dtm.now()
                    seg_rest = max(0, 600 - int((agora - primeira).total_seconds()))
                except Exception:
                    seg_rest = 300
                return (True, n, seg_rest)
            return (False, n, 0)
        except Exception:
            _log_war.debug('excecao tratada: %s', exc_info=True)
            return (False, 0, 0)


def limpar_tentativas_login(email):
    """Limpa tentativas apos login bem sucedido."""
    _garantir_tabela_login_tentativas()
    with _conexao() as conn:
        cur = conn.cursor()
        p = _ph()
        try:
            cur.execute(
                f"DELETE FROM login_tentativas WHERE email={p}",
                (email.lower().strip(),)
            )
            conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)


def _garantir_status_animal_lote():
    """Garante coluna status em animais e lotes."""
    with _conexao() as conn:
        cur = conn.cursor()
        try:
            if _usar_postgres():
                cur.execute("ALTER TABLE animais ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ATIVO'")
                cur.execute("ALTER TABLE lotes ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Ativo'")
            else:
                for tbl, col in [('animais','status'),('lotes','status')]:
                    cur.execute(f"PRAGMA table_info({tbl})")
                    cols = [r[1] for r in cur.fetchall()]
                    if col not in cols:
                        cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} TEXT DEFAULT 'Ativo'")
            conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
# MODULO VETERINARIO - Funcoes CRUD
# ============================================================

def obter_crmv_usuario(user_id):
    """Retorna o CRMV do veterinario. Cria coluna se nao existir."""
    _garantir_coluna_crmv()
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT crmv FROM usuarios WHERE id={p}", (user_id,))
            r = cur.fetchone()
            return (r[0] or "") if r else ""
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return ""


def atualizar_crmv(user_id, crmv):
    """Atualiza o CRMV do veterinario. Garante coluna antes de atualizar."""
    _garantir_coluna_crmv()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE usuarios SET crmv={p} WHERE id={p}",
            (crmv, user_id)
        )
        conn.commit()
    invalidar_cache("listar_lotes")
    return True


# ── RECEITUARIO DIGITAL ───────────────────────────────────────
def adicionar_receita(vet_id, fazenda_owner_id, medicamento, dose, via, duracao,
                     animal_id=None, lote_id=None, carencia_dias=0,
                     observacoes="", crmv=""):
    """Emite receita e registra ocorrencia Medicacao no prontuario do(s) animal(is)."""
    _garantir_tabelas_vet()
    from datetime import date
    p  = _ph()
    dt = str(date.today())

    # 1. Inserir receita
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO receitas (vet_id,fazenda_owner_id,animal_id,lote_id,"
                f"data_emissao,medicamento,dose,via,duracao,carencia_dias,"
                f"observacoes,crmv_emissao) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (vet_id, fazenda_owner_id, animal_id, lote_id,
                 dt, medicamento, dose, via, duracao,
                 int(carencia_dias or 0), observacoes or "", crmv or "")
            )
            rid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO receitas (vet_id,fazenda_owner_id,animal_id,lote_id,"
                f"data_emissao,medicamento,dose,via,duracao,carencia_dias,"
                f"observacoes,crmv_emissao) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
                (vet_id, fazenda_owner_id, animal_id, lote_id,
                 dt, medicamento, dose, via, duracao,
                 int(carencia_dias or 0), observacoes or "", crmv or "")
            )
            rid = cur.lastrowid

    # 2. Montar descricao da ocorrencia
    desc = (
        f"Receituario #{rid} | {medicamento} | "
        f"Dose: {dose} | Via: {via} | Duracao: {duracao}"
    )
    if carencia_dias:
        desc += f" | Carencia: {carencia_dias} dias"
    if observacoes:
        desc += f" | Obs: {observacoes}"

    # 3. Registrar ocorrencia nos animais alvo
    alvos = []
    if animal_id:
        alvos = [animal_id]
    elif lote_id:
        alvos = [a[0] for a in listar_animais_por_lote(lote_id)]

    for aid in alvos:
        try:
            adicionar_ocorrencia(
                animal_id=aid,
                data=dt,
                tipo="Medicacao",
                descricao=desc,
                gravidade="Baixa",
                custo=0,
                dias_recuperacao=0,
                status="Resolvido"
            )
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    return rid


# ── EXAMES LABORATORIAIS ─────────────────────────────────────
def adicionar_exame(animal_id, vet_id, tipo_exame, data_coleta,
                   laboratorio="", resultado="", interpretacao="",
                   status="aguardando", alerta=0):
    """Registra exame laboratorial. Cria ocorrencia no prontuario."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    dt = str(date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO exames_laboratoriais "
                f"(animal_id,vet_id,data_coleta,tipo_exame,laboratorio,"
                f"resultado,interpretacao,status,alerta,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (animal_id, vet_id, str(data_coleta), tipo_exame,
                 laboratorio or "", resultado or "", interpretacao or "",
                 status, int(alerta), dt)
            )
            eid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO exames_laboratoriais "
                f"(animal_id,vet_id,data_coleta,tipo_exame,laboratorio,"
                f"resultado,interpretacao,status,alerta,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
                (animal_id, vet_id, str(data_coleta), tipo_exame,
                 laboratorio or "", resultado or "", interpretacao or "",
                 status, int(alerta), dt)
            )
            eid = cur.lastrowid

    # Registrar ocorrencia no prontuario
    tipo_oc = "Exame"
    desc_oc = f"Exame #{eid}: {tipo_exame}"
    if laboratorio:
        desc_oc += f" | Lab: {laboratorio}"
    if resultado and status == "concluido":
        desc_oc += f" | Resultado: {resultado[:100]}"
    if alerta:
        desc_oc += " | RESULTADO ALTERADO"
    try:
        adicionar_ocorrencia(
            animal_id=animal_id, data=str(data_coleta),
            tipo=tipo_oc, descricao=desc_oc,
            gravidade="Alta" if alerta else "Baixa",
            custo=0, dias_recuperacao=0, status="Resolvido"
        )
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    return eid


def atualizar_exame(exame_id, resultado, interpretacao="", status="concluido", alerta=0):
    """Atualiza resultado do exame e ajusta gravidade da ocorrencia."""
    _garantir_tabelas_vet()
    p = _ph()

    # Buscar dados do exame para atualizar ocorrencia
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT animal_id,tipo_exame,data_coleta,laboratorio "
            f"FROM exames_laboratoriais WHERE id={p}",
            (exame_id,)
        )
        row = cur.fetchone()

    # Atualizar registro do exame
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE exames_laboratoriais SET resultado={p},"
            f"interpretacao={p},status={p},alerta={p} WHERE id={p}",
            (resultado, interpretacao or "", status, int(alerta), exame_id)
        )
        conn.commit()

    # Atualizar gravidade da ocorrencia existente no prontuario
    if row:
        animal_id = row[0]
        tipo_exame = row[1]
        desc_check = f"Exame #{exame_id}:"
        nova_grav  = "Alta" if alerta else "Baixa"
        nova_desc  = f"Exame #{exame_id}: {tipo_exame}"
        if row[3]:  # laboratorio
            nova_desc += f" | Lab: {row[3]}"
        if resultado:
            nova_desc += f" | Resultado: {resultado[:100]}"
        if alerta:
            nova_desc += " | RESULTADO ALTERADO"
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE ocorrencias SET gravidade={p},descricao={p} "
                    f"WHERE animal_id={p} AND descricao LIKE {p}",
                    (nova_grav, nova_desc, animal_id, f"%{desc_check}%")
                )
                conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    return True


def listar_exames(animal_id=None, vet_id=None):
    """Lista exames por animal ou por vet."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if animal_id is not None:
            cur.execute(
                f"SELECT id,animal_id,vet_id,data_coleta,tipo_exame,"
                f"laboratorio,resultado,interpretacao,status,alerta "
                f"FROM exames_laboratoriais WHERE animal_id={p} "
                f"ORDER BY data_coleta DESC",
                (animal_id,)
            )
        elif vet_id is not None:
            cur.execute(
                f"SELECT id,animal_id,vet_id,data_coleta,tipo_exame,"
                f"laboratorio,resultado,interpretacao,status,alerta "
                f"FROM exames_laboratoriais WHERE vet_id={p} "
                f"ORDER BY data_coleta DESC",
                (vet_id,)
            )
        else:
            return []
        return cur.fetchall()


# ── MONITORAMENTO POS-TRATAMENTO ──────────────────────────────
def adicionar_monitoramento(animal_id, vet_id, descricao,
                            data_inicio, data_retorno, receita_id=None):
    """Cria monitoramento pos-tratamento com data de retorno."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO monitoramento_pos_tratamento "
                f"(animal_id,vet_id,receita_id,descricao,data_inicio,"
                f"data_retorno,status,evolucoes,alerta_enviado) "
                f"VALUES({p},{p},{p},{p},{p},{p},'ativo','[]',0) RETURNING id",
                (animal_id, vet_id, receita_id, descricao,
                 str(data_inicio), str(data_retorno))
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO monitoramento_pos_tratamento "
                f"(animal_id,vet_id,receita_id,descricao,data_inicio,"
                f"data_retorno,status,evolucoes,alerta_enviado) "
                f"VALUES({p},{p},{p},{p},{p},{p},'ativo','[]',0)",
                (animal_id, vet_id, receita_id, descricao,
                 str(data_inicio), str(data_retorno))
            )
            return cur.lastrowid


def registrar_evolucao(monitor_id, texto, data=None, quem="fazendeiro"):
    """Fazendeiro ou vet registra evolucao do animal monitorado."""
    _garantir_tabelas_vet()
    import json
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT evolucoes FROM monitoramento_pos_tratamento WHERE id={p}",
            (monitor_id,)
        )
        row = cur.fetchone()
        if not row:
            return False
        try:
            evols = json.loads(row[0] or "[]")
        except Exception:
            evols = []
        evols.append({
            "data": str(data or date.today()),
            "texto": texto,
            "quem": quem
        })
        cur.execute(
            f"UPDATE monitoramento_pos_tratamento SET evolucoes={p} WHERE id={p}",
            (json.dumps(evols, ensure_ascii=False), monitor_id)
        )
        conn.commit()
    return True


def encerrar_monitoramento(monitor_id):
    """Encerra o monitoramento."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE monitoramento_pos_tratamento SET status='encerrado' WHERE id={p}",
            (monitor_id,)
        )
        conn.commit()
    return True


def listar_monitoramentos(animal_id=None, vet_id=None,
                          owner_id=None, apenas_ativos=True):
    """Lista monitoramentos por animal, vet ou fazendeiro."""
    _garantir_tabelas_vet()
    import json
    from datetime import date
    p  = _ph()
    hoje = str(date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        # Prefixo m. em todas as referencias para evitar AmbiguousColumn no JOIN
        filtro_status = "AND m.status='ativo'" if apenas_ativos else ""
        if animal_id is not None:
            cur.execute(
                f"SELECT m.id,m.animal_id,m.vet_id,m.receita_id,m.descricao,"
                f"m.data_inicio,m.data_retorno,m.status,m.evolucoes "
                f"FROM monitoramento_pos_tratamento m "
                f"WHERE m.animal_id={p} {filtro_status} ORDER BY m.data_retorno",
                (animal_id,)
            )
        elif vet_id is not None:
            cur.execute(
                f"SELECT m.id,m.animal_id,m.vet_id,m.receita_id,m.descricao,"
                f"m.data_inicio,m.data_retorno,m.status,m.evolucoes "
                f"FROM monitoramento_pos_tratamento m "
                f"WHERE m.vet_id={p} {filtro_status} ORDER BY m.data_retorno",
                (vet_id,)
            )
        elif owner_id is not None:
            # Usar subquery para evitar AmbiguousColumn no JOIN
            _st_filter = "AND m.status='ativo'" if apenas_ativos else ""
            cur.execute(
                f"SELECT m.id,m.animal_id,m.vet_id,m.receita_id,m.descricao,"
                f"m.data_inicio,m.data_retorno,m.status,m.evolucoes,"
                f"a.identificacao "
                f"FROM monitoramento_pos_tratamento m "
                f"JOIN animais a ON a.id=m.animal_id "
                f"WHERE a.lote_id IN ("
                f"  SELECT id FROM lotes WHERE owner_id={p}"
                f") {_st_filter} ORDER BY m.data_retorno",
                (owner_id,)
            )
        else:
            return []
        rows = cur.fetchall()

    result = []
    for r in rows:
        evols = []
        try:
            evols = json.loads(r[8] or "[]")
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
        result.append({
            "id":           r[0],
            "animal_id":    r[1],
            "vet_id":       r[2],
            "receita_id":   r[3],
            "descricao":    r[4],
            "data_inicio":  r[5],
            "data_retorno": r[6],
            "status":       r[7],
            "evolucoes":    evols,
            "brinco":       r[9] if len(r) > 9 else None,
            "vencido":      str(r[6]) < hoje,
        })
    return result


def monitoramentos_vencendo(owner_id, dias=3):
    """Retorna monitoramentos vencidos OU com retorno em ate X dias."""
    _garantir_tabelas_vet()
    from datetime import date, timedelta
    hoje   = date.today()
    limite = str(hoje + timedelta(days=dias))
    todos  = listar_monitoramentos(owner_id=owner_id, apenas_ativos=True)
    # Inclui vencidos (data_retorno < hoje) E proximos (ate X dias)
    return [m for m in todos if str(m["data_retorno"]) <= limite]


# ── HONORARIOS VETERINARIOS ──────────────────────────────────
# ── MENSAGENS VET-FAZENDEIRO ─────────────────────────────────
def enviar_mensagem(remetente_id, destinatario_id, corpo,
                   assunto="", tipo="mensagem"):
    """Envia mensagem interna entre vet e fazendeiro."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO mensagens_vet "
                f"(remetente_id,destinatario_id,assunto,corpo,"
                f"lida,criado_em,tipo) "
                f"VALUES({p},{p},{p},{p},0,{p},{p}) RETURNING id",
                (remetente_id, destinatario_id, assunto or "",
                 corpo, str(date.today()), tipo)
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO mensagens_vet "
                f"(remetente_id,destinatario_id,assunto,corpo,"
                f"lida,criado_em,tipo) "
                f"VALUES({p},{p},{p},{p},0,{p},{p})",
                (remetente_id, destinatario_id, assunto or "",
                 corpo, str(date.today()), tipo)
            )
            return cur.lastrowid


def listar_mensagens(user_id, caixa="entrada"):
    """Lista mensagens do usuario. caixa='entrada' ou 'enviadas'."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if caixa == "entrada":
            cur.execute(
                f"SELECT id,remetente_id,destinatario_id,assunto,"
                f"corpo,lida,criado_em,tipo "
                f"FROM mensagens_vet WHERE destinatario_id={p} "
                f"ORDER BY criado_em DESC",
                (user_id,)
            )
        else:
            cur.execute(
                f"SELECT id,remetente_id,destinatario_id,assunto,"
                f"corpo,lida,criado_em,tipo "
                f"FROM mensagens_vet WHERE remetente_id={p} "
                f"ORDER BY criado_em DESC",
                (user_id,)
            )
        return cur.fetchall()


def marcar_mensagem_lida(mensagem_id):
    """Marca mensagem como lida."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE mensagens_vet SET lida=1 WHERE id={p}",
            (mensagem_id,)
        )
        conn.commit()


def contar_mensagens_nao_lidas(user_id):
    """Retorna numero de mensagens nao lidas."""
    _garantir_tabelas_vet()
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM mensagens_vet "
                f"WHERE destinatario_id={p} AND lida=0",
                (user_id,)
            )
            return cur.fetchone()[0]
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return 0


# ── CAMPANHAS DE VACINACAO ────────────────────────────────────
def criar_campanha(vet_id, nome, vacina, safra, data_inicio,
                  data_fim, meta_cobertura=100, observacoes=""):
    """Cria campanha de vacinacao."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO campanhas_vacinacao "
                f"(vet_id,nome,vacina,safra,data_inicio,data_fim,"
                f"meta_cobertura,status,observacoes,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},'ativa',{p},{p}) RETURNING id",
                (vet_id, nome, vacina, safra,
                 str(data_inicio), str(data_fim),
                 float(meta_cobertura), observacoes or "",
                 str(date.today()))
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO campanhas_vacinacao "
                f"(vet_id,nome,vacina,safra,data_inicio,data_fim,"
                f"meta_cobertura,status,observacoes,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},'ativa',{p},{p})",
                (vet_id, nome, vacina, safra,
                 str(data_inicio), str(data_fim),
                 float(meta_cobertura), observacoes or "",
                 str(date.today()))
            )
            return cur.lastrowid


def listar_campanhas(vet_id):
    """Lista campanhas do vet."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,vet_id,nome,vacina,safra,data_inicio,data_fim,"
            f"meta_cobertura,status,observacoes "
            f"FROM campanhas_vacinacao WHERE vet_id={p} "
            f"ORDER BY criado_em DESC",
            (vet_id,)
        )
        return cur.fetchall()


def adicionar_lote_campanha(campanha_id, lote_id, meta_animais):
    """Adiciona lote a campanha e agenda a vacina no calendario sanitario."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO campanha_lotes "
            f"(campanha_id,lote_id,meta_animais,vacinados,status) "
            f"VALUES({p},{p},{p},0,'pendente')",
            (campanha_id, lote_id, int(meta_animais))
        )
        conn.commit()

    # Buscar dados da campanha para agendar no calendario
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT vet_id,nome,vacina,data_inicio "
                f"FROM campanhas_vacinacao WHERE id={p}",
                (campanha_id,)
            )
            camp = cur.fetchone()
        if camp:
            vet_id, nome_camp, vacina, dt_ini = camp
            obs = f"Campanha: {nome_camp}"
            adicionar_vacina_agenda(
                lote_id=lote_id,
                nome_vacina=vacina,
                data_prevista=str(dt_ini),
                observacao=obs,
                agendado_por=vet_id
            )
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    return True


def listar_lotes_campanha(campanha_id):
    """Lista lotes de uma campanha com progresso."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT cl.id,cl.campanha_id,cl.lote_id,l.nome,"
            f"cl.meta_animais,cl.vacinados,cl.status,cl.data_execucao "
            f"FROM campanha_lotes cl "
            f"JOIN lotes l ON l.id=cl.lote_id "
            f"WHERE cl.campanha_id={p} ORDER BY l.nome",
            (campanha_id,)
        )
        return cur.fetchall()


def registrar_vacinacao_campanha(campanha_lote_id, vacinados, data_exec=None):
    """Registra execucao: atualiza campanha, insere no calendario
    e registra ocorrencia Vacinacao no prontuario dos animais."""
    _garantir_tabelas_vet()
    from datetime import date
    p  = _ph()
    dt = str(data_exec or date.today())

    # 1. Buscar dados do lote e campanha (sem try/except para ver erros)
    lote_id = None
    vacina  = None
    nome_camp = None
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT cl.lote_id, c.vacina, c.nome "
            f"FROM campanha_lotes cl "
            f"JOIN campanhas_vacinacao c ON c.id=cl.campanha_id "
            f"WHERE cl.id={p}",
            (campanha_lote_id,)
        )
        row = cur.fetchone()
        if row:
            lote_id, vacina, nome_camp = row[0], row[1], row[2]

    # 2. Atualizar campanha_lotes
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE campanha_lotes SET vacinados={p},"
            f"status='concluido',data_execucao={p} WHERE id={p}",
            (int(vacinados), dt, campanha_lote_id)
        )
        conn.commit()

    if not lote_id or not vacina:
        return True

    obs_oc = f"Vacinacao em campanha: {nome_camp} | {vacina}"

    # 3. Verificar se ja existe vacina pendente no calendario para este lote
    vac_pendente = None
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id FROM vacinas_agenda "
                f"WHERE lote_id={p} AND nome_vacina={p} "
                f"AND status='pendente' LIMIT 1",
                (lote_id, vacina)
            )
            vac_row = cur.fetchone()
            if vac_row:
                vac_pendente = vac_row[0]
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    if vac_pendente:
        # Confirmar vacina ja agendada
        try:
            registrar_vacina_realizada(
                vac_pendente, dt,
                obs_extra=f"Campanha: {nome_camp}"
            )
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    else:
        # Criar entrada ja como realizada no calendario
        try:
            vid = adicionar_vacina_agenda(
                lote_id=lote_id,
                nome_vacina=vacina,
                data_prevista=dt,
                observacao=f"Campanha: {nome_camp}"
            )
            if vid:
                # Marcar imediatamente como realizada
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"UPDATE vacinas_agenda SET "
                        f"data_realizada={p}, status='realizado' "
                        f"WHERE id={p}",
                        (dt, vid)
                    )
                    conn.commit()
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    animais = listar_animais_por_lote(lote_id)
    for an in animais:
        try:
            adicionar_ocorrencia(
                animal_id=an[0], data=dt,
                tipo="Vacinacao",
                descricao=obs_oc,
                gravidade="Baixa",
                custo=0, dias_recuperacao=0,
                status="Resolvido"
            )
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    return True


def sincronizar_campanha_executada(campanha_lote_id, data_exec=None):
    """Re-processa uma campanha ja executada para garantir
    que o calendario e prontuario estejam atualizados."""
    _garantir_tabelas_vet()
    from datetime import date
    p  = _ph()
    dt = str(data_exec or date.today())

    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT cl.lote_id, cl.vacinados, c.vacina, c.nome "
            f"FROM campanha_lotes cl "
            f"JOIN campanhas_vacinacao c ON c.id=cl.campanha_id "
            f"WHERE cl.id={p}",
            (campanha_lote_id,)
        )
        row = cur.fetchone()

    if not row:
        return 0

    lote_id, vacinados, vacina, nome_camp = row
    obs_oc = f"Vacinacao em campanha: {nome_camp} | {vacina}"

    # Calendário: criar entrada realizada se nao existir
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM vacinas_agenda "
                f"WHERE lote_id={p} AND nome_vacina={p}",
                (lote_id, vacina)
            )
            existe = cur.fetchone()[0]
        if not existe:
            vid = adicionar_vacina_agenda(
                lote_id=lote_id, nome_vacina=vacina,
                data_prevista=dt,
                observacao=f"Campanha: {nome_camp}"
            )
            if vid:
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"UPDATE vacinas_agenda SET "
                        f"data_realizada={p}, status='realizado' WHERE id={p}",
                        (dt, vid)
                    )
                    conn.commit()
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    animais = listar_animais_por_lote(lote_id)
    n_criadas = 0
    for an in animais:
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"SELECT COUNT(*) FROM ocorrencias "
                    f"WHERE animal_id={p} AND descricao LIKE {p}",
                    (an[0], f"%{nome_camp}%")
                )
                ja_existe = cur.fetchone()[0]
            if not ja_existe:
                adicionar_ocorrencia(
                    animal_id=an[0], data=dt,
                    tipo="Vacinacao", descricao=obs_oc,
                    gravidade="Baixa", custo=0,
                    dias_recuperacao=0, status="Resolvido"
                )
                n_criadas += 1
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    return n_criadas


def resumo_campanha(campanha_id):
    """Retorna progresso consolidado da campanha."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*),COALESCE(SUM(meta_animais),0),"
            f"COALESCE(SUM(vacinados),0),"
            f"COUNT(CASE WHEN status='concluido' THEN 1 END) "
            f"FROM campanha_lotes WHERE campanha_id={p}",
            (campanha_id,)
        )
        r = cur.fetchone()
        if not r or not r[0]:
            return {"n_lotes":0,"meta":0,"vacinados":0,"concluidos":0,"pct":0}
        n_lotes, meta, vac, conc = r[0], r[1], r[2], r[3]
        pct = round(100 * vac / max(1, meta), 1)
        return {
            "n_lotes": n_lotes, "meta": meta,
            "vacinados": vac, "concluidos": conc, "pct": pct
        }


# ── COORDENADAS DE FAZENDAS ───────────────────────────────────
def salvar_coords_fazenda(owner_id, latitude, longitude,
                          cidade="", estado=""):
    """Salva ou atualiza coordenadas da fazenda."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO fazendas_coords "
                f"(owner_id,latitude,longitude,cidade,estado) "
                f"VALUES({p},{p},{p},{p},{p}) "
                f"ON CONFLICT(owner_id) DO UPDATE SET "
                f"latitude={p},longitude={p},cidade={p},estado={p}",
                (owner_id, latitude, longitude, cidade or "", estado or "",
                 latitude, longitude, cidade or "", estado or "")
            )
        else:
            cur.execute(
                f"INSERT OR REPLACE INTO fazendas_coords "
                f"(owner_id,latitude,longitude,cidade,estado) "
                f"VALUES({p},{p},{p},{p},{p})",
                (owner_id, latitude, longitude, cidade or "", estado or "")
            )
        conn.commit()
    return True


def listar_coords_fazendas(owner_ids):
    """Retorna coords das fazendas pelos owner_ids."""
    _garantir_tabelas_vet()
    if not owner_ids:
        return []
    p  = _ph()
    ph = ",".join([p] * len(owner_ids))
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT owner_id,latitude,longitude,cidade,estado "
            f"FROM fazendas_coords WHERE owner_id IN ({ph})",
            tuple(owner_ids)
        )
        return cur.fetchall()


# ── DADOS EPIDEMIOLOGICOS ──────────────────────────────────────
def epidemiologia_por_fazenda(vet_id):
    """Retorna dados epidemiologicos consolidados por fazenda."""
    _garantir_tabelas_vet()
    from database import listar_fazendas_do_vet
    p    = _ph()
    foids = listar_fazendas_do_vet(vet_id)
    result = []
    for foid in foids:
        nome_faz = obter_nome_usuario(foid)
        with _conexao() as conn:
            cur = conn.cursor()
            # Ocorrencias por tipo
            try:
                cur.execute(
                    f"SELECT o.tipo, COUNT(*) "
                    f"FROM ocorrencias o "
                    f"JOIN animais a ON a.id=o.animal_id "
                    f"WHERE a.lote_id IN "
                    f"(SELECT id FROM lotes WHERE owner_id={p}) "
                    f"GROUP BY o.tipo ORDER BY COUNT(*) DESC LIMIT 5",
                    (foid,)
                )
                tipos = cur.fetchall()
            except Exception:
                tipos = []

            # Total animais e mortes
            try:
                cur.execute(
                    f"SELECT COUNT(*), "
                    f"COUNT(CASE WHEN a.status='MORTO' THEN 1 END) "
                    f"FROM animais a "
                    f"WHERE a.lote_id IN "
                    f"(SELECT id FROM lotes WHERE owner_id={p}) "
                    f"AND a.ativo=1",
                    (foid,)
                )
                r = cur.fetchone()
                n_ativos = r[0] or 0
                n_mortos = r[1] or 0
            except Exception:
                n_ativos = n_mortos = 0

        result.append({
            "owner_id":  foid,
            "nome":      nome_faz,
            "n_ativos":  n_ativos,
            "n_mortos":  n_mortos,
            "taxa_mort": round(100 * n_mortos / max(1, n_ativos+n_mortos), 2),
            "por_tipo":  tipos,
        })
    return result


# ── HISTORICO CLINICO PDF ──────────────────────────────────────
def historico_clinico_animal(animal_id):
    """Retorna historico completo do animal para PDF."""
    p = _ph()
    dados = {}

    # Dados basicos
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT a.identificacao,a.raca,a.sexo,a.idade,"
                f"a.peso_entrada,a.peso_alvo,l.nome "
                f"FROM animais a JOIN lotes l ON l.id=a.lote_id "
                f"WHERE a.id={p}",
                (animal_id,)
            )
            r = cur.fetchone()
            if r:
                dados["animal"] = {
                    "brinco": r[0], "raca": r[1], "sexo": r[2],
                    "idade": r[3], "peso_entrada": r[4],
                    "peso_alvo": r[5], "lote": r[6]
                }
    except Exception:
        dados["animal"] = {}

    # Pesagens
    dados["pesagens"] = listar_pesagens(animal_id) or []

    # Ocorrencias
    dados["ocorrencias"] = listar_ocorrencias(animal_id) or []

    # Exames
    try:
        dados["exames"] = listar_exames(animal_id=animal_id) or []
    except Exception:
        dados["exames"] = []

    # Carencia ativa
    try:
        dados["carencia"] = animal_em_carencia(animal_id) or []
    except Exception:
        dados["carencia"] = []

    return dados


# ── PLANOS E LIMITES ─────────────────────────────────────────
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


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD FINANCEIRO DO FAZENDEIRO
# ═══════════════════════════════════════════════════════════════════════════

def adicionar_custo_lote(lote_id, categoria, descricao, valor,
                         data_lancamento, observacoes=""):
    """Lança custo variável no lote (ração, medicamento, frete, etc)."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO custos_lote "
                f"(lote_id,categoria,descricao,valor,data_lancamento,observacoes)"
                f" VALUES({p},{p},{p},{p},{p},{p}) RETURNING id",
                (lote_id, categoria, descricao, float(valor),
                 str(data_lancamento or date.today()), observacoes or "")
            )
            rid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO custos_lote "
                f"(lote_id,categoria,descricao,valor,data_lancamento,observacoes)"
                f" VALUES({p},{p},{p},{p},{p},{p})",
                (lote_id, categoria, descricao, float(valor),
                 str(data_lancamento or date.today()), observacoes or "")
            )
            rid = cur.lastrowid
        conn.commit()
    _log_db.info("custo_lote inserido id=%s lote=%s valor=%s", rid, lote_id, valor)
    return rid


def listar_custos_lote(lote_id):
    """Lista todos os custos de um lote."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,lote_id,categoria,descricao,valor,"
            f"data_lancamento,observacoes "
            f"FROM custos_lote WHERE lote_id={p} ORDER BY data_lancamento DESC",
            (lote_id,)
        )
        return cur.fetchall()


@lambda _f: _cached(_f, ttl=120)
def margem_bruta_lote(lote_id):
    """Calcula margem bruta completa do lote.
    Retorna dict com todos os componentes financeiros."""
    from datetime import date
    p = _ph()

    # Dados básicos do lote
    lote = obter_lote(lote_id)
    if not lote:
        return {}

    nome_lote  = lote[1]
    qtd        = int(lote[5] or lote[4] or 0)  # qtd_recebida ou comprada
    preco_ua   = float(lote[9] or 0)            # preco_por_animal
    data_entr  = str(lote[3])[:10]
    data_vend  = str(lote[10])[:10] if len(lote) > 10 and lote[10] else None

    # Custo de compra
    custo_compra = preco_ua * qtd

    # Custos variáveis lançados
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COALESCE(SUM(valor),0),categoria "
                f"FROM custos_lote WHERE lote_id={p} "
                f"GROUP BY categoria",
                (lote_id,)
            )
            custos_var = {r[1]: float(r[0]) for r in cur.fetchall()}
    except Exception:
        custos_var = {}

    total_custos_var = sum(custos_var.values())

    # Receita de venda (se lote já foi vendido)
    receita_venda = 0.0
    preco_venda_kg = 0.0
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT preco_venda_kg,peso_total_kg FROM vendas_lote "
                f"WHERE lote_id={p} ORDER BY id DESC LIMIT 1",
                (lote_id,)
            )
            row = cur.fetchone()
            if row:
                preco_venda_kg = float(row[0])
                receita_venda  = preco_venda_kg * float(row[1])
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    receita_projetada = 0.0
    animais = listar_animais_por_lote(lote_id)
    n_ativos = len([a for a in animais if a])
    peso_medio_atual = 0.0
    peso_medio_alvo  = 0.0

    if animais:
        pesos_atuais = []
        pesos_alvo   = []
        for a in animais:
            pes = listar_pesagens(a[0])
            if pes:
                pesos_atuais.append(float(pes[-1][2]))
            peso_alvo_a = float(a[7] or 0) if len(a) > 7 else 0
            if peso_alvo_a:
                pesos_alvo.append(peso_alvo_a)

        if pesos_atuais:
            peso_medio_atual = sum(pesos_atuais) / len(pesos_atuais)
        if pesos_alvo:
            peso_medio_alvo = sum(pesos_alvo) / len(pesos_alvo)

        # Usar cotação CEPEA ou padrão R$15/kg
        try:
            cotacao = obter_cotacao_boi_gordo() or 15.0
        except Exception:
            cotacao = 15.0

        peso_ref = peso_medio_alvo if peso_medio_alvo > 0 else peso_medio_atual
        if peso_ref > 0 and cotacao > 0:
            # @ = arroba = 15kg
            receita_projetada = (peso_ref / 15) * cotacao * n_ativos

    # Cálculos finais
    custo_total = custo_compra + total_custos_var
    receita     = receita_venda if receita_venda > 0 else receita_projetada
    margem_r    = receita - custo_total
    margem_pct  = round(100 * margem_r / max(receita, 1), 1) if receita > 0 else 0

    # Dias no confinamento
    try:
        from datetime import datetime
        d_ini = datetime.strptime(data_entr, "%Y-%m-%d").date()
        d_ref = datetime.strptime(data_vend, "%Y-%m-%d").date()                 if data_vend else date.today()
        dias_conf = (d_ref - d_ini).days
    except Exception:
        dias_conf = 0

    return {
        "lote_id":          lote_id,
        "nome":             nome_lote,
        "n_animais":        n_ativos,
        "qtd_comprada":     qtd,
        "custo_compra":     custo_compra,
        "custo_compra_ua":  preco_ua,
        "custos_var":       custos_var,
        "total_custos_var": total_custos_var,
        "custo_total":      custo_total,
        "custo_ua":         custo_total / max(n_ativos, 1),
        "receita_venda":    receita_venda,
        "receita_projetada":receita_projetada,
        "receita":          receita,
        "vendido":          receita_venda > 0,
        "margem_r":         margem_r,
        "margem_pct":       margem_pct,
        "peso_medio_atual": round(peso_medio_atual, 1),
        "peso_medio_alvo":  round(peso_medio_alvo, 1),
        "dias_confinamento":dias_conf,
        "data_entrada":     data_entr,
        "data_venda":       data_vend,
    }


def dashboard_financeiro_fazendeiro(owner_id):
    """Consolida todos os indicadores financeiros do fazendeiro.
    Retorna dict com KPIs, lotes e alertas."""
    from datetime import date
    p = _ph()

    # Buscar lotes: tenta owner_id direto, depois busca por fazenda_id
    lotes = listar_lotes(owner_id=owner_id)

    if not lotes:
        # Fallback: buscar lotes onde fazenda_id aponta para uma fazenda do owner
        try:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"SELECT id,nome,descricao,data_entrada,qtd_comprada,"
                    f"qtd_recebida,transporte,tipo_alimentacao,tipo_dieta,"
                    f"COALESCE(preco_por_animal,0),COALESCE(data_venda,''),owner_id "
                    f"FROM lotes WHERE owner_id={p} OR id IN ("
                    f"  SELECT id FROM lotes WHERE owner_id IS NULL"
                    f") ORDER BY data_entrada DESC",
                    (owner_id,)
                )
                rows = cur.fetchall()
                lotes = [
                    (r[0],r[1],r[2],r[3],r[4],r[5],r[6],
                     r[7],r[8],float(r[9]),str(r[10]),r[11])
                    for r in rows if r[11] == owner_id or r[11] is None
                ]
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    if not lotes:
        return {"lotes": [], "kpis": {}, "alertas": [], "dre": {}}

    # Calcular margem de cada lote
    margens = []
    for l in lotes:
        try:
            m = margem_bruta_lote(l[0])
            if m:
                margens.append(m)
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)

    if not margens:
        return {"lotes": [], "kpis": {}, "alertas": [], "dre": {}}

    # KPIs consolidados
    total_investido  = sum(m["custo_total"] for m in margens)
    total_receita    = sum(m["receita"] for m in margens)
    total_margem     = sum(m["margem_r"] for m in margens)
    margem_media_pct = round(total_margem / max(total_receita, 1) * 100, 1)

    lotes_positivos  = [m for m in margens if m["margem_r"] >= 0]
    lotes_negativos  = [m for m in margens if m["margem_r"] < 0]
    total_animais    = sum(m["n_animais"] for m in margens)
    receita_proj     = sum(m["receita_projetada"] for m in margens
                          if not m["vendido"])
    vendidos         = [m for m in margens if m["vendido"]]
    receita_real     = sum(m["receita_venda"] for m in vendidos)

    kpis = {
        "total_lotes":       len(margens),
        "total_animais":     total_animais,
        "total_investido":   total_investido,
        "total_receita":     total_receita,
        "total_margem":      total_margem,
        "margem_pct":        margem_media_pct,
        "lotes_positivos":   len(lotes_positivos),
        "lotes_negativos":   len(lotes_negativos),
        "receita_realizada": receita_real,
        "receita_projetada": receita_proj,
        "lotes_vendidos":    len(vendidos),
    }

    # Alertas financeiros
    alertas = []
    for m in margens:
        if m["margem_pct"] < 0:
            alertas.append({
                "tipo": "perda",
                "lote": m["nome"],
                "msg":  f"Margem negativa: R$ {m['margem_r']:,.0f} "
                        f"({m['margem_pct']}%)",
                "prioridade": "alta",
            })
        elif m["margem_pct"] < 10:
            alertas.append({
                "tipo": "margem_baixa",
                "lote": m["nome"],
                "msg":  f"Margem baixa: {m['margem_pct']}% "
                        f"(R$ {m['margem_r']:,.0f})",
                "prioridade": "media",
            })
        if m["dias_confinamento"] > 180 and not m["vendido"]:
            alertas.append({
                "tipo": "prazo",
                "lote": m["nome"],
                "msg":  f"{m['dias_confinamento']} dias em confinamento "
                        f"sem venda — custos crescendo",
                "prioridade": "media",
            })

    # Ranking de lotes por margem
    ranking = sorted(margens, key=lambda x: x["margem_r"], reverse=True)

    # DRE simplificado
    dre = {
        "receita_bruta":    total_receita,
        "custo_compra":     sum(m["custo_compra"] for m in margens),
        "custos_var":       sum(m["total_custos_var"] for m in margens),
        "custo_total":      total_investido,
        "margem_bruta":     total_margem,
        "margem_bruta_pct": margem_media_pct,
    }

    return {
        "lotes":    margens,
        "kpis":     kpis,
        "alertas":  alertas,
        "ranking":  ranking,
        "dre":      dre,
    }


@lambda _f: _cached(_f, ttl=300)
def calendario_abate(owner_id):
    """Previsão de abate para todos os lotes ativos do fazendeiro."""
    from datetime import date, timedelta
    lotes = listar_lotes(owner_id=owner_id)
    resultado = []

    for l in lotes:
        lote_id = l[0]
        animais = listar_animais_por_lote(lote_id)
        if not animais:
            continue

        datas_prev   = []
        pesos_atuais = []

        for a in animais:
            peso_alvo = float(a[7] or 450) if len(a) > 7 else 450
            pes = listar_pesagens(a[0])
            if not pes:
                continue

            peso_ult = float(pes[-1][2])
            pesos_atuais.append(peso_ult)

            if len(pes) >= 2:
                gmd = _gmd_animal(pes)
                if gmd > 0:
                    kg_faltam = max(0, peso_alvo - peso_ult)
                    dias      = int(kg_faltam / gmd)
                    data_prev = date.today() + timedelta(days=dias)
                    datas_prev.append(data_prev)
            elif pes:
                pesos_atuais.append(peso_ult)

        if not datas_prev:
            continue

        data_media   = date.fromordinal(
            int(sum(d.toordinal() for d in datas_prev) / len(datas_prev))
        )
        peso_medio   = round(sum(pesos_atuais) / max(len(pesos_atuais), 1), 1)
        dias_restant = (data_media - date.today()).days

        try:
            cotacao = obter_cotacao_boi_gordo() or 15.0
        except Exception:
            cotacao = 15.0

        # Receita projetada no abate
        peso_alvo_medio = 450
        if animais:
            alvos = [float(a[7] or 450) for a in animais if len(a) > 7]
            if alvos:
                peso_alvo_medio = sum(alvos) / len(alvos)

        receita_proj = (peso_alvo_medio / 15) * cotacao * len(animais)

        resultado.append({
            "lote_id":       lote_id,
            "nome":          l[1],
            "n_animais":     len(animais),
            "peso_atual":    peso_medio,
            "peso_alvo":     round(peso_alvo_medio, 1),
            "data_abate":    str(data_media),
            "dias_restantes":dias_restant,
            "receita_proj":  receita_proj,
            "cotacao":       cotacao,
        })

    return sorted(resultado, key=lambda x: x["data_abate"])


# ── VENDAS DE LOTE ───────────────────────────────────────────




# ── DRE POR PERÍODO ───────────────────────────────────────────
def dre_por_periodo(owner_id, ano=None, mes=None):
    """DRE filtrado por período (ano e/ou mês).
    Retorna dict com receitas, custos e margem do período."""
    from datetime import date
    import calendar

    hoje  = date.today()
    _ano  = ano  or hoje.year
    _mes  = mes  # None = ano inteiro

    # Montar filtro de data
    if _mes:
        dt_ini = f"{_ano}-{_mes:02d}-01"
        ultimo_dia = calendar.monthrange(_ano, _mes)[1]
        dt_fim = f"{_ano}-{_mes:02d}-{ultimo_dia:02d}"
    else:
        dt_ini = f"{_ano}-01-01"
        dt_fim = f"{_ano}-12-31"

    p = _ph()

    # Receitas de venda no período
    receitas_venda = 0.0
    n_vendas = 0
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COALESCE(SUM(v.preco_venda_kg * v.peso_total_kg),0),"
                f"COUNT(*) "
                f"FROM vendas_lote v "
                f"JOIN lotes l ON l.id=v.lote_id "
                f"WHERE l.owner_id={p} "
                f"AND v.data_venda BETWEEN {p} AND {p}",
                (owner_id, dt_ini, dt_fim)
            )
            row = cur.fetchone()
            receitas_venda = float(row[0] or 0)
            n_vendas       = int(row[1] or 0)
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    custo_compra = 0.0
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COALESCE(SUM("
                f"COALESCE(preco_por_animal,0) * "
                f"COALESCE(qtd_recebida,qtd_comprada,0)"
                f"),0) "
                f"FROM lotes "
                f"WHERE owner_id={p} "
                f"AND data_entrada BETWEEN {p} AND {p}",
                (owner_id, dt_ini, dt_fim)
            )
            custo_compra = float(cur.fetchone()[0] or 0)
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    custos_var  = 0.0
    custos_cats = {}
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT cl.categoria, COALESCE(SUM(cl.valor),0) "
                f"FROM custos_lote cl "
                f"JOIN lotes l ON l.id=cl.lote_id "
                f"WHERE l.owner_id={p} "
                f"AND cl.data_lancamento BETWEEN {p} AND {p} "
                f"GROUP BY cl.categoria",
                (owner_id, dt_ini, dt_fim)
            )
            for row in cur.fetchall():
                custos_cats[row[0]] = float(row[1])
            custos_var = sum(custos_cats.values())
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    custo_total  = custo_compra + custos_var
    margem_bruta = receitas_venda - custo_total
    margem_pct   = round(100 * margem_bruta / max(receitas_venda, 1), 1)

    return {
        "periodo":       f"{_mes:02d}/{_ano}" if _mes else str(_ano),
        "dt_ini":        dt_ini,
        "dt_fim":        dt_fim,
        "receita_venda": receitas_venda,
        "n_vendas":      n_vendas,
        "custo_compra":  custo_compra,
        "custos_var":    custos_var,
        "custos_cats":   custos_cats,
        "custo_total":   custo_total,
        "margem_bruta":  margem_bruta,
        "margem_pct":    margem_pct,
    }


def curva_resultado_mensal(owner_id, ano=None):
    """Retorna resultado mensal para gráficos.
    Lista de 12 dicts com receita, custo e margem por mês."""
    from datetime import date
    _ano = ano or date.today().year
    meses = []
    acum  = 0.0

    for m in range(1, 13):
        dre = dre_por_periodo(owner_id, ano=_ano, mes=m)
        acum += dre["margem_bruta"]
        meses.append({
            "mes":         f"{m:02d}/{_ano}",
            "mes_num":     m,
            "receita":     dre["receita_venda"],
            "custo":       dre["custo_total"],
            "margem":      dre["margem_bruta"],
            "margem_acum": acum,
        })
    return meses


# ═══════════════════════════════════════════════════════════════════════════
# PAINEL ADMIN — MRR, USUARIOS, CHURN, ERROS
# ═══════════════════════════════════════════════════════════════════════════

def admin_metricas_usuarios():
    """Retorna metricas consolidadas de usuarios para o painel admin."""
    from datetime import date, timedelta
    hoje   = date.today()
    p30    = str(hoje - timedelta(days=30))
    p60    = str(hoje - timedelta(days=60))
    p7     = str(hoje - timedelta(days=7))

    p = _ph()
    resultado = {}

    with _conexao() as conn:
        cur = conn.cursor()

        # Total de usuarios por perfil
        cur.execute(
            "SELECT perfil, COUNT(*) FROM usuarios "
            "WHERE ativo=1 GROUP BY perfil"
        )
        por_perfil = {r[0]: r[1] for r in cur.fetchall()}
        resultado["total"]        = sum(por_perfil.values())
        resultado["fazendeiros"]  = por_perfil.get("fazendeiro", 0)
        resultado["vets"]         = por_perfil.get("veterinario", 0)
        resultado["admins"]       = por_perfil.get("admin", 0)

        # Ativos nos ultimos 30 dias (por last_login)
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM usuarios "
                f"WHERE ativo=1 AND last_login >= {p}",
                (p30,)
            )
            resultado["ativos_30d"] = cur.fetchone()[0]
        except Exception:
            resultado["ativos_30d"] = 0

        # Ativos nos ultimos 7 dias
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM usuarios "
                f"WHERE ativo=1 AND last_login >= {p}",
                (p7,)
            )
            resultado["ativos_7d"] = cur.fetchone()[0]
        except Exception:
            resultado["ativos_7d"] = 0

        # Novos nos ultimos 30 dias
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM usuarios "
                f"WHERE ativo=1 AND trial_inicio >= {p}",
                (p30,)
            )
            resultado["novos_30d"] = cur.fetchone()[0]
        except Exception:
            resultado["novos_30d"] = 0

        # Churn: usuarios que tinham last_login em p60 mas nao em p30
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM usuarios "
                f"WHERE ativo=1 "
                f"AND last_login >= {p} AND last_login < {p}",
                (p60, p30)
            )
            resultado["churn_30d"] = cur.fetchone()[0]
        except Exception:
            resultado["churn_30d"] = 0

        # Usuarios por plano
        try:
            cur.execute(
                "SELECT COALESCE(plano,'free'), COUNT(*) "
                "FROM usuarios WHERE ativo=1 GROUP BY COALESCE(plano,'free')"
            )
            resultado["por_plano"] = {r[0]: r[1] for r in cur.fetchall()}
        except Exception:
            resultado["por_plano"] = {}

    # Churn rate %
    base = max(resultado.get("ativos_30d", 0) +
               resultado.get("churn_30d", 0), 1)
    resultado["churn_rate"] = round(
        100 * resultado.get("churn_30d", 0) / base, 1
    )

    return resultado


def admin_calcular_mrr():
    """Calcula MRR automatico baseado nos planos dos usuarios
    e adiciona ajustes manuais do mes atual."""
    from datetime import date
    import calendar
    hoje   = date.today()
    mes_ref = f"{hoje.year}-{hoje.month:02d}"
    p      = _ph()

    precos_plano = {
        "free":       0,
        "pro":        99,
        "vet":        199,
        "enterprise": 0,  # sob consulta
    }

    # MRR automatico
    mrr_auto = 0.0
    por_plano = {}
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(plano,'free'), COUNT(*) "
                "FROM usuarios WHERE ativo=1 "
                "AND COALESCE(status_conta,'ativo')='ativo' "
                "GROUP BY COALESCE(plano,'free')"
            )
            for plano, qtd in cur.fetchall():
                preco  = precos_plano.get(plano, 0)
                total  = preco * qtd
                mrr_auto      += total
                por_plano[plano] = {"qtd": qtd, "preco": preco, "total": total}
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)
    mrr_ajuste = 0.0
    ajustes    = []
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id,mes_ref,valor,descricao,criado_em "
                f"FROM mrr_ajustes WHERE mes_ref={p} ORDER BY criado_em DESC",
                (mes_ref,)
            )
            for r in cur.fetchall():
                mrr_ajuste += float(r[2])
                ajustes.append({
                    "id":       r[0],
                    "mes_ref":  r[1],
                    "valor":    float(r[2]),
                    "descricao":r[3],
                })
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    mrr_total = mrr_auto + mrr_ajuste
    arr       = mrr_total * 12

    return {
        "mes_ref":    mes_ref,
        "mrr_auto":   mrr_auto,
        "mrr_ajuste": mrr_ajuste,
        "mrr_total":  mrr_total,
        "arr":        arr,
        "por_plano":  por_plano,
        "ajustes":    ajustes,
    }


def admin_adicionar_ajuste_mrr(mes_ref, valor, descricao=""):
    """Adiciona ajuste manual ao MRR do mes."""
    from datetime import datetime
    p = _ph()
    dt = datetime.utcnow().isoformat()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO mrr_ajustes (mes_ref,valor,descricao,criado_em) "
            f"VALUES({p},{p},{p},{p})",
            (mes_ref, float(valor), descricao or "", dt)
        )
        conn.commit()
    return True


def admin_listar_usuarios(perfil=None, plano=None, ativos_30d=False):
    """Lista usuarios com filtros para o painel admin."""
    from datetime import date, timedelta
    p   = _ph()
    p30 = str(date.today() - timedelta(days=30))

    with _conexao() as conn:
        cur = conn.cursor()
        sql = (
            "SELECT id,nome,email,perfil,"
            "COALESCE(plano,'free'),COALESCE(status_conta,'ativo'),"
            "COALESCE(last_login,'nunca'),COALESCE(trial_inicio,''),"
            "COALESCE(limite_animais,50) "
            "FROM usuarios WHERE ativo=1"
        )
        params = []
        if perfil:
            sql += f" AND perfil={p}"
            params.append(perfil)
        if plano:
            sql += f" AND COALESCE(plano,'free')={p}"
            params.append(plano)
        if ativos_30d:
            sql += f" AND last_login >= {p}"
            params.append(p30)
        sql += " ORDER BY COALESCE(last_login,'') DESC"
        cur.execute(sql, tuple(params))
        return cur.fetchall()


def admin_historico_acessos(user_id=None, dias=7):
    """Retorna historico de acessos recentes."""
    from datetime import date, timedelta
    p   = _ph()
    dt  = str(date.today() - timedelta(days=dias))
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            if user_id:
                cur.execute(
                    f"SELECT a.user_id, u.nome, a.rota, a.criado_em "
                    f"FROM access_log a JOIN usuarios u ON u.id=a.user_id "
                    f"WHERE a.user_id={p} AND a.criado_em >= {p} "
                    f"ORDER BY a.criado_em DESC LIMIT 100",
                    (user_id, dt)
                )
            else:
                cur.execute(
                    f"SELECT a.user_id, u.nome, a.rota, a.criado_em "
                    f"FROM access_log a JOIN usuarios u ON u.id=a.user_id "
                    f"WHERE a.criado_em >= {p} "
                    f"ORDER BY a.criado_em DESC LIMIT 200",
                    (dt,)
                )
            return cur.fetchall()
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return []


def admin_registrar_erro(mensagem, stack_trace="", user_id=None, rota=""):
    """Registra erro da aplicacao no banco."""
    from datetime import datetime
    p  = _ph()
    dt = datetime.utcnow().isoformat()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO error_log "
                f"(user_id,rota,mensagem,stack_trace,criado_em) "
                f"VALUES({p},{p},{p},{p},{p})",
                (user_id, rota or "", mensagem[:1000],
                 stack_trace[:3000] if stack_trace else "", dt)
            )
            conn.commit()
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)


def admin_listar_erros(dias=7, limit=50):
    """Lista erros recentes."""
    from datetime import date, timedelta
    p   = _ph()
    dt  = str(date.today() - timedelta(days=dias))
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT e.id, e.user_id, COALESCE(u.nome,'?'), "
                f"e.rota, e.mensagem, e.stack_trace, e.criado_em "
                f"FROM error_log e "
                f"LEFT JOIN usuarios u ON u.id=e.user_id "
                f"WHERE e.criado_em >= {p} "
                f"ORDER BY e.criado_em DESC LIMIT {limit}",
                (dt,)
            )
            return cur.fetchall()
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return []


def admin_erros_email_log(dias=30, limit=20):
    """Lista emails com erro nos ultimos N dias."""
    from datetime import date, timedelta
    p  = _ph()
    dt = str(date.today() - timedelta(days=dias))
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id,destinatario,assunto,status,erro,criado_em "
                f"FROM email_log WHERE status='erro' AND criado_em >= {p} "
                f"ORDER BY criado_em DESC LIMIT {limit}",
                (dt,)
            )
            return cur.fetchall()
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return []


@lambda _f: _cached(_f, ttl=300)
def admin_metricas_produto():
    """Metricas de uso do produto: animais, lotes, ocorrencias etc."""
    with _conexao() as conn:
        cur = conn.cursor()
        metricas = {}

        for tabela, alias in [
            ("animais",     "total_animais"),
            ("lotes",       "total_lotes"),
            ("ocorrencias", "total_ocorrencias"),
            ("receitas",    "total_receitas"),
            ("pesagens",    "total_pesagens"),
        ]:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tabela}")
                metricas[alias] = cur.fetchone()[0]
            except Exception:
                metricas[alias] = 0

        # PDFs gerados (email_log como proxy)
        try:
            cur.execute(
                "SELECT COUNT(*) FROM email_log WHERE status='enviado'"
            )
            metricas["emails_enviados"] = cur.fetchone()[0]
        except Exception:
            metricas["emails_enviados"] = 0

    return metricas


_MESES_ABR_DB = {
    1:"jan",2:"fev",3:"mar",4:"abr",5:"mai",6:"jun",
    7:"jul",8:"ago",9:"set",10:"out",11:"nov",12:"dez"
}

def _fmt_dt(d):
    """Formata data para exibição: 12 jan 2025"""
    try:
        if not d or str(d) in ("None","","nan"): return "—"
        s = str(d)[:10]
        ano,mes,dia = int(s[:4]),int(s[5:7]),int(s[8:10])
        return f"{dia:02d} {_MESES_ABR_DB[mes]} {ano}"
    except Exception:
        return str(d)[:10] if d else "—"


def _brl(v):
    """Formata valor em BRL: R$ 1.250,00"""
    try:
        v = float(v)
        neg = v < 0
        inteiro = int(abs(v))
        centavos = round((abs(v) - inteiro) * 100)
        s_int = f"{inteiro:,}".replace(",", ".")
        s = f"R$ {s_int},{centavos:02d}"
        return f"-{s}" if neg else s
    except Exception:
        return "R$ 0,00"


def buscar_usuario_por_email(email):
    """Busca usuario por email. Retorna dict ou None."""
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,nome,email,perfil,fazenda_id,"
            f"COALESCE(owner_id,id) as owner_id "
            f"FROM usuarios WHERE email={p}",
            (email,)
        )
        r = cur.fetchone()
    if not r:
        return None
    return dict(id=r[0], nome=r[1], email=r[2],
                perfil=r[3], fazenda_id=r[4], owner_id=r[5])


def obter_plano(user_id):
    """Retorna dados do plano do usuario."""
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return _PLANOS["free"].copy()
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT plano, plano_nome, plano_expira, "
                f"limite_animais, limite_fazendas, status_conta "
                f"FROM usuarios WHERE id={p}",
                (user_id,)
            )
            r = cur.fetchone()
        if not r:
            return _PLANOS["free"].copy()
        plano_key = (r[0] or "free").lower()
        dados = _PLANOS.get(plano_key, _PLANOS["free"]).copy()
        dados["plano_key"]    = plano_key
        dados["plano_expira"] = r[2]
        dados["status_conta"] = r[5] or "ativo"
        return dados
    except Exception as _e:
        _log_war.warning("obter_plano erro user_id=%s: %s", user_id, _e)
        return _PLANOS["free"].copy()


def atualizar_plano(user_id, plano_key, expira=None):
    """Atualiza plano do usuario."""
    info = _PLANOS.get(plano_key, _PLANOS["free"])
    p    = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE usuarios SET plano={p}, plano_nome={p}, "
            f"plano_expira={p}, limite_animais={p}, limite_fazendas={p} "
            f"WHERE id={p}",
            (plano_key, info["nome"], expira,
             info["limite_animais"], info["limite_fazendas"],
             user_id)
        )
        conn.commit()
    return True




def enviar_email(destinatario, assunto, corpo_html, corpo_txt=""):
    """Envia email via SMTP. Registra no email_log independente do resultado."""
    from datetime import datetime
    p  = _ph()
    dt = datetime.utcnow().isoformat()

    # Registrar tentativa
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            if _usar_postgres():
                cur.execute(
                    f"INSERT INTO email_log "
                    f"(destinatario,assunto,corpo,status,criado_em) "
                    f"VALUES({p},{p},{p},'pendente',{p}) RETURNING id",
                    (destinatario, assunto, corpo_txt or corpo_html, dt)
                )
                log_id = cur.fetchone()[0]
            else:
                cur.execute(
                    f"INSERT INTO email_log "
                    f"(destinatario,assunto,corpo,status,criado_em) "
                    f"VALUES({p},{p},{p},'pendente',{p})",
                    (destinatario, assunto, corpo_txt or corpo_html, dt)
                )
                log_id = cur.lastrowid
            conn.commit()
    except Exception:
        log_id = None

    # Tentar envio SMTP
    cfg = _smtp_config()
    if not cfg.get("user") or not cfg.get("password"):
        _log_db.warning("SMTP nao configurado — email nao enviado para %s",
                       destinatario)
        return False, "SMTP nao configurado"

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = cfg["from"]
        msg["To"]      = destinatario

        if corpo_txt:
            msg.attach(MIMEText(corpo_txt, "plain", "utf-8"))
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))

        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["from"], [destinatario], msg.as_string())

        # Marcar como enviado
        if log_id:
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE email_log SET status='enviado', "
                    f"enviado_em={p} WHERE id={p}",
                    (datetime.utcnow().isoformat(), log_id)
                )
                conn.commit()

        _log_db.info("Email enviado para %s | assunto: %s", destinatario, assunto)
        return True, "ok"

    except Exception as e:
        erro = str(e)
        _log_db.error("Falha ao enviar email para %s: %s", destinatario, erro)
        if log_id:
            try:
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"UPDATE email_log SET status='erro', erro={p} "
                        f"WHERE id={p}",
                        (erro[:500], log_id)
                    )
                    conn.commit()
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
        return False, erro


def enviar_email_boas_vindas(nome, email, plano="free"):
    """Email de boas-vindas ao novo usuario."""
    info  = _PLANOS.get(plano, _PLANOS["free"])
    html  = f"""
    <html><body style='font-family:sans-serif;max-width:600px;margin:auto'>
    <div style='background:#1B4332;padding:18px 28px;display:flex;
         align-items:center;gap:14px'>
        <svg width='34' height='34' viewBox='0 0 44 44' xmlns='http://www.w3.org/2000/svg'>
          <polygon points='22,3 39,13 39,31 22,41 5,31 5,13' fill='none' stroke='#F5F0E8' stroke-width='2'/>
          <text x='22' y='30' font-family='sans-serif' font-size='19'
                font-weight='300' fill='#F5F0E8' text-anchor='middle'>A</text>
          <line x1='13' y1='34' x2='31' y2='34' stroke='#40916C' stroke-width='1.8'/>
        </svg>
        <div>
          <div style='font-family:Georgia,serif;font-size:20px;font-weight:700;
               color:#F5F0E8;letter-spacing:2px'>Auroque</div>
          <div style='font-size:8px;color:#40916C;letter-spacing:4px;
               margin-top:2px'>GESTÃO PECUÁRIA INTELIGENTE</div>
        </div>
    </div>
    <div style='padding:30px;background:#f9f9f9'>
        <h2 style='color:#1B4332'>Bem-vindo(a), {nome}!</h2>
        <p>Sua conta foi criada com sucesso no plano <strong>{info['nome']}</strong>.</p>
        <p>Com o Auroque voce pode:</p>
        <ul>
            <li>Gerenciar animais, pesagens e lotes</li>
            <li>Acompanhar o calendario sanitario</li>
            <li>Gerar relatorios de desempenho</li>
            {'<li>Usar o modulo veterinario completo</li>' if info['modulo_vet'] else ''}
        </ul>
        <p>Seu limite atual: <strong>{info['limite_animais']} animais</strong> e
        <strong>{info['limite_fazendas']} fazenda(s)</strong>.</p>
        <div style='background:#1B4332;padding:15px;border-radius:8px;text-align:center;margin-top:20px'>
            <p style='color:white;margin:0'>Qualquer duvida, responda este email.</p>
        </div>
    </div>
    </body></html>
    """
    txt = f"Bem-vindo(a) ao Auroque, {nome}! Plano: {info['nome']}."
    return enviar_email(email, "Bem-vindo ao Auroque!", html, txt)


def enviar_email_alerta_diario(nome, email, alertas):
    """Email diario com resumo de alertas."""
    if not alertas:
        return False, "sem alertas"

    itens_html = "".join(
        f"<li style='margin:8px 0'>{a}</li>"
        for a in alertas
    )
    html = f"""
    <html><body style='font-family:sans-serif;max-width:600px;margin:auto'>
    <div style='background:#1B4332;padding:16px 28px;display:flex;
         align-items:center;gap:12px'>
        <svg width='28' height='28' viewBox='0 0 44 44' xmlns='http://www.w3.org/2000/svg'>
          <polygon points='22,3 39,13 39,31 22,41 5,31 5,13' fill='none' stroke='#F5F0E8' stroke-width='2'/>
          <text x='22' y='30' font-family='sans-serif' font-size='19'
                font-weight='300' fill='#F5F0E8' text-anchor='middle'>A</text>
          <line x1='13' y1='34' x2='31' y2='34' stroke='#40916C' stroke-width='1.8'/>
        </svg>
        <div style='font-family:Georgia,serif;font-size:18px;
             font-weight:700;color:#F5F0E8;letter-spacing:2px'>Auroque</div>
    </div>
    <div style='padding:30px'>
        <h2 style='color:#1B4332'>Ola, {nome}!</h2>
        <p>Resumo de alertas do dia:</p>
        <ul style='background:#f5f0e8;padding:20px;border-radius:8px'>
            {itens_html}
        </ul>
        <p style='color:#888;font-size:12px'>
            Voce recebe este email porque tem alertas ativos no Auroque.
        </p>
    </div>
    </body></html>
    """
    txt = f"Auroque Alertas - {nome}:\n" + "\n".join(f"- {a}" for a in alertas)
    return enviar_email(
        email, f"Auroque — {len(alertas)} alerta(s) hoje", html, txt
    )


# ── ONBOARDING ────────────────────────────────────────────────
_PASSOS_ONBOARDING = [
    ("perfil",     "Complete seu perfil"),
    ("lote",       "Crie seu primeiro lote"),
    ("animais",    "Cadastre seus animais"),
    ("calendario", "Configure o calendario sanitario"),
    ("alertas",    "Configure seus alertas"),
]


def obter_progresso_onboarding(user_id):
    """Retorna dict {passo: completo} para o usuario."""
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            p = _ph()
            cur.execute(
                f"SELECT passo, completo FROM onboarding_log "
                f"WHERE user_id={p}",
                (user_id,)
            )
            rows = {r[0]: bool(r[1]) for r in cur.fetchall()}
        return {passo: rows.get(passo, False)
                for passo, _ in _PASSOS_ONBOARDING}
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return {passo: False for passo, _ in _PASSOS_ONBOARDING}


def marcar_passo_onboarding(user_id, passo):
    """Marca passo do onboarding como completo."""
    from datetime import date
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            if _usar_postgres():
                cur.execute(
                    f"INSERT INTO onboarding_log "
                    f"(user_id,passo,completo,criado_em) "
                    f"VALUES({p},{p},1,{p}) "
                    f"ON CONFLICT(user_id,passo) DO UPDATE SET completo=1",
                    (user_id, passo, str(date.today()))
                )
            else:
                cur.execute(
                    f"INSERT OR REPLACE INTO onboarding_log "
                    f"(user_id,passo,completo,criado_em) "
                    f"VALUES({p},{p},1,{p})",
                    (user_id, passo, str(date.today()))
                )
            conn.commit()
        # Verificar se todos os passos foram concluidos
        prog = obter_progresso_onboarding(user_id)
        if all(prog.values()):
            with _conexao() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE usuarios SET onboarding_completo=1 WHERE id={p}",
                    (user_id,)
                )
                conn.commit()
        return True
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return False


def onboarding_completo(user_id):
    """Verifica se o usuario completou o onboarding."""
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT onboarding_completo FROM usuarios WHERE id={p}",
                (user_id,)
            )
            r = cur.fetchone()
        return bool(r and r[0])
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return True  # Em caso de erro, nao bloquear



def criar_dados_demo(owner_id):
    """Cria fazenda demo com dados fictícios para novo usuário.
    Chamada automaticamente no primeiro login.
    """
    from datetime import date, timedelta
    import random
    p = _ph()
    _log_db.info("Criando dados demo para owner_id=%s", owner_id)
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            # Verificar se já tem lote (não criar duplicado)
            cur.execute(
                f"SELECT COUNT(*) FROM lotes WHERE owner_id={p}", (owner_id,)
            )
            r = cur.fetchone()
            if r and r[0] > 0:
                return True  # já tem dados

            # Lote demo
            dt_entrada = str(date.today() - timedelta(days=90))
            if _usar_postgres():
                cur.execute(
                    f"INSERT INTO lotes (nome,descricao,data_entrada,"
                    f"qtd_comprada,qtd_recebida,preco_por_animal,owner_id,status)"
                    f" VALUES ({p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                    ("Lote Demo — Nelore 2025",
                     "Lote criado automaticamente para demonstração",
                     dt_entrada, 8, 8, 2800.00, owner_id, "ATIVO")
                )
                lote_id = cur.fetchone()[0]
            else:
                cur.execute(
                    f"INSERT INTO lotes (nome,descricao,data_entrada,"
                    f"qtd_comprada,qtd_recebida,preco_por_animal,owner_id,status)"
                    f" VALUES ({p},{p},{p},{p},{p},{p},{p},{p})",
                    ("Lote Demo — Nelore 2025",
                     "Lote criado automaticamente para demonstração",
                     dt_entrada, 8, 8, 2800.00, owner_id, "ATIVO")
                )
                lote_id = cur.lastrowid
            conn.commit()

            # 8 animais demo
            animais = [
                ("DEMO-01","Nelore","M",24,320),("DEMO-02","Nelore","M",22,305),
                ("DEMO-03","Nelore","M",24,332),("DEMO-04","Angus","M",20,348),
                ("DEMO-05","Angus","M",21,338),("DEMO-06","Nelore","F",18,280),
                ("DEMO-07","Nelore","F",20,295),("DEMO-08","Angus","M",23,355),
            ]
            animal_ids = []
            for ident, raca, sexo, idade, peso in animais:
                if _usar_postgres():
                    cur.execute(
                        f"INSERT INTO animais (identificacao,raca,sexo,"
                        f"idade_meses,peso_entrada,lote_id,ativo,status)"
                        f" VALUES ({p},{p},{p},{p},{p},{p},1,'ATIVO') RETURNING id",
                        (ident, raca, sexo, idade, peso, lote_id)
                    )
                    animal_ids.append(cur.fetchone()[0])
                else:
                    cur.execute(
                        f"INSERT INTO animais (identificacao,raca,sexo,"
                        f"idade_meses,peso_entrada,lote_id,ativo,status)"
                        f" VALUES ({p},{p},{p},{p},{p},{p},1,'ATIVO')",
                        (ident, raca, sexo, idade, peso, lote_id)
                    )
                    animal_ids.append(cur.lastrowid)
            conn.commit()

            # Pesagens ao longo de 90 dias
            pesos_base = [320,305,332,348,338,280,295,355]
            for i, aid in enumerate(animal_ids):
                peso = pesos_base[i]
                for dias_atras in [90, 60, 30, 0]:
                    peso += random.randint(18, 32)
                    dt = str(date.today() - timedelta(days=dias_atras))
                    cur.execute(
                        f"INSERT INTO pesagens (animal_id,peso,data)"
                        f" VALUES ({p},{p},{p})",
                        (aid, round(peso, 1), dt)
                    )
            conn.commit()

            # Custos demo
            for cat, desc, val, dias in [
                ("racao","Ração concentrada — 3 meses",4200.00,80),
                ("medicamento","Vermifugação e vacinas",480.00,75),
                ("mao_de_obra","Mão de obra — 3 meses",1800.00,70),
                ("veterinario","Visita técnica",350.00,45),
            ]:
                dt = str(date.today() - timedelta(days=dias))
                cur.execute(
                    f"INSERT INTO custos_lote"
                    f" (lote_id,categoria,descricao,valor,data_lancamento,owner_id)"
                    f" VALUES ({p},{p},{p},{p},{p},{p})",
                    (lote_id, cat, desc, val, dt, owner_id)
                )
            conn.commit()

        # Marcar demo como criado
        marcar_onboarding_completo(owner_id)
        _log_db.info("Dados demo criados: lote_id=%s, %d animais",
                     lote_id, len(animal_ids))
        return True
    except Exception as _e:
        _log_err.error("criar_dados_demo: %s", _e)
        return False


def is_primeiro_login(user_id):
    """Verifica se é o primeiro login do usuário (sem lotes cadastrados)."""
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM lotes WHERE owner_id={p}",
                (user_id,)
            )
            r = cur.fetchone()
            return (r[0] if r else 0) == 0
    except Exception:
        return False


# ── IMPORTACAO CSV ────────────────────────────────────────────


def lancar_honorario(vet_id, fazenda_owner_id, descricao, valor,
                     tipo="consulta", visita_id=None,
                     itens=None, observacoes=""):
    """Lanca honorario do vet. itens = lista de dicts com
    {descricao, quantidade, valor_unitario}."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    dt = str(date.today())

    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO honorarios_vet "
                f"(vet_id,fazenda_owner_id,visita_id,data_lancamento,"
                f"descricao,tipo,valor,status,observacoes) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},'pendente',{p}) RETURNING id",
                (vet_id, fazenda_owner_id, visita_id, dt,
                 descricao, tipo, float(valor), observacoes or "")
            )
            hid = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO honorarios_vet "
                f"(vet_id,fazenda_owner_id,visita_id,data_lancamento,"
                f"descricao,tipo,valor,status,observacoes) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},'pendente',{p})",
                (vet_id, fazenda_owner_id, visita_id, dt,
                 descricao, tipo, float(valor), observacoes or "")
            )
            hid = cur.lastrowid

    # Inserir itens se fornecidos
    if itens:
        for item in itens:
            qtd   = float(item.get("quantidade", 1))
            v_un  = float(item.get("valor_unitario", 0))
            v_tot = round(qtd * v_un, 2)
            try:
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"INSERT INTO honorarios_itens "
                        f"(honorario_id,descricao,quantidade,"
                        f"valor_unitario,valor_total) "
                        f"VALUES({p},{p},{p},{p},{p})",
                        (hid, item.get("descricao",""),
                         qtd, v_un, v_tot)
                    )
                    conn.commit()
            except Exception as _ew:
                _log_err.error("erro em lancar_honorario: %s", _ew)
    return hid


def listar_honorarios(vet_id, fazenda_owner_id=None, status=None):
    """Lista honorarios do vet, opcionalmente por fazenda e status."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        sql = (
            f"SELECT id,vet_id,fazenda_owner_id,visita_id,"
            f"data_lancamento,descricao,tipo,valor,status,"
            f"data_pagamento,forma_pagamento,observacoes "
            f"FROM honorarios_vet WHERE vet_id={p}"
        )
        params = [vet_id]
        if fazenda_owner_id is not None:
            sql += f" AND fazenda_owner_id={p}"
            params.append(fazenda_owner_id)
        if status:
            sql += f" AND status={p}"
            params.append(status)
        sql += " ORDER BY data_lancamento DESC"
        cur.execute(sql, tuple(params))
        return cur.fetchall()


def listar_itens_honorario(honorario_id):
    """Lista itens de um honorario."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,honorario_id,descricao,quantidade,"
            f"valor_unitario,valor_total "
            f"FROM honorarios_itens WHERE honorario_id={p}",
            (honorario_id,)
        )
        return cur.fetchall()


def registrar_pagamento_honorario(honorario_id, forma_pagamento,
                                  data_pagamento=None):
    """Marca honorario como pago."""
    _garantir_tabelas_vet()
    from datetime import date
    p  = _ph()
    dt = str(data_pagamento or date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE honorarios_vet SET status='pago',"
            f"data_pagamento={p},forma_pagamento={p} WHERE id={p}",
            (dt, forma_pagamento, honorario_id)
        )
        conn.commit()
    return True


def cancelar_honorario(honorario_id):
    """Cancela um honorario pendente."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE honorarios_vet SET status='cancelado' WHERE id={p}",
            (honorario_id,)
        )
        conn.commit()
    return True


def resumo_financeiro_vet(vet_id, mes=None, ano=None):
    """Retorna resumo financeiro do vet por periodo."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    hoje = date.today()
    _mes = mes or hoje.month
    _ano = ano or hoje.year
    prefixo = f"{_ano}-{_mes:02d}"

    with _conexao() as conn:
        cur = conn.cursor()

        # Total por status
        try:
            cur.execute(
                f"SELECT status, COUNT(*), COALESCE(SUM(valor),0) "
                f"FROM honorarios_vet WHERE vet_id={p} "
                f"AND data_lancamento LIKE {p} "
                f"GROUP BY status",
                (vet_id, f"{prefixo}%")
            )
            por_status = {r[0]: {"count": r[1], "valor": float(r[2])}
                         for r in cur.fetchall()}
        except Exception:
            por_status = {}

        # Total por fazenda no mes
        try:
            cur.execute(
                f"SELECT fazenda_owner_id, COUNT(*), COALESCE(SUM(valor),0) "
                f"FROM honorarios_vet WHERE vet_id={p} "
                f"AND data_lancamento LIKE {p} "
                f"GROUP BY fazenda_owner_id ORDER BY SUM(valor) DESC",
                (vet_id, f"{prefixo}%")
            )
            por_fazenda = cur.fetchall()
        except Exception:
            por_fazenda = []

        # Ultimos 12 meses (faturamento mensal)
        try:
            if _usar_postgres():
                cur.execute(
                    f"SELECT TO_CHAR(data_lancamento::date, 'YYYY-MM') as mes,"
                    f"COALESCE(SUM(valor),0) "
                    f"FROM honorarios_vet WHERE vet_id={p} AND status!='cancelado'"
                    f"GROUP BY mes ORDER BY mes DESC LIMIT 12",
                    (vet_id,)
                )
            else:
                cur.execute(
                    f"SELECT strftime('%Y-%m',data_lancamento) as mes,"
                    f"COALESCE(SUM(valor),0) "
                    f"FROM honorarios_vet WHERE vet_id={p} AND status!='cancelado'"
                    f"GROUP BY mes ORDER BY mes DESC LIMIT 12",
                    (vet_id,)
                )
            mensal = cur.fetchall()
        except Exception:
            mensal = []

    pend  = por_status.get("pendente", {})
    pago  = por_status.get("pago",     {})
    canc  = por_status.get("cancelado",{})

    return {
        "mes":         f"{_mes:02d}/{_ano}",
        "pendente":    pend.get("valor", 0),
        "pago":        pago.get("valor", 0),
        "cancelado":   canc.get("valor", 0),
        "n_pendente":  pend.get("count", 0),
        "n_pago":      pago.get("count", 0),
        "por_fazenda": por_fazenda,
        "mensal":      mensal,
    }


def sincronizar_ocorrencias_receitas():
    """Cria ocorrencias para receitas antigas que nao as geraram.
    Chamada uma vez para sincronizar o historico."""
    p  = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id,vet_id,animal_id,lote_id,data_emissao,"
                "medicamento,dose,via,duracao,carencia_dias,observacoes "
                "FROM receitas ORDER BY id"
            )
            receitas = cur.fetchall()
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return 0

    ok = 0
    for r in receitas:
        rid, vet_id, animal_id, lote_id, dt, med, dose, via, dur, carc, obs = r
        # Verificar se ja existe ocorrencia com essa receita
        desc_check = f"Receituario #{rid}"
        alvos = []
        if animal_id:
            alvos = [animal_id]
        elif lote_id:
            alvos = [a[0] for a in listar_animais_por_lote(lote_id)]

        for aid in alvos:
            try:
                with _conexao() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"SELECT id FROM ocorrencias "
                        f"WHERE animal_id={p} AND descricao LIKE {p}",
                        (aid, f"%{desc_check}%")
                    )
                    if cur.fetchone():
                        continue  # Ja existe
                # Criar ocorrencia
                desc = (
                    f"Receituario #{rid} | {med} | "
                    f"Dose: {dose} | Via: {via} | Duracao: {dur}"
                )
                if carc:
                    desc += f" | Carencia: {carc} dias"
                adicionar_ocorrencia(
                    animal_id=aid, data=str(dt),
                    tipo="Medicacao", descricao=desc,
                    gravidade="Baixa", custo=0,
                    dias_recuperacao=0, status="Resolvido"
                )
                ok += 1
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
    return ok


def listar_receitas(vet_id=None, fazenda_owner_id=None):
    """Lista receitas. Vet ve as proprias, fazendeiro ve as recebidas."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if vet_id is not None:
            cur.execute(
                f"SELECT id,vet_id,fazenda_owner_id,animal_id,lote_id,"
                f"data_emissao,medicamento,dose,via,duracao,carencia_dias,"
                f"observacoes,crmv_emissao FROM receitas "
                f"WHERE vet_id={p} ORDER BY data_emissao DESC",
                (vet_id,)
            )
        elif fazenda_owner_id is not None:
            cur.execute(
                f"SELECT id,vet_id,fazenda_owner_id,animal_id,lote_id,"
                f"data_emissao,medicamento,dose,via,duracao,carencia_dias,"
                f"observacoes,crmv_emissao FROM receitas "
                f"WHERE fazenda_owner_id={p} ORDER BY data_emissao DESC",
                (fazenda_owner_id,)
            )
        else:
            return []
        return cur.fetchall()


# ── PROTOCOLOS SANITARIOS ─────────────────────────────────────
def adicionar_protocolo(vet_id, nome, descricao="", categoria="geral"):
    """Cria novo protocolo sanitario."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO protocolos_sanitarios (vet_id,nome,descricao,categoria,criado_em) "
                f"VALUES({p},{p},{p},{p},{p}) RETURNING id",
                (vet_id, nome, descricao or "", categoria, str(date.today()))
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO protocolos_sanitarios (vet_id,nome,descricao,categoria,criado_em) "
                f"VALUES({p},{p},{p},{p},{p})",
                (vet_id, nome, descricao or "", categoria, str(date.today()))
            )
            return cur.lastrowid


def listar_protocolos(vet_id):
    """Lista protocolos do veterinario."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,vet_id,nome,descricao,categoria,criado_em "
            f"FROM protocolos_sanitarios WHERE vet_id={p} ORDER BY nome",
            (vet_id,)
        )
        return cur.fetchall()


def adicionar_item_protocolo(protocolo_id, ordem, tipo, nome, dia_offset, observacao=""):
    """Adiciona item (vacina/medicacao) ao protocolo."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO protocolo_itens (protocolo_id,ordem,tipo,nome,dia_offset,observacao) "
            f"VALUES({p},{p},{p},{p},{p},{p})",
            (protocolo_id, int(ordem), tipo, nome, int(dia_offset), observacao or "")
        )
        conn.commit()
        return True


def listar_itens_protocolo(protocolo_id):
    """Lista itens de um protocolo na ordem correta."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,protocolo_id,ordem,tipo,nome,dia_offset,observacao "
            f"FROM protocolo_itens WHERE protocolo_id={p} ORDER BY dia_offset",
            (protocolo_id,)
        )
        return cur.fetchall()


def aplicar_protocolo_no_lote(protocolo_id, lote_id, data_inicio, vet_id):
    """Aplica um protocolo ao lote criando vacinas agendadas."""
    _garantir_tabelas_vet()
    from datetime import datetime, timedelta
    try:
        dt_inicio = datetime.strptime(str(data_inicio)[:10], "%Y-%m-%d").date()
    except Exception:
        from datetime import date
        dt_inicio = date.today()

    itens = listar_itens_protocolo(protocolo_id)
    n_criados = 0
    for item in itens:
        _, _, ordem, tipo, nome_item, dia_offset, obs_item = item
        data_prev = dt_inicio + timedelta(days=int(dia_offset))
        try:
            adicionar_vacina_agenda(
                lote_id=lote_id,
                nome_vacina=nome_item,
                data_prevista=str(data_prev),
                observacao=f"Protocolo: {obs_item or 'sem obs'}",
                agendado_por=vet_id
            )
            n_criados += 1
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
    return n_criados


# ── VISITAS TECNICAS ──────────────────────────────────────────
def adicionar_visita(vet_id, fazenda_owner_id, data_visita, objetivo,
                    duracao_min=60, observacoes=""):
    """Agenda nova visita tecnica."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO visitas_tecnicas (vet_id,fazenda_owner_id,data_visita,"
                f"objetivo,duracao_min,status,observacoes,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},'agendada',{p},{p}) RETURNING id",
                (vet_id, fazenda_owner_id, str(data_visita), objetivo,
                 int(duracao_min or 60), observacoes or "", str(date.today()))
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO visitas_tecnicas (vet_id,fazenda_owner_id,data_visita,"
                f"objetivo,duracao_min,status,observacoes,criado_em) "
                f"VALUES({p},{p},{p},{p},{p},'agendada',{p},{p})",
                (vet_id, fazenda_owner_id, str(data_visita), objetivo,
                 int(duracao_min or 60), observacoes or "", str(date.today()))
            )
            return cur.lastrowid


def listar_visitas(vet_id=None, fazenda_owner_id=None):
    """Lista visitas - vet ve as proprias, fazendeiro ve as recebidas."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if vet_id is not None:
            cur.execute(
                f"SELECT id,vet_id,fazenda_owner_id,data_visita,objetivo,"
                f"duracao_min,status,observacoes FROM visitas_tecnicas "
                f"WHERE vet_id={p} ORDER BY data_visita DESC",
                (vet_id,)
            )
        elif fazenda_owner_id is not None:
            cur.execute(
                f"SELECT id,vet_id,fazenda_owner_id,data_visita,objetivo,"
                f"duracao_min,status,observacoes FROM visitas_tecnicas "
                f"WHERE fazenda_owner_id={p} ORDER BY data_visita DESC",
                (fazenda_owner_id,)
            )
        else:
            return []
        return cur.fetchall()


def atualizar_status_visita(visita_id, status):
    """Atualiza status da visita (agendada/realizada/cancelada)."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE visitas_tecnicas SET status={p} WHERE id={p}",
            (status, visita_id)
        )
        conn.commit()
        return True


# ── RELATORIOS DE VISITA ──────────────────────────────────────
def adicionar_relatorio_visita(vet_id, fazenda_owner_id, achados, tratamentos,
                              recomendacoes, animais_inspecionados=0,
                              visita_id=None, proxima_visita=None, crmv=""):
    """Cria relatorio tecnico da visita."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if _usar_postgres():
            cur.execute(
                f"INSERT INTO relatorios_visita (visita_id,vet_id,fazenda_owner_id,"
                f"data_relatorio,animais_inspecionados,achados,tratamentos,"
                f"recomendacoes,proxima_visita,crmv_emissao) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                (visita_id, vet_id, fazenda_owner_id, str(date.today()),
                 int(animais_inspecionados or 0), achados, tratamentos,
                 recomendacoes, str(proxima_visita) if proxima_visita else None,
                 crmv or "")
            )
            return cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO relatorios_visita (visita_id,vet_id,fazenda_owner_id,"
                f"data_relatorio,animais_inspecionados,achados,tratamentos,"
                f"recomendacoes,proxima_visita,crmv_emissao) "
                f"VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
                (visita_id, vet_id, fazenda_owner_id, str(date.today()),
                 int(animais_inspecionados or 0), achados, tratamentos,
                 recomendacoes, str(proxima_visita) if proxima_visita else None,
                 crmv or "")
            )
            return cur.lastrowid


def listar_relatorios(vet_id=None, fazenda_owner_id=None):
    """Lista relatorios de visita."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        if vet_id is not None:
            cur.execute(
                f"SELECT id,visita_id,vet_id,fazenda_owner_id,data_relatorio,"
                f"animais_inspecionados,achados,tratamentos,recomendacoes,"
                f"proxima_visita,crmv_emissao FROM relatorios_visita "
                f"WHERE vet_id={p} ORDER BY data_relatorio DESC",
                (vet_id,)
            )
        elif fazenda_owner_id is not None:
            cur.execute(
                f"SELECT id,visita_id,vet_id,fazenda_owner_id,data_relatorio,"
                f"animais_inspecionados,achados,tratamentos,recomendacoes,"
                f"proxima_visita,crmv_emissao FROM relatorios_visita "
                f"WHERE fazenda_owner_id={p} ORDER BY data_relatorio DESC",
                (fazenda_owner_id,)
            )
        else:
            return []
        return cur.fetchall()


# ── CARENCIA ──────────────────────────────────────────────────
def adicionar_carencia(animal_id, medicamento, data_aplicacao, carencia_dias):
    """Registra periodo de carencia para abate."""
    _garantir_tabelas_vet()
    from datetime import datetime, timedelta
    try:
        dt = datetime.strptime(str(data_aplicacao)[:10], "%Y-%m-%d").date()
    except Exception:
        from datetime import date
        dt = date.today()
    data_lib = dt + timedelta(days=int(carencia_dias))
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO carencias_ativas (animal_id,medicamento,data_aplicacao,"
            f"carencia_dias,data_liberacao,ativo) VALUES({p},{p},{p},{p},{p},1)",
            (animal_id, medicamento, str(dt), int(carencia_dias), str(data_lib))
        )
        conn.commit()
        return str(data_lib)


def listar_carencias_ativas(owner_id=None):
    """Lista animais em carencia (filtrado por dono do lote)."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    hoje = str(date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        if owner_id is not None:
            cur.execute(
                f"SELECT c.id,c.animal_id,a.identificacao,c.medicamento,"
                f"c.data_aplicacao,c.carencia_dias,c.data_liberacao "
                f"FROM carencias_ativas c "
                f"JOIN animais a ON a.id=c.animal_id "
                f"WHERE c.ativo=1 AND c.data_liberacao >= {p} "
                f"AND a.lote_id IN (SELECT id FROM lotes WHERE owner_id={p}) "
                f"ORDER BY c.data_liberacao",
                (hoje, owner_id)
            )
        else:
            cur.execute(
                f"SELECT c.id,c.animal_id,a.identificacao,c.medicamento,"
                f"c.data_aplicacao,c.carencia_dias,c.data_liberacao "
                f"FROM carencias_ativas c "
                f"JOIN animais a ON a.id=c.animal_id "
                f"WHERE c.ativo=1 AND c.data_liberacao >= {p} "
                f"ORDER BY c.data_liberacao",
                (hoje,)
            )
        return cur.fetchall()


def listar_animais_em_carencia_fazendeiro(owner_id):
    """Lista todos os animais em carencia para o fazendeiro.
    Consulta carencias_ativas vinculadas aos lotes do fazendeiro."""
    import datetime
    hoje = str(datetime.date.today())
    p = _ph()
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT c.animal_id, a.identificacao, c.medicamento, "
                f"c.data_liberacao, c.carencia_dias "
                f"FROM carencias_ativas c "
                f"JOIN animais a ON a.id = c.animal_id "
                f"WHERE c.ativo = 1 AND c.data_liberacao >= {p} "
                f"AND a.lote_id IN (SELECT id FROM lotes WHERE owner_id = {p}) "
                f"ORDER BY c.data_liberacao",
                (hoje, owner_id)
            )
            return cur.fetchall()
    except Exception:
        _log_war.debug('excecao tratada: %s', exc_info=True)
        return []


def animal_em_carencia(animal_id):
    """Retorna lista de carencias ativas para o animal."""
    _garantir_tabelas_vet()
    from datetime import date
    p = _ph()
    hoje = str(date.today())
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT medicamento,data_liberacao FROM carencias_ativas "
            f"WHERE animal_id={p} AND ativo=1 AND data_liberacao >= {p} "
            f"ORDER BY data_liberacao DESC",
            (animal_id, hoje)
        )
        return cur.fetchall()


# ── PAINEL DE SAUDE DO REBANHO ────────────────────────────────
def painel_saude_rebanho(owner_id):
    """Retorna estatisticas sanitarias do rebanho."""
    _garantir_tabelas_vet()
    p = _ph()
    with _conexao() as conn:
        cur = conn.cursor()

        # Total de ocorrencias por tipo
        try:
            cur.execute(
                f"SELECT o.tipo, COUNT(*) FROM ocorrencias o "
                f"JOIN animais a ON a.id=o.animal_id "
                f"JOIN lotes l ON l.id=a.lote_id "
                f"WHERE l.owner_id={p} GROUP BY o.tipo ORDER BY COUNT(*) DESC",
                (owner_id,)
            )
            por_tipo = cur.fetchall()
        except Exception:
            por_tipo = []

        # Total de mortes
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM animais a "
                f"JOIN lotes l ON l.id=a.lote_id "
                f"WHERE l.owner_id={p} AND COALESCE(a.status,'')='MORTO'",
                (owner_id,)
            )
            n_mortes = cur.fetchone()[0]
        except Exception:
            n_mortes = 0

        # Total de animais ativos
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM animais a "
                f"JOIN lotes l ON l.id=a.lote_id "
                f"WHERE l.owner_id={p} AND a.ativo=1",
                (owner_id,)
            )
            n_ativos = cur.fetchone()[0]
        except Exception:
            n_ativos = 0

        # Ocorrencias graves (gravidade Alta)
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM ocorrencias o "
                f"JOIN animais a ON a.id=o.animal_id "
                f"JOIN lotes l ON l.id=a.lote_id "
                f"WHERE l.owner_id={p} AND o.gravidade='Alta'",
                (owner_id,)
            )
            n_graves = cur.fetchone()[0]
        except Exception:
            n_graves = 0

    return {
        "por_tipo":   por_tipo,
        "n_mortes":   n_mortes,
        "n_ativos":   n_ativos,
        "n_graves":   n_graves,
        "taxa_mortalidade": round(100 * n_mortes / max(1, n_mortes + n_ativos), 2),
    }






def _garantir_owner_id_medicamentos():
    """Garante que a tabela medicamentos tem coluna owner_id."""
    with _conexao() as conn:
        cur = conn.cursor()
        try:
            if _usar_postgres():
                cur.execute(
                    "ALTER TABLE medicamentos ADD COLUMN IF NOT EXISTS owner_id INTEGER"
                )
            else:
                cur.execute("PRAGMA table_info(medicamentos)")
                cols = [r[1] for r in cur.fetchall()]
                if 'owner_id' not in cols:
                    cur.execute("ALTER TABLE medicamentos ADD COLUMN owner_id INTEGER")
            conn.commit()
            return True
        except Exception:
            _log_war.debug('excecao tratada: %s', exc_info=True)
            return False


def _garantir_coluna_onboarding():
    """Garante que a coluna onboarding_completo existe na tabela usuarios."""
    with _conexao() as conn:
        cur = conn.cursor()
        try:
            if _usar_postgres():
                cur.execute(
                    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS "
                    "onboarding_completo INTEGER DEFAULT 0"
                )
            else:
                # SQLite: verificar antes de adicionar
                cur.execute("PRAGMA table_info(usuarios)")
                cols = [r[1] for r in cur.fetchall()]
                if 'onboarding_completo' not in cols:
                    cur.execute(
                        "ALTER TABLE usuarios ADD COLUMN "
                        "onboarding_completo INTEGER DEFAULT 0"
                    )
            conn.commit()
            return True
        except Exception:
            _log_war.debug('excecao tratada: %s', exc_info=True)
            return False


def marcar_onboarding_completo(uid):
    """Marca o onboarding como concluido para o usuario."""
    _garantir_coluna_onboarding()
    with _conexao() as conn:
        cur = conn.cursor()
        p = _ph()
        try:
            cur.execute(
                f"UPDATE usuarios SET onboarding_completo=1 WHERE id={p}",
                (uid,)
            )
            conn.commit()
            # Verificar se UPDATE afetou alguma linha
            if hasattr(cur, 'rowcount') and cur.rowcount == 0:
                # Usuario nao encontrado - nao e erro critico
                pass
            return True
        except Exception as e:
            try:
                conn.rollback()
            except Exception as _ew:
                _log_war.debug("excecao ignorada: %s", _ew)
            return False


def onboarding_concluido(uid):
    """Verifica se o usuario ja completou o onboarding."""
    _garantir_coluna_onboarding()
    with _conexao() as conn:
        cur = conn.cursor()
        p = _ph()
        try:
            cur.execute(
                f"SELECT onboarding_completo FROM usuarios WHERE id={p}",
                (uid,)
            )
            r = cur.fetchone()
            return bool(r and r[0])
        except Exception:
            _log_war.debug('excecao tratada: %s', exc_info=True)
            return False


def criar_dados_exemplo(uid):
    """Cria uma fazenda demo com 1 lote e 5 animais ficticios.
    Bloqueia se ultrapassar o limite do plano."""
    import random
    from datetime import date as _d, timedelta as _td

    # Verificar se ja tem dados exemplo
    lotes_user = listar_lotes(owner_id=uid)
    if any('[DEMO]' in (l[1] or '') for l in lotes_user):
        return dict(ja_existe=True, bloqueado=False,
                    msg="Voce ja tem dados de exemplo cadastrados.")

    # Verificar limite do plano (5 animais sao criados)
    try:
        lim = verificar_limite_animais(uid, 5)
        if not lim["pode"]:
            return dict(
                ja_existe=False,
                bloqueado=True,
                msg=(f"Limite do plano atingido. Voce tem {lim['atual']} de "
                     f"{lim['limite']} animais e os dados de exemplo criariam "
                     f"mais 5. Disponiveis: {lim['disponiveis']}. "
                     f"Faca upgrade ou remova animais antes de criar dados de exemplo.")
            )
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    hoje = _d.today()
    inicio = hoje - _td(days=90)

    # Criar lote demo
    lote_id = adicionar_lote(
        nome="[DEMO] Pasto Vitrine",
        descricao="Lote de exemplo - pode excluir quando quiser",
        data_entrada=str(inicio),
        qtd_comprada=5,
        qtd_recebida=5,
        transporte="Demo",
        owner_id=uid
    )

    # Criar 5 animais com pesagens
    nomes = ["DEMO-001", "DEMO-002", "DEMO-003", "DEMO-004", "DEMO-005"]
    pesos_iniciais = [280, 295, 310, 270, 305]
    ganhos = [0.85, 0.75, 0.90, 0.65, 0.80]  # kg/dia

    for i, nome in enumerate(nomes):
        aid = adicionar_animal(nome, 24, lote_id)
        # Pesagem inicial
        adicionar_pesagem(aid, pesos_iniciais[i], str(inicio))
        # Pesagem ha 30 dias
        peso_30 = pesos_iniciais[i] + ganhos[i] * 60
        adicionar_pesagem(aid, round(peso_30, 1), str(inicio + _td(days=60)))
        # Pesagem atual
        peso_hoje = pesos_iniciais[i] + ganhos[i] * 90
        adicionar_pesagem(aid, round(peso_hoje, 1), str(hoje))

    # Adicionar uma ocorrencia exemplo
    primeiro_animal = listar_animais_por_lote(lote_id)[0]
    adicionar_ocorrencia(
        primeiro_animal[0],
        str(inicio + _td(days=30)),
        "Vacina",
        "Vacinacao contra Aftosa (exemplo)",
        "Baixa",
        15.0,
        0,
        "Resolvido"
    )

    return dict(ja_existe=False, bloqueado=False,
                msg="Fazenda exemplo criada! Explore o sistema.",
                lote_id=lote_id)


def remover_dados_exemplo(uid):
    """Remove os dados de exemplo do usuario - cascade manual."""
    lotes_demo = [l for l in listar_lotes(owner_id=uid)
                  if '[DEMO]' in (l[1] or '')]
    n_removidos = 0
    p = _ph()
    for lote in lotes_demo:
        lid = lote[0]
        with _conexao() as conn:
            cur = conn.cursor()
            try:
                # 1. Buscar animais do lote
                cur.execute(
                    f"SELECT id FROM animais WHERE lote_id={p}", (lid,)
                )
                aids = [r[0] for r in cur.fetchall()]

                # 2. Remover registros dos animais
                for aid in aids:
                    for tbl in ['pesagens', 'ocorrencias', 'medicamentos_uso']:
                        try:
                            cur.execute(
                                f"DELETE FROM {tbl} WHERE animal_id={p}",
                                (aid,)
                            )
                        except Exception as _ew:
                            _log_war.debug("excecao ignorada: %s", _ew)
                if aids:
                    cur.execute(
                        f"UPDATE animais SET ativo=0 WHERE lote_id={p}",
                        (lid,)
                    )
                    cur.execute(
                        f"DELETE FROM animais WHERE lote_id={p}",
                        (lid,)
                    )

                # 4. Remover vacinas e outros do lote
                for tbl in ['vacinas_agenda', 'reproducao',
                            'piquetes_historico', 'vendas_lote']:
                    try:
                        cur.execute(
                            f"DELETE FROM {tbl} WHERE lote_id={p}", (lid,)
                        )
                    except Exception as _ew:
                        _log_war.debug("excecao ignorada: %s", _ew)
                cur.execute(f"DELETE FROM lotes WHERE id={p}", (lid,))
                conn.commit()
                n_removidos += 1
            except Exception as e:
                try:
                    conn.rollback()
                except Exception as _ew:
                    _log_war.debug("excecao ignorada: %s", _ew)
    return n_removidos


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
        except Exception as _ew:
            _log_war.debug("excecao ignorada: %s", _ew)
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
