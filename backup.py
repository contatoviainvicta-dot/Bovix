# backup.py -- Backup do banco de dados
# Suporta PostgreSQL (Supabase) e SQLite

import io
import csv
import zipfile
from datetime import datetime


def gerar_backup_zip(db_path=None):
    """Gera ZIP com CSVs de todas as tabelas.
    Funciona com PostgreSQL (Supabase) e SQLite."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    buf = io.BytesIO()
    try:
        from database import _conexao, _usar_postgres
        with _conexao() as conn:
            cur = conn.cursor()
            if _usar_postgres():
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
            else:
                cur.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
            tabelas = [r[0] for r in cur.fetchall()]

            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                meta = (
                    f"Backup BOVIX\n"
                    f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                    f"Banco: {'PostgreSQL (Supabase)' if _usar_postgres() else 'SQLite'}\n"
                    f"Tabelas: {len(tabelas)}\n"
                )
                zf.writestr("README.txt", meta)

                for tabela in tabelas:
                    try:
                        cur.execute(f"SELECT * FROM {tabela} LIMIT 10000")
                        rows = cur.fetchall()
                        if not rows:
                            continue
                        colunas = [d[0] for d in cur.description]
                        csv_buf = io.StringIO()
                        writer  = csv.writer(csv_buf)
                        writer.writerow(colunas)
                        writer.writerows([
                            [str(v) if v is not None else "" for v in r]
                            for r in rows
                        ])
                        zf.writestr(f"{tabela}.csv", csv_buf.getvalue())
                    except Exception as e:
                        zf.writestr(f"{tabela}_ERRO.txt", str(e))
    except Exception as e:
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("ERRO.txt", f"Erro ao gerar backup: {e}")

    return buf.getvalue()


def gerar_backup_sqlite(db_path="pecuaria.db"):
    """Retorna o arquivo SQLite como bytes (so para banco local)."""
    try:
        with open(db_path, "rb") as f:
            return f.read()
    except Exception:
        return b""


def nome_arquivo_backup(extensao="zip"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_bovix_{ts}.{extensao}"
