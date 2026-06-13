# db/onboarding.py -- Onboarding, progresso e dados de demonstracao
# Gerencia o fluxo de boas-vindas, marcacao de passos concluidos e criacao/
# remocao de dados de exemplo para novos usuarios.
# Depende de db.core e db.schema. Deps de outros dominios via lazy import.

from datetime import date, datetime, timedelta

from db.core import (
    _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached,
    _date_add, _cast_date,
)
from db.schema import _log_db, _log_err, _log_war


# Passos do fluxo de onboarding (ordem importa)
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
    from database import adicionar_animal, adicionar_lote, adicionar_ocorrencia, adicionar_pesagem, listar_animais_por_lote, listar_lotes, verificar_limite_animais  # lazy import
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
    from database import listar_lotes  # lazy import
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
