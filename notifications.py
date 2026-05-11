# notifications.py -- Envio de alertas por e-mail.
#
# Configuração via st.secrets (secrets.toml) ou variáveis de ambiente:
# [email]
# smtp_host     = "smtp.gmail.com"
# smtp_port     = 587
# smtp_user     = "seu@gmail.com"
# smtp_password = "senha_app"
# remetente     = "Sistema Pecuário <seu@gmail.com>"
#
# Para Gmail: use uma "Senha de app" (não a senha da conta).
# Docs: https://support.google.com/accounts/answer/185833


import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
from typing import Optional

try:
    import streamlit as st
    def _cfg(key: str, fallback: str = "") -> str:
        try:
            return st.secrets["email"].get(key, fallback)
        except Exception:
            import os
            return os.environ.get(f"EMAIL_{key.upper()}", fallback)
except ImportError:
    import os
    def _cfg(key: str, fallback: str = "") -> str:
        return os.environ.get(f"EMAIL_{key.upper()}", fallback)


# ---------------------------------------------------------------------------
# Núcleo de envio
# ---------------------------------------------------------------------------

def _enviar(destinatario: str, assunto: str, corpo_html: str) -> tuple[bool, str]:
    '''
    Envia e-mail. Retorna (sucesso: bool, mensagem: str).
    Silencia falhas para não derrubar o app se e-mail não estiver configurado.
    '''
    host = _cfg("smtp_host", "smtp.gmail.com")
    port = int(_cfg("smtp_port", "587"))
    user = _cfg("smtp_user", "")
    pwd  = _cfg("smtp_password", "")
    rem  = _cfg("remetente", user)

    if not user or not pwd:
        return False, "E-mail não configurado (verifique secrets.toml)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"]    = rem
    msg["To"]      = destinatario
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.login(user, pwd)
            smtp.sendmail(user, destinatario, msg.as_string())
        return True, "E-mail enviado com sucesso"
    except smtplib.SMTPAuthenticationError:
        return False, "Falha de autenticação SMTP -- verifique usuário/senha"
    except smtplib.SMTPException as e:
        return False, f"Erro SMTP: {e}"
    except OSError as e:
        return False, f"Erro de rede: {e}"


# ---------------------------------------------------------------------------
# Template base
# ---------------------------------------------------------------------------

def _template(titulo: str, corpo: str, cor: str = "#1F5C2E") -> str:
    return f'''
    <html><body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:24px">
    <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;
                box-shadow:0 2px 8px rgba(0,0,0,.08)">
      <div style="background:{cor};padding:24px 28px">
        <h1 style="color:#fff;margin:0;font-size:20px;font-weight:600">🐄 Sistema de Gestão Pecuária</h1>
        <p  style="color:rgba(255,255,255,.8);margin:6px 0 0;font-size:14px">{titulo}</p>
      </div>
      <div style="padding:28px;font-size:14px;color:#333;line-height:1.7">
        {corpo}
      </div>
      <div style="padding:16px 28px;background:#f9f9f9;font-size:12px;color:#999;border-top:1px solid #eee">
        Mensagem automática -- não responda a este e-mail.
      </div>
    </div></body></html>
    '''


# ---------------------------------------------------------------------------
# Templates específicos
# ---------------------------------------------------------------------------

def email_boas_vindas(destinatario: str, nome: str, dias_trial: int = 30) -> tuple[bool, str]:
    corpo = f'''
    <p>Olá, <strong>{nome}</strong>! 👋</p>
    <p>Seu acesso ao <strong>Sistema de Gestão Pecuária</strong> foi criado com sucesso.</p>
    <p>Você tem <strong>{dias_trial} dias de teste gratuito</strong> com acesso completo a todos os módulos.</p>
    <ul>
      <li>Cadastro de lotes e animais</li>
      <li>Controle de pesagens e GMD</li>
      <li>Dashboard sanitário e reprodutivo</li>
      <li>Calendário de vacinas e medicamentos</li>
    </ul>
    <p>Qualquer dúvida, responda este e-mail.</p>
    <p>Bom trabalho! 🐄</p>
    '''
    return _enviar(destinatario,
                   "✅ Bem-vindo ao Sistema de Gestão Pecuária",
                   _template("Acesso criado com sucesso", corpo))


def email_trial_expirando(destinatario: str, nome: str,
                           dias_restantes: int) -> tuple[bool, str]:
    cor = "#C8740A" if dias_restantes > 3 else "#A32D2D"
    corpo = f'''
    <p>Olá, <strong>{nome}</strong>!</p>
    <p>Seu período de teste gratuito expira em <strong>{dias_restantes} dia(s)</strong>
       ({date.today().strftime('%d/%m/%Y')}).</p>
    <p>Para continuar usando o sistema e não perder seus dados, assine um plano:</p>
    <div style="text-align:center;margin:24px 0">
      <a href="mailto:contato@seusistema.com.br?subject=Quero assinar o sistema"
         style="background:{cor};color:#fff;padding:12px 28px;border-radius:6px;
                text-decoration:none;font-weight:600;font-size:15px">
        Quero assinar agora
      </a>
    </div>
    <p style="font-size:12px;color:#888">
      Após a expiração seus dados ficam disponíveis por mais 15 dias em modo somente leitura.
    </p>
    '''
    return _enviar(destinatario,
                   f"⚠️ Seu trial expira em {dias_restantes} dia(s)",
                   _template("Aviso de expiração do trial", corpo, cor))


def email_trial_expirado(destinatario: str, nome: str) -> tuple[bool, str]:
    corpo = f'''
    <p>Olá, <strong>{nome}</strong>.</p>
    <p>Seu período de teste gratuito <strong>encerrou hoje</strong>.</p>
    <p>Seus dados estão preservados por mais <strong>15 dias</strong>.
       Após esse prazo, o acesso será encerrado definitivamente.</p>
    <div style="text-align:center;margin:24px 0">
      <a href="mailto:contato@seusistema.com.br?subject=Quero reativar minha conta"
         style="background:#A32D2D;color:#fff;padding:12px 28px;border-radius:6px;
                text-decoration:none;font-weight:600;font-size:15px">
        Reativar minha conta
      </a>
    </div>
    '''
    return _enviar(destinatario,
                   "🔴 Trial encerrado -- reative sua conta",
                   _template("Trial encerrado", corpo, "#A32D2D"))


def email_vacina_pendente(destinatario: str, nome: str,
                           vacinas: list) -> tuple[bool, str]:
    '''vacinas = lista de dicts com chaves: lote, vacina, data_prevista'''
    itens = "".join(
        f"<li><strong>{v.get('vacina','--')}</strong> -- Lote: {v.get('lote','--')}"
        f" -- Previsto: {v.get('data_prevista','--')}</li>"
        for v in vacinas
    )
    corpo = f'''
    <p>Olá, <strong>{nome}</strong>!</p>
    <p>Há <strong>{len(vacinas)} vacina(s) pendente(s)</strong> no sistema:</p>
    <ul style="background:#FFF8E1;padding:16px 16px 16px 32px;border-radius:6px">
      {itens}
    </ul>
    <p>Acesse o <strong>Calendário Sanitário</strong> para confirmar a realização.</p>
    '''
    return _enviar(destinatario,
                   f"💉 {len(vacinas)} vacina(s) pendente(s) no sistema",
                   _template("Alerta de Calendário Sanitário", corpo, "#C8740A"))


def email_medicamento_critico(destinatario: str, nome: str,
                               medicamentos: list) -> tuple[bool, str]:
    '''medicamentos = lista de dicts: nome, estoque_atual, unidade, validade'''
    itens = "".join(
        f"<li><strong>{m.get('nome','--')}</strong> -- "
        f"Estoque: {m.get('estoque_atual',0):.1f} {m.get('unidade','')}"
        f"{' -- Vence: '+m.get('validade','') if m.get('validade') else ''}</li>"
        for m in medicamentos
    )
    corpo = f'''
    <p>Olá, <strong>{nome}</strong>!</p>
    <p>Os seguintes medicamentos precisam de atenção:</p>
    <ul style="background:#FFEBEE;padding:16px 16px 16px 32px;border-radius:6px">
      {itens}
    </ul>
    <p>Acesse o <strong>Estoque de Medicamentos</strong> para repor ou descartar itens vencidos.</p>
    '''
    return _enviar(destinatario,
                   f"💊 {len(medicamentos)} medicamento(s) em alerta",
                   _template("Alerta de Estoque", corpo, "#A32D2D"))


def email_parto_previsto(destinatario: str, nome: str,
                          partos: list) -> tuple[bool, str]:
    '''partos = lista de dicts: animal, lote, data_parto_previsto'''
    itens = "".join(
        f"<li><strong>{p.get('animal','--')}</strong> -- Lote: {p.get('lote','--')}"
        f" -- Previsto: {p.get('data_parto_previsto','--')}</li>"
        for p in partos
    )
    corpo = f'''
    <p>Olá, <strong>{nome}</strong>!</p>
    <p><strong>{len(partos)} parto(s)</strong> estão previstos nos próximos 30 dias:</p>
    <ul style="background:#E8F5E9;padding:16px 16px 16px 32px;border-radius:6px">
      {itens}
    </ul>
    <p>Acesse o <strong>Controle Reprodutivo</strong> para acompanhar.</p>
    '''
    return _enviar(destinatario,
                   f"🐄 {len(partos)} parto(s) previstos nos próximos 30 dias",
                   _template("Alerta Reprodutivo", corpo))


def email_abate_previsto(destinatario: str, nome: str,
                          animais_prontos: list) -> tuple[bool, str]:
    '''animais_prontos = lista de dicts: animal, lote, peso_atual, peso_alvo, data_prevista'''
    itens = "".join(
        f"<li><strong>{a.get('animal','--')}</strong> -- "
        f"{a.get('peso_atual',0):.0f}/{a.get('peso_alvo',0):.0f} kg"
        f" -- Abate previsto: {a.get('data_prevista','--')}</li>"
        for a in animais_prontos
    )
    corpo = f'''
    <p>Olá, <strong>{nome}</strong>!</p>
    <p><strong>{len(animais_prontos)} animal(is)</strong> atingirão o peso de abate nos próximos 30 dias:</p>
    <ul style="background:#E3F2FD;padding:16px 16px 16px 32px;border-radius:6px">
      {itens}
    </ul>
    <p>Acesse o <strong>Painel de Decisão</strong> para planejar a saída do lote.</p>
    '''
    return _enviar(destinatario,
                   f"🥩 {len(animais_prontos)} animal(is) prontos para abate",
                   _template("Previsão de Abate", corpo))


# ---------------------------------------------------------------------------
# Verificação de configuração
# ---------------------------------------------------------------------------

def email_configurado() -> bool:
    '''Retorna True se as credenciais SMTP estão presentes.'''
    return bool(_cfg("smtp_user") and _cfg("smtp_password"))
