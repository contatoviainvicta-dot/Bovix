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


def criar_dados_demo(owner_id, vet_uid=None):
    """Cria fazenda demo com dados fictícios para novo usuário.
    Cobre 3 fluxos da demo:
    1. Produtor: Workspace → Pesagem → Dashboard Sanitário
    2. Veterinário: Prontuário → Controle Carência → Receituário
    3. Financeiro: DRE com custos e KPIs preenchidos
    """
    from datetime import date, timedelta, datetime
    p = _ph()
    _log_db.info("Criando dados demo para owner_id=%s", owner_id)
    try:
        with _conexao() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM lotes WHERE owner_id={p}", (owner_id,)
            )
            r = cur.fetchone()
            cnt = r[0] if isinstance(r, (tuple, list)) else (r['count'] if 'count' in r.keys() else list(r)[0])
            if cnt and int(cnt) > 0:
                return True

            hoje = date.today()
            d90 = str(hoje - timedelta(days=90))
            d60 = str(hoje - timedelta(days=60))
            d45 = str(hoje - timedelta(days=45))
            d30 = str(hoje - timedelta(days=30))
            d15 = str(hoje - timedelta(days=15))
            d7f = str(hoje + timedelta(days=7))

            # Lote demo
            if _usar_postgres():
                cur.execute(
                    f"INSERT INTO lotes (nome,descricao,data_entrada,"
                    f"qtd_comprada,qtd_recebida,preco_por_animal,owner_id,status)"
                    f" VALUES ({p},{p},{p},{p},{p},{p},{p},{p}) RETURNING id",
                    ("Lote Demo — Nelore 2025",
                     "Lote criado automaticamente para demonstração",
                     d90, 8, 8, 2800.00, owner_id, "ATIVO")
                )
                lote_id = cur.fetchone()[0]
            else:
                cur.execute(
                    f"INSERT INTO lotes (nome,descricao,data_entrada,"
                    f"qtd_comprada,qtd_recebida,preco_por_animal,owner_id,status)"
                    f" VALUES ({p},{p},{p},{p},{p},{p},{p},{p})",
                    ("Lote Demo — Nelore 2025",
                     "Lote criado automaticamente para demonstração",
                     d90, 8, 8, 2800.00, owner_id, "ATIVO")
                )
                lote_id = cur.lastrowid
            conn.commit()

            # 8 animais com peso_alvo (barra de progresso ao abate)
            animais = [
                ("DEMO-01","Nelore","M",24,320,450),
                ("DEMO-02","Nelore","M",22,305,440),
                ("DEMO-03","Nelore","M",24,332,460),
                ("DEMO-04","Angus", "M",20,348,480),
                ("DEMO-05","Angus", "M",21,338,470),
                ("DEMO-06","Nelore","F",18,280,420),
                ("DEMO-07","Nelore","F",20,295,430),
                ("DEMO-08","Angus", "M",23,355,490),
            ]
            animal_ids = []
            for ident, raca, sexo, idade, peso_ini, peso_alvo in animais:
                if _usar_postgres():
                    cur.execute(
                        f"INSERT INTO animais (identificacao,raca,sexo,"
                        f"idade,peso_entrada,peso_alvo,lote_id,ativo,status)"
                        f" VALUES ({p},{p},{p},{p},{p},{p},{p},1,'ATIVO') RETURNING id",
                        (ident, raca, sexo, idade, peso_ini, peso_alvo, lote_id)
                    )
                    animal_ids.append(cur.fetchone()[0])
                else:
                    cur.execute(
                        f"INSERT INTO animais (identificacao,raca,sexo,"
                        f"idade,peso_entrada,peso_alvo,lote_id,ativo,status)"
                        f" VALUES ({p},{p},{p},{p},{p},{p},{p},1,'ATIVO')",
                        (ident, raca, sexo, idade, peso_ini, peso_alvo, lote_id)
                    )
                    animal_ids.append(cur.lastrowid)
            conn.commit()

            # 4 pesagens por animal — curva de crescimento real
            gmds = [0.90, 0.80, 0.95, 1.00, 0.85, 0.70, 0.75, 1.05]
            pesos_base = [320, 305, 332, 348, 338, 280, 295, 355]
            for i, aid in enumerate(animal_ids):
                g = gmds[i]
                pb = pesos_base[i]
                for dias in [90, 60, 30, 0]:
                    dt = str(hoje - timedelta(days=dias))
                    cur.execute(
                        f"INSERT INTO pesagens (animal_id,peso,data)"
                        f" VALUES ({p},{p},{p})",
                        (aid, round(pb + g * (90 - dias), 1), dt)
                    )
            conn.commit()

            # Ocorrências variadas — Dashboard Sanitário impactante
            ocorrencias = [
                (animal_ids[0], d60, "Doenca",
                 "Tristeza parasitária — tratado com imidocarb",
                 "Alta", 180.0, 5, "Resolvido"),
                (animal_ids[1], d45, "Medicamento",
                 "Ivermectina 1% — controle de carrapato",
                 "Baixa", 35.0, 0, "Resolvido"),
                (animal_ids[2], d30, "Lesao",
                 "Lesão no casco — curativo e restrição de piquete",
                 "Media", 60.0, 7, "Em tratamento"),
                (animal_ids[3], d15, "Doenca",
                 "Pneumonia leve — antibioticoterapia iniciada",
                 "Alta", 220.0, 10, "Em tratamento"),
                (animal_ids[4], d30, "Vacina",
                 "Vacinação aftosa — dose reforço",
                 "Baixa", 18.0, 0, "Resolvido"),
                (animal_ids[5], d15, "Medicamento",
                 "Closantel 10% — fasciolose",
                 "Media", 45.0, 0, "Resolvido"),
            ]
            for oc in ocorrencias:
                try:
                    cur.execute(
                        f"INSERT INTO ocorrencias "
                        f"(animal_id,data,tipo,descricao,gravidade,custo,"
                        f"dias_recuperacao,status)"
                        f" VALUES ({p},{p},{p},{p},{p},{p},{p},{p})", oc
                    )
                except Exception as _ew:
                    _log_war.debug("ocorrencia demo: %s", _ew)
            conn.commit()

            # Carências ativas — Controle Carência vet
            carencias = [
                (animal_ids[3], "Enrofloxacina 5%",  d15, 28),
                (animal_ids[4], "Ivermectina 1%",    d30, 35),
                (animal_ids[5], "Closantel 10%",     d15, 42),
            ]
            for cid, med, dt_ap, dias_car in carencias:
                try:
                    dt_lib = str(
                        datetime.strptime(dt_ap, "%Y-%m-%d").date()
                        + timedelta(days=dias_car)
                    )
                    cur.execute(
                        f"INSERT INTO carencias_ativas "
                        f"(animal_id,medicamento,data_aplicacao,"
                        f"carencia_dias,data_liberacao,ativo)"
                        f" VALUES ({p},{p},{p},{p},{p},1)",
                        (cid, med, dt_ap, dias_car, dt_lib)
                    )
                except Exception as _ew:
                    _log_war.debug("carencia demo: %s", _ew)
            conn.commit()

            # Custos — DRE preenchido
            for cat, desc, val, dias in [
                ("racao",       "Ração concentrada — 3 meses",  4200.00, 80),
                ("medicamento", "Vermifugação e vacinas",         480.00, 75),
                ("mao_de_obra", "Mão de obra — 3 meses",        1800.00, 70),
                ("veterinario", "Visita técnica",                 350.00, 45),
            ]:
                try:
                    cur.execute(
                        f"INSERT INTO custos_lote"
                        f" (lote_id,categoria,descricao,valor,data_lancamento)"
                        f" VALUES ({p},{p},{p},{p},{p})",
                        (lote_id, cat, desc, val,
                         str(hoje - timedelta(days=dias)))
                    )
                except Exception as _ew:
                    _log_war.debug("custo demo: %s", _ew)
            conn.commit()

        # Vinculação vet↔fazenda (fora do with para não travar)
        if vet_uid:
            try:
                from db.veterinario import (
                    solicitar_acesso_vet, aprovar_acesso_vet
                )
                solicitar_acesso_vet(vet_uid, owner_id)
                aprovar_acesso_vet(vet_uid, owner_id, owner_id, aprovar=True)
                _log_db.info("Vet %s vinculado à fazenda demo", vet_uid)
            except Exception as _ew:
                _log_war.debug("vinculo vet demo: %s", _ew)
            try:
                from db.clinica import adicionar_visita
                adicionar_visita(
                    vet_uid, owner_id, d7f,
                    "Revisão sanitária e vacinação aftosa",
                    90, "Visita de demonstração"
                )
            except Exception as _ew:
                _log_war.debug("visita demo: %s", _ew)

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


def criar_dados_exemplo(uid, vet_uid=None):
    """Cria fazenda demo completa cobrindo 3 fluxos:
    1. Produtor: Workspace → Pesagem → Dashboard Sanitário
    2. Veterinário: Prontuário → Controle Carência → Receituário
    Se vet_uid fornecido, vincula o veterinário à fazenda demo.
    """
    from database import (  # lazy import
        adicionar_animal, adicionar_lote, adicionar_ocorrencia,
        adicionar_pesagem, listar_animais_por_lote, listar_lotes,
        verificar_limite_animais,
    )
    from datetime import date, timedelta
    import random

    # ── Verificar se já existe ────────────────────────────────────
    lotes_user = listar_lotes(owner_id=uid)
    if any('[DEMO]' in (l[1] or '') for l in lotes_user):
        return dict(ja_existe=True, bloqueado=False,
                    msg="Você já tem dados de exemplo cadastrados.")

    # ── Verificar limite do plano ─────────────────────────────────
    try:
        lim = verificar_limite_animais(uid, 8)
        if not lim["pode"]:
            return dict(
                ja_existe=False, bloqueado=True,
                msg=(f"Limite do plano atingido ({lim['atual']}/{lim['limite']} "
                     f"animais). Faça upgrade ou remova animais antes.")
            )
    except Exception as _ew:
        _log_war.debug("excecao ignorada: %s", _ew)

    hoje = date.today()
    d90  = hoje - timedelta(days=90)  # entrada no lote
    d60  = hoje - timedelta(days=60)
    d45  = hoje - timedelta(days=45)
    d30  = hoje - timedelta(days=30)
    d15  = hoje - timedelta(days=15)

    # ── FLUXO 1: Lote + animais + pesagens + ocorrências ─────────
    lote_id = adicionar_lote(
        nome="[DEMO] Confinamento Vitrine",
        descricao="Lote de exemplo — pode excluir quando quiser",
        data_entrada=str(d90),
        qtd_comprada=8, qtd_recebida=8,
        transporte="Demo",
        owner_id=uid
    )

    # 8 animais com peso_alvo definido (mostra barra de progresso)
    nomes_pesos = [
        ("DEMO-001", 280, 450, 0.90),
        ("DEMO-002", 295, 460, 0.80),
        ("DEMO-003", 310, 470, 0.95),
        ("DEMO-004", 270, 440, 0.70),
        ("DEMO-005", 305, 455, 0.85),
        ("DEMO-006", 290, 450, 0.75),
        ("DEMO-007", 315, 480, 1.00),
        ("DEMO-008", 285, 445, 0.65),
    ]

    ids = []
    for nome, peso_ini, peso_alvo, gmd in nomes_pesos:
        aid = adicionar_animal(
            nome, 24, lote_id,
            sexo="macho",
            peso_entrada=float(peso_ini),
            peso_alvo=float(peso_alvo)
        )
        ids.append(aid)
        # 4 pesagens = curva de crescimento convincente
        adicionar_pesagem(aid, float(peso_ini),            str(d90))
        adicionar_pesagem(aid, round(peso_ini+gmd*30, 1),  str(d60))
        adicionar_pesagem(aid, round(peso_ini+gmd*60, 1),  str(d30))
        adicionar_pesagem(aid, round(peso_ini+gmd*90, 1),  str(hoje))

    # Ocorrências variadas — Dashboard Sanitário fica rico
    ocorrencias_demo = [
        (ids[0], d60, "Doenca",      "Tristeza parasitária — tratado com imidocarb",   "Alta",   180.0, 5,  "Resolvido"),
        (ids[1], d45, "Medicamento", "Ivermectina 1% aplicada — controle de carrapato", "Baixa",  35.0,  0,  "Resolvido"),
        (ids[2], d30, "Lesao",       "Lesão no casco — curativo e restrição de piquete","Media",  60.0,  7,  "Em tratamento"),
        (ids[3], d15, "Doenca",      "Pneumonia leve — antibioticoterapia iniciada",    "Alta",   220.0, 10, "Em tratamento"),
        (ids[4], d30, "Vacina",      "Vacinação aftosa dose reforço",                   "Baixa",  18.0,  0,  "Resolvido"),
        (ids[5], d15, "Medicamento", "Closantel aplicado — fasciolose",                 "Media",  45.0,  0,  "Resolvido"),
    ]
    for oc in ocorrencias_demo:
        try:
            adicionar_ocorrencia(
                oc[0], str(oc[1]), oc[2], oc[3], oc[4],
                oc[5], oc[6], oc[7]
            )
        except Exception as _ew:
            _log_war.debug("ocorrencia demo ignorada: %s", _ew)

    # ── FLUXO 2: Carências ativas (Controle Carência vet) ────────
    # Animal DEMO-004 com pneumonia — antibiótico tem carência de 28 dias
    # Animal DEMO-005 — ivermectina tem carência de 35 dias
    carencias_demo = [
        (ids[3], "Enrofloxacina 5%",  str(d15), 28),   # libera em d15+28
        (ids[4], "Ivermectina 1%",    str(d30), 35),   # libera em d30+35 = futuro
        (ids[5], "Closantel 10%",     str(d15), 42),   # libera em d15+42 = futuro
    ]
    for cid, med, dt_aplic, dias in carencias_demo:
        try:
            from db.veterinario import adicionar_carencia  # lazy
            adicionar_carencia(cid, med, dt_aplic, dias)
        except Exception as _ew:
            _log_war.debug("carencia demo ignorada: %s", _ew)

    # ── FLUXO 3: Vinculação vet↔fazenda (se vet_uid fornecido) ───
    if vet_uid:
        try:
            from db.veterinario import solicitar_acesso_vet, aprovar_acesso_vet  # lazy
            solicitar_acesso_vet(vet_uid, uid)
            aprovar_acesso_vet(vet_uid, uid, uid, aprovar=True)
            _log_db.info("Vet %s vinculado à fazenda demo %s", vet_uid, uid)
        except Exception as _ew:
            _log_war.debug("vinculo vet demo ignorado: %s", _ew)

        # Visita técnica agendada (aparece na Agenda Visitas)
        try:
            from db.clinica import adicionar_visita  # lazy
            adicionar_visita(
                vet_uid, uid,
                str(hoje + timedelta(days=7)),
                "Revisão sanitária e vacinação aftosa",
                90, "Visita de exemplo"
            )
        except Exception as _ew:
            _log_war.debug("visita demo ignorada: %s", _ew)

    return dict(
        ja_existe=False, bloqueado=False,
        msg="Fazenda demo criada! Explore o sistema com os dados de exemplo.",
        lote_id=lote_id,
        n_animais=len(ids),
        n_ocorrencias=len(ocorrencias_demo),
        n_carencias=len(carencias_demo),
    )


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
