# db/admin.py -- Painel administrativo: metricas, MRR, logs de erro
# Modulo isolado (sem dependencias de outros dominios de negocio).

from datetime import date, datetime, timedelta

from db.core import _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached
from db.schema import _log_db, _log_err, _log_war


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
