# backup.py -- Backup automatico do banco de dados
# Exporta todas as tabelas em ZIP com CSVs ou copia o arquivo SQLite.

import io
import csv
import sqlite3
import zipfil# backup.py -- Backup automatico do banco de dados
# Exporta todas as tabelas em ZIP com CSVs ou copia o arquivo SQLite.

import io
import csv
import sqlite3
import zipfile
from datetime import datetime


def gerar_backup_zip(db_path):
    buf = io.BytesIO()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tabelas = [
        row[0] for row in
        conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    ]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        meta = (
            f"Backup gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"Tabelas: {', '.join(tabelas)}\n"
        )
        zf.writestr("README.txt", meta)
        for tabela in tabelas:
            try:
                rows = conn.execute(f"SELECT * FROM {tabela}").fetchall()
                if not rows: continue
                csv_buf = io.StringIO()
                writer  = csv.writer(csv_buf)
                writer.writerow(rows[0].keys())
                writer.writerows([tuple(r) for r in rows])
                zf.writestr(f"{tabela}.csv", csv_buf.getvalue())
            except Exception as e:
                zf.writestr(f"{tabela}_ERRO.txt", str(e))
    conn.close()
    return buf.getvalue()


def gerar_backup_sqlite(db_path):
    with open(db_path, "rb") as f:
        return f.read()


def nome_arquivo_backup(extensao="zip"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_pecuaria_{ts}.{extensao}"
from datetime import datetime


def gerar_backup_zip(db_path):
    buf = io.BytesIO()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tabelas = [
        row[0] for row in
        conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    ]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        meta = (
            f"Backup gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"Tabelas: {', '.join(tabelas)}\n"
        )
        zf.writestr("README.txt", meta)
        for tabela in tabelas:
            try:
                rows = conn.execute(f"SELECT * FROM {tabela}").fetchall()
                if not rows: continue
                csv_buf = io.StringIO()
                writer  = csv.writer(csv_buf)
                writer.writerow(rows[0].keys())
                writer.writerows([tuple(r) for r in rows])
                zf.writestr(f"{tabela}.csv", csv_buf.getvalue())
            except Exception as e:
                zf.writestr(f"{tabela}_ERRO.txt", str(e))
    conn.close()
    return buf.getvalue()


def gerar_backup_sqlite(db_path):
    with open(db_path, "rb") as f:
        return f.read()


def nome_arquivo_backup(extensao="zip"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_pecuaria_{ts}.{extensao}"
