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
    STATUS_ANIMAL, STATUS_LOTE,
    listar_animais, listar_animais_por_lote, adicionar_animal, obter_animal,
    atualizar_animal, excluir_animal, atualizar_status_animal,
    listar_animais_por_status, contagem_status_animais, importar_animais_csv,
)

# ── Lotes (movidos para db/lotes.py) ─────────────────────────────────────────
from db.lotes import (
    adicionar_lote, listar_lotes, obter_lote, atualizar_lote, excluir_lote,
    resumo_lote, atualizar_status_lote, adicionar_custo_lote, listar_custos_lote,
    calcular_margem_lote, encerrar_lote, verificar_limite_fazendas,
)

# ── Usuarios (movidos para db/usuarios.py) ───────────────────────────────────
from db.usuarios import (
    TRIAL_DIAS,
    _hash_senha, _bcrypt_hash, _bcrypt_verify, _is_bcrypt_hash,
    email_valido, email_ja_cadastrado, auto_registrar_usuario, criar_usuario,
    obter_nome_usuario, autenticar_usuario, listar_usuarios, usuario_existe,
    alterar_senha, ativar_trial, obter_status_plano,
    listar_usuarios_trial_expirando, definir_plano_usuario, obter_limites_usuario,
    listar_fazendas_do_vet, aprovar_conta_usuario, adicionar_fazenda,
    listar_fazendas, registrar_auditoria, listar_auditoria,
    _garantir_tabela_login_tentativas, registrar_tentativa_login,
    verificar_bloqueio_login, limpar_tentativas_login, obter_crmv_usuario,
    atualizar_crmv, salvar_coords_fazenda, listar_coords_fazendas,
    buscar_usuario_por_email, obter_plano, atualizar_plano, enviar_email,
    enviar_email_boas_vindas, enviar_email_alerta_diario, is_primeiro_login,
)
# Reexportar _PLANOS (usado por admin_painel e crescimento)
from db.core import _PLANOS

# ── Veterinario (movidos para db/veterinario.py) ─────────────────────────────
from db.veterinario import (
    adicionar_ocorrencia, listar_ocorrencias, atualizar_ocorrencia,
    excluir_ocorrencia, listar_ocorrencias_em_tratamento, solicitar_acesso_vet,
    aprovar_acesso_vet, revogar_acesso_vet, listar_acessos_vet, listar_lotes_vet,
    adicionar_vacina_agenda, registrar_vacina_realizada, listar_vacinas_agenda,
    listar_vacinas_pendentes, adicionar_medicamento, listar_medicamentos,
    atualizar_estoque, registrar_uso_medicamento, listar_medicamentos_criticos,
    verificar_carencia, adicionar_piquete, listar_piquetes, alocar_lote_piquete,
    liberar_piquete, historico_piquete, listar_ocorrencias_todos_animais,
    calcular_risco_sanitario, criar_campanha, listar_campanhas,
    adicionar_lote_campanha, listar_lotes_campanha, registrar_vacinacao_campanha,
    sincronizar_campanha_executada, resumo_campanha, resumo_financeiro_vet,
    sincronizar_ocorrencias_receitas, adicionar_carencia, listar_carencias_ativas,
    listar_animais_em_carencia_fazendeiro, animal_em_carencia,
)

# ── Financeiro (movidos para db/financeiro.py) ───────────────────────────────
from db.financeiro import (
    calcular_score_saude, calcular_previsao_abate, salvar_cotacao,
    obter_ultima_cotacao, calcular_scores_lote, margem_bruta_lote,
    dashboard_financeiro_fazendeiro, dre_por_periodo, curva_resultado_mensal,
    listar_cotacoes,
)

# ── Admin (movidos para db/admin.py) ─────────────────────────────────────────
from db.admin import (
    admin_metricas_usuarios, admin_calcular_mrr, admin_adicionar_ajuste_mrr,
    admin_listar_usuarios, admin_historico_acessos, admin_registrar_erro,
    admin_listar_erros, admin_erros_email_log, admin_metricas_produto,
)

# ── Clinica veterinaria (movidos para db/clinica.py) ─────────────────────────
from db.clinica import (
    adicionar_exame, atualizar_exame, listar_exames, adicionar_monitoramento,
    registrar_evolucao, encerrar_monitoramento, listar_monitoramentos,
    monitoramentos_vencendo, lancar_honorario, listar_honorarios,
    listar_itens_honorario, registrar_pagamento_honorario, cancelar_honorario,
    listar_receitas, adicionar_receita, adicionar_protocolo, listar_protocolos,
    adicionar_item_protocolo, listar_itens_protocolo, aplicar_protocolo_no_lote,
    adicionar_visita, listar_visitas, atualizar_status_visita,
    adicionar_relatorio_visita, listar_relatorios,
)

# ── Insights / IA / KPIs (movidos para db/insights.py) ───────────────────────
from db.insights import (
    gerar_insights_lote, prever_abate, detectar_anomalias_peso,
    resumo_ia_fazenda, resumo_dashboard, kpis_executivos,
    painel_saude_rebanho, epidemiologia_por_fazenda,
)

# ── Onboarding / dados demo (movidos para db/onboarding.py) ──────────────────
from db.onboarding import (
    obter_progresso_onboarding, marcar_passo_onboarding, onboarding_completo,
    criar_dados_demo, _garantir_coluna_onboarding, marcar_onboarding_completo,
    onboarding_concluido, criar_dados_exemplo, remover_dados_exemplo,
    _PASSOS_ONBOARDING,
)

# ── Operacoes de campo (movidos para db/operacoes.py) ────────────────────────
from db.operacoes import (
    adicionar_reproducao, atualizar_reproducao, listar_reproducao,
    listar_partos_previstos, taxa_prenhez_lote, registrar_morte,
    listar_mortalidade, taxa_mortalidade_lote, registrar_gta, listar_gta,
    registrar_sisbov, obter_sisbov, transferir_animal, listar_movimentacoes,
    enviar_mensagem, listar_mensagens, marcar_mensagem_lida,
    contar_mensagens_nao_lidas,
)

# ── Consultas / utilitarios transversais (movidos para db/consultas.py) ──────
from db.consultas import (
    buscar_animal_global, contar_animais_no_lote, atualizar_animal_detalhes,
    listar_lotes_por_status, listar_tratamentos_vencidos, converter_para_pago,
    verificar_limite_animais, listar_solicitacoes_pendentes, lote_ja_vendido,
    listar_animais_por_lote_status, atualizar_qtd_lote, historico_clinico_animal,
    calendario_abate, sincronizar_todos_lotes,
)

# ── LOTES ────────────────────────────────────────────────────────────────────






# ── OCORRENCIAS ──────────────────────────────────────────────────────────────


# ── USUARIOS ─────────────────────────────────────────────────────────────────
# ─── BCRYPT — novo sistema de hash ───────────────────────────────────────────

# ── PLANOS E VETERINARIO ────────────────────────────────────────────────────


# ── Acesso veterinario-fazenda ───────────────────────────────────────────────


# ── FAZENDAS ──────────────────────────────────────────────────────────────────
# ── VACINAS ───────────────────────────────────────────────────────────────────
# ── REPRODUCAO ────────────────────────────────────────────────────────────────
# ── PIQUETES ──────────────────────────────────────────────────────────────────
# ── MORTALIDADE ───────────────────────────────────────────────────────────────
# ── AUDITORIA ─────────────────────────────────────────────────────────────────
# ── GTA / SISBOV ──────────────────────────────────────────────────────────────
# ── SCORE DE SAUDE ────────────────────────────────────────────────────────────
# ── PREVISAO DE ABATE ─────────────────────────────────────────────────────────
# ── VENDAS / MARGEM ───────────────────────────────────────────────────────────


# ── CICLO DE VIDA: VENDA E ENCERRAMENTO ──────────────────────




# ── COTACOES ──────────────────────────────────────────────────────────────────
# ── GMD TEMPORAL ──────────────────────────────────────────────────────────────
# ── CICLO DE VIDA DO LOTE ─────────────────────────────────────────────────────

# ── IMPORTACAO CSV ─────────────────────────────────────────────────────────────


# ── CONSISTENCIA DE LOTE ──────────────────────────────────────────────────────

# ── QUERIES AGREGADAS (elimina N+1) ─────────────────────────────────────────

# ── IA E PREDICAO ────────────────────────────────────────────────────────────

# MODULO VETERINARIO - Funcoes CRUD
# ============================================================

# ── RECEITUARIO DIGITAL ───────────────────────────────────────
# ── EXAMES LABORATORIAIS ─────────────────────────────────────
# ── MONITORAMENTO POS-TRATAMENTO ──────────────────────────────
# ── HONORARIOS VETERINARIOS ──────────────────────────────────
# ── MENSAGENS VET-FAZENDEIRO ─────────────────────────────────
# ── CAMPANHAS DE VACINACAO ────────────────────────────────────
# ── COORDENADAS DE FAZENDAS ───────────────────────────────────
# ── DADOS EPIDEMIOLOGICOS ──────────────────────────────────────
# ── HISTORICO CLINICO PDF ──────────────────────────────────────


# ── PLANOS E LIMITES ─────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD FINANCEIRO DO FAZENDEIRO
# ═══════════════════════════════════════════════════════════════════════════



# ── VENDAS DE LOTE ───────────────────────────────────────────




# ── DRE POR PERÍODO ───────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════
# PAINEL ADMIN — MRR, USUARIOS, CHURN, ERROS
# ═══════════════════════════════════════════════════════════════════════════





# ── ONBOARDING ────────────────────────────────────────────────


# ── IMPORTACAO CSV ────────────────────────────────────────────


# ── PROTOCOLOS SANITARIOS ─────────────────────────────────────
# ── VISITAS TECNICAS ──────────────────────────────────────────
# ── RELATORIOS DE VISITA ──────────────────────────────────────
# ── CARENCIA ──────────────────────────────────────────────────
# ── PAINEL DE SAUDE DO REBANHO ────────────────────────────────
