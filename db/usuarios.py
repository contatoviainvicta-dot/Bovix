# db/usuarios.py -- Autenticacao, usuarios, planos, fazendas, email
# Modulo autocontido (sem dependencias de outros dominios de negocio).

import os
import re
import hashlib
import secrets
from datetime import date, datetime, timedelta
_date = date       # alias usado em algumas funcoes
_td = timedelta    # alias usado em algumas funcoes

try:
    import bcrypt
except ImportError:
    bcrypt = None

from db.core import (
    _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached,
    PLANOS_FAZENDEIRO, PLANOS_VETERINARIO,
    UPGRADE_MSG_FAZENDEIRO, UPGRADE_MSG_VETERINARIO,
    _PLANOS,
)
from db.schema import _log_db, _log_err, _log_war

# Dias de trial gratuito
TRIAL_DIAS = 30


def _hash_senha(senha, salt):
    """Hash legado SHA256. Mantido para verificacao de senhas antigas."""
    return hashlib.sha256((salt + senha).encode()).hexdigest()


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


def definir_plano_usuario(usuario_id, perfil, plano_nome, admin_id, dias_validade=365):
    p = _ph()
    if perfil == 'veterinario':
        cfg = PLANOS_VETERINARIO.get(plano_nome, PLANOS_VETERINARIO['trial'])
        limite_f = cfg['limite_fazendas']
        limite_a = 0
    else:
        cfg = PLANOS_FAZENDEIRO.get(plano_nome, PLANOS_FAZENDEIRO['trial'])
        limite_f = 0
        limite_a = cfg['limite_animais']
    # Estender a validade do plano (evita ficar com data expirada antiga)
    nova_expira = str(_date.today() + _td(days=dias_validade))
    with _conexao() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE usuarios SET plano={p}, plano_nome={p},"
            f" limite_animais={p}, limite_fazendas={p},"
            f" plano_expira={p}, ativo=1,"
            f" status_conta='ativo' WHERE id={p}",
            ('pago', plano_nome, limite_a, limite_f, nova_expira, usuario_id),
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
