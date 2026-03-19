"""
setup_sheets.py — Setup tab di Google Sheets HAR yang sudah ada

Jalankan SEKALI saja:
  python setup_sheets.py
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1vuGQFh0qzZi4dL5WfhP6tIjNsXUZeNY5o8hHzL-lvAM"

def get_client():
    json_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "./credentials.json")
    creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
    return gspread.authorize(creds)

def get_or_create_ws(sh, title, rows=1000, cols=15):
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)

def setup():
    gc = get_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    print(f"✓ Spreadsheet ditemukan: {sh.title}")
    print()

    header_fmt = {
        "backgroundColor": {"red": 0.13, "green": 0.16, "blue": 0.22},
        "textFormat": {"bold": True, "foregroundColor": {"red": 0.6, "green": 0.7, "blue": 0.9}},
        "horizontalAlignment": "CENTER"
    }

    # ── TAB 1: TRANSAKSI ─────────────────────────────────────────────────────
    ws_t = get_or_create_ws(sh, "TRANSAKSI")
    if ws_t.row_count < 2 or ws_t.cell(1, 1).value != "TGL":
        ws_t.clear()
        ws_t.append_row([
            "TGL", "NAMA", "TIPE NOTA", "JENIS",
            "KG", "UKURAN", "HARGA/KG",
            "JUMLAH (Rp)", "KAS KELUAR (Rp)", "KAS MASUK (Rp)",
            "STOK ±KG", "CATATAN"
        ])
        ws_t.format("A1:L1", header_fmt)
        ws_t.freeze(rows=1)
    print("✓ Tab TRANSAKSI siap")

    # ── TAB 2: KAS ───────────────────────────────────────────────────────────
    ws_k = get_or_create_ws(sh, "KAS")
    if ws_k.cell(1, 1).value != "TANGGAL":
        ws_k.clear()
        ws_k.append_row(["TANGGAL", "KAS KELUAR", "KAS MASUK", "NET", "SALDO KUMULATIF", "KETERANGAN"])
        ws_k.append_row(["SALDO AWAL", "", "", "", "0", ""])
        ws_k.format("A1:F1", header_fmt)
        ws_k.freeze(rows=1)
    print("✓ Tab KAS siap")

    # ── TAB 3: STOK ──────────────────────────────────────────────────────────
    ws_s = get_or_create_ws(sh, "STOK", rows=20, cols=10)
    if ws_s.cell(1, 1).value != "JENIS UDANG":
        ws_s.clear()
        ws_s.append_row([
            "JENIS UDANG", "KG MASUK", "KG KELUAR JUAL", "KG KELUAR PACKING",
            "STOK AKTUAL", "% PROGRESS TRIP"
        ])
        jenis_list = [
            "Tiger (T)", "White (W)", "Brown (BR)",
            "Tiger Head On (HO)", "White Head On (WHO)", "Pink Tambak (PT)"
        ]
        for i, nama in enumerate(jenis_list):
            r = i + 2
            ws_s.append_row([nama, 0, 0, 0, f"=B{r}-C{r}-D{r}", f'=IF(E{r}>0,E{r}/2000,"—")'])
        ws_s.format("A1:F1", header_fmt)
        ws_s.freeze(rows=1)
    print("✓ Tab STOK siap")

    # ── TAB 4: TRIP ──────────────────────────────────────────────────────────
    ws_tr = get_or_create_ws(sh, "TRIP", rows=100, cols=10)
    if ws_tr.cell(1, 1).value != "TRIP #":
        ws_tr.clear()
        ws_tr.append_row([
            "TRIP #", "TANGGAL", "KG TOTAL", "HARGA JUAL/KG",
            "REVENUE", "TOTAL COST BELI", "MARGIN", "MARGIN/KG", "KETERANGAN"
        ])
        ws_tr.format("A1:I1", header_fmt)
        ws_tr.freeze(rows=1)
    print("✓ Tab TRIP siap")

    print()
    print("=" * 55)
    print("SELESAI. Tambahkan ini ke Railway Variables:")
    print(f"GOOGLE_SHEETS_SPREADSHEET_ID = {SPREADSHEET_ID}")
    print("=" * 55)

if __name__ == "__main__":
    setup()
