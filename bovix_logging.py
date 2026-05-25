"""
bovix_logging.py — Configuracao centralizada de logs do BOVIX.

Uso:
    from bovix_logging import get_logger
    log = get_logger("bovix.modulo")
    log.info("mensagem")
    log.error("erro: %s", err, exc_info=True)
"""
import logging
import logging.handlers
import os
import sys
from datetime import datetime

_CONFIGURED = False
_LOG_DIR    = os.environ.get("BOVIX_LOG_DIR", "/tmp/bovix_logs")


def configurar_logs(nivel=logging.INFO, arquivo=True, console=True):
    """Configura o sistema de logs do BOVIX.
    Chamada uma vez no boot. Idempotente."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    # Garantir diretorio de logs
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
    except Exception:
        pass

    # Logger raiz da aplicacao
    root = logging.getLogger("bovix")
    root.setLevel(nivel)

    # Remover handlers anteriores (Streamlit pode reinjetar)
    for h in list(root.handlers):
        root.removeHandler(h)

    # Formato estruturado
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler de console (stdout)
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(nivel)
        ch.setFormatter(fmt)
        root.addHandler(ch)

    # Handler de arquivo rotativo (5MB x 3 arquivos)
    if arquivo:
        try:
            arquivo_path = os.path.join(_LOG_DIR, "bovix.log")
            fh = logging.handlers.RotatingFileHandler(
                arquivo_path, maxBytes=5 * 1024 * 1024,
                backupCount=3, encoding="utf-8"
            )
            fh.setLevel(nivel)
            fh.setFormatter(fmt)
            root.addHandler(fh)
        except Exception as e:
            print(f"[bovix_logging] Falha ao criar log de arquivo: {e}",
                  file=sys.stderr)

    # Evitar duplicacao via propagacao
    root.propagate = False

    _CONFIGURED = True
    root.info("Sistema de logs inicializado | nivel=%s | arquivo=%s | console=%s",
              logging.getLevelName(nivel), arquivo, console)


def get_logger(nome="bovix"):
    """Retorna logger nomeado. Configura sistema se necessario."""
    if not _CONFIGURED:
        configurar_logs()
    return logging.getLogger(nome)


def log_exception(logger, msg, exc=None):
    """Helper para logar excecao com stack trace."""
    logger.error("%s | %s", msg, exc or "", exc_info=True)
