"""
whatsapp.py — Notificações WhatsApp para o Auroque
Suporta Z-API (brasileiro) e Twilio (internacional)
Configurável pelo admin via config_sistema
"""
import os
import logging
import requests

_log = logging.getLogger("auroque.whatsapp")


# ── HELPERS INTERNOS ──────────────────────────────────────────

def _get_config():
    """Retorna configuração do provedor WhatsApp do banco."""
    try:
        from database import obter_config_sistema
        cfg = obter_config_sistema("whatsapp") or {}
        return cfg
    except Exception as _e:
        _log.debug("config whatsapp nao encontrada: %s", _e)
        return {}


def _fmt_fone(fone: str) -> str:
    """Normaliza telefone para formato internacional: 5511999999999"""
    if not fone:
        return ""
    digitos = "".join(c for c in fone if c.isdigit())
    if len(digitos) == 11 and digitos.startswith("0"):
        digitos = digitos[1:]
    if len(digitos) == 11:          # 11 + 9 dígitos (Brasil com DDD)
        digitos = "55" + digitos
    elif len(digitos) == 10:        # DDD + 8 dígitos (fixo)
        digitos = "55" + digitos
    return digitos


# ── Z-API ─────────────────────────────────────────────────────

def _enviar_zapi(fone: str, mensagem: str, cfg: dict) -> bool:
    """Envia mensagem via Z-API."""
    instance_id = cfg.get("zapi_instance_id") or os.environ.get("ZAPI_INSTANCE_ID", "")
    token       = cfg.get("zapi_token")       or os.environ.get("ZAPI_TOKEN", "")
    client_token= cfg.get("zapi_client_token")or os.environ.get("ZAPI_CLIENT_TOKEN", "")

    if not instance_id or not token:
        _log.warning("Z-API: credenciais nao configuradas")
        return False

    url = f"https://api.z-api.io/instances/{instance_id}/token/{token}/send-text"
    payload = {
        "phone":   _fmt_fone(fone),
        "message": mensagem,
    }
    headers = {"Client-Token": client_token} if client_token else {}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            _log.info("WhatsApp Z-API enviado para %s", fone[-4:])
            return True
        _log.warning("Z-API erro %s: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as _e:
        _log.error("Z-API excecao: %s", _e)
        return False


# ── TWILIO ────────────────────────────────────────────────────

def _enviar_twilio(fone: str, mensagem: str, cfg: dict) -> bool:
    """Envia mensagem via Twilio WhatsApp."""
    account_sid = cfg.get("twilio_account_sid") or os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token  = cfg.get("twilio_auth_token")  or os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = cfg.get("twilio_from_number") or os.environ.get("TWILIO_FROM_NUMBER",
                                                                    "whatsapp:+14155238886")

    if not account_sid or not auth_token:
        _log.warning("Twilio: credenciais nao configuradas")
        return False

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=mensagem,
            from_=from_number,
            to=f"whatsapp:+{_fmt_fone(fone)}"
        )
        _log.info("WhatsApp Twilio enviado sid=%s para %s", msg.sid, fone[-4:])
        return True
    except ImportError:
        # Fallback via requests se twilio não estiver instalado
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        try:
            resp = requests.post(url,
                data={
                    "Body": mensagem,
                    "From": from_number,
                    "To":   f"whatsapp:+{_fmt_fone(fone)}",
                },
                auth=(account_sid, auth_token),
                timeout=10
            )
            if resp.status_code in (200, 201):
                return True
            _log.warning("Twilio erro %s", resp.status_code)
            return False
        except Exception as _e:
            _log.error("Twilio excecao: %s", _e)
            return False
    except Exception as _e:
        _log.error("Twilio excecao: %s", _e)
        return False


# ── INTERFACE PÚBLICA ─────────────────────────────────────────

def enviar_whatsapp(fone: str, mensagem: str) -> bool:
    """Envia mensagem WhatsApp usando o provedor configurado.
    Retorna True se enviado com sucesso."""
    if not fone:
        return False

    cfg      = _get_config()
    provedor = cfg.get("provedor", "").lower()

    # Auto-detectar: se não configurado, tentar Z-API primeiro
    if not provedor:
        if os.environ.get("ZAPI_INSTANCE_ID"):
            provedor = "zapi"
        elif os.environ.get("TWILIO_ACCOUNT_SID"):
            provedor = "twilio"
        else:
            _log.debug("WhatsApp: nenhum provedor configurado")
            return False

    if provedor == "zapi":
        return _enviar_zapi(fone, mensagem, cfg)
    elif provedor == "twilio":
        return _enviar_twilio(fone, mensagem, cfg)
    else:
        _log.warning("Provedor WhatsApp desconhecido: %s", provedor)
        return False


# ── MENSAGENS PADRÃO ──────────────────────────────────────────

def notificar_vacina_pendente(fone: str, nome_animal: str,
                               vacina: str, data: str) -> bool:
    msg = (
        f"🐄 *Auroque — Alerta Sanitário*\n\n"
        f"Vacina pendente: *{vacina}*\n"
        f"Animal: {nome_animal}\n"
        f"Data prevista: {data}\n\n"
        f"Acesse o Auroque para confirmar a vacinação."
    )
    return enviar_whatsapp(fone, msg)


def notificar_carencia_vencendo(fone: str, nome_animal: str,
                                 medicamento: str, data_lib: str) -> bool:
    msg = (
        f"⚠️ *Auroque — Carência Vencendo*\n\n"
        f"Animal: {nome_animal}\n"
        f"Medicamento: {medicamento}\n"
        f"Liberação para abate: *{data_lib}*\n\n"
        f"Verifique o calendário de carências no Auroque."
    )
    return enviar_whatsapp(fone, msg)


def notificar_abate_proximo(fone: str, nome_lote: str,
                             n_animais: int, data: str) -> bool:
    msg = (
        f"🔪 *Auroque — Previsão de Abate*\n\n"
        f"Lote: {nome_lote}\n"
        f"{n_animais} animal(is) próximo(s) do peso ideal\n"
        f"Data estimada: *{data}*\n\n"
        f"Veja a análise completa no Auroque."
    )
    return enviar_whatsapp(fone, msg)


def notificar_receita_nova(fone: str, nome_fazendeiro: str,
                            animal: str, vet: str) -> bool:
    msg = (
        f"💊 *Auroque — Nova Receita*\n\n"
        f"O veterinário *{vet}* emitiu uma receita\n"
        f"para o animal: {animal}\n\n"
        f"Acesse o Auroque para ver o receituário completo."
    )
    return enviar_whatsapp(fone, msg)
