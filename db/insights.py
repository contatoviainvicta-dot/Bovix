import streamlit as st
# db/insights.py -- Inteligencia, previsoes e KPIs executivos
# Insights de lote, previsao de abate, deteccao de anomalias, dashboards,
# resumos de IA, KPIs e epidemiologia.
# Depende de db.core e db.schema. Deps de outros dominios via lazy import.

from datetime import date, datetime, timedelta

from db.core import (
    _conexao, _ph, _fetch, _fetchone, _usar_postgres, _cached,
    _date_add, _cast_date,
)
from db.schema import _log_db, _log_err, _log_war, _garantir_tabelas_vet


@st.cache_data(ttl=300, show_spinner=False)
def gerar_insights_lote(lote_id):
    from database import listar_animais_por_lote, listar_pesagens, taxa_mortalidade_lote, resumo_lote  # lazy import
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


def prever_abate(lote_id, peso_alvo_kg=450.0, preco_kg=10.0, custo_diario=12.0):
    from database import listar_animais_por_lote, listar_pesagens_todos_animais  # lazy import
    """
    Prevê data e resultado financeiro do abate para cada animal do lote.
    Retorna lista de dicts por animal com previsao.
    """
    import pandas as pd
    from datetime import date as _d, timedelta as timedelta

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
        data_prev = hoje + timedelta(days=dias_rest)
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
    from database import listar_animais_por_lote, listar_pesagens_todos_animais  # lazy import
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
                ))@st.cache_data(ttl=300, show_spinner=False)


    return alertas


def resumo_ia_fazenda(owner_id=None):
    from database import calcular_risco_sanitario, listar_animais_por_lote, listar_lotes, resumo_lote  # lazy import
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


@st.cache_data(ttl=300, show_spinner=False)
def kpis_executivos(owner_id=None, lote_ids=None):
    from database import calcular_gmds_lote, calcular_risco_sanitario, listar_lotes  # lazy import
    """
    KPIs consolidados para o Dashboard Executivo.
    Retorna metricas financeiras, sanitarias e produtivas da fazenda.
    lote_ids: lista de IDs especifica (para vet com fazendas aprovadas)
    """
    import pandas as pd
    from datetime import date as _d, timedelta as timedelta

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
        mes_ref = hoje.replace(day=1) - timedelta(days=m*30)
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


@st.cache_data(ttl=300, show_spinner=False)
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


def epidemiologia_por_fazenda(vet_id):
    """Retorna dados epidemiologicos consolidados por fazenda."""
    _garantir_tabelas_vet()
    from database import listar_fazendas_do_vet, obter_nome_usuario  # lazy import
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
