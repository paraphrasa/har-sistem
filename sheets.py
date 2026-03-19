"""
sheets.py — Tulis data nota ke Google Sheets HAR

3 operasi per konfirmasi:
  1. Append ke TRANSAKSI (satu baris per item)
  2. Append ke KAS (satu baris per nota)
  3. Update STOK (baca → tambah → tulis balik)
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Urutan jenis di tab STOK (baris 2–7)
JENIS_ROW = {
    "T":   2,
    "W":   3,
    "BR":  4,
    "HO":  5,
    "WHO": 6,
    "PT":  7,
}

_client = None
_spreadsheet = None

def get_sheet():
    global _client, _spreadsheet
    if _spreadsheet is None:
        json_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "./credentials.json")

        # Support credentials dari environment variable (untuk Railway)
        json_str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if json_str:
            import json, tempfile
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            tmp.write(json_str)
            tmp.close()
            json_path = tmp.name

        creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
        _client = gspread.authorize(creds)

        sheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID")
        if not sheet_id:
            raise RuntimeError("GOOGLE_SHEETS_SPREADSHEET_ID tidak ditemukan di environment")

        _spreadsheet = _client.open_by_key(sheet_id)

    return _spreadsheet


def tulis(data: dict) -> dict:
    """
    Tulis satu nota ke Sheets.
    Return {"status": "ok"} atau {"status": "error", "error": "..."}
    """
    try:
        sh = get_sheet()
        ws_transaksi = sh.worksheet("TRANSAKSI")
        ws_kas       = sh.worksheet("KAS")
        ws_stok      = sh.worksheet("STOK")

        tgl    = data.get("tanggal", "")
        nama   = data.get("nama", "")
        tipe   = (data.get("tipe") or "").upper()
        kas    = data.get("kas", "")
        items  = data.get("items", [])
        es     = data.get("es_balok") or 0
        total  = data.get("total_nota") or 0
        notes  = data.get("side_notes") or ""

        # ── OPERASI 1: TRANSAKSI ─────────────────────────────────────────────
        transaksi_rows = []

        for item in items:
            kode   = (item.get("jenis_kode") or "").upper()
            berat  = item.get("berat") or 0
            ukuran = item.get("ukuran") or ""
            harga  = item.get("harga") or 0
            jumlah = item.get("jumlah_nota") or 0

            kas_keluar = jumlah if kas == "keluar" else ""
            kas_masuk  = jumlah if kas == "masuk"  else ""

            if kas == "keluar":
                stok_delta = berat       # masuk peti
            elif kas == "masuk":
                stok_delta = -berat      # keluar jual
            elif tipe == "MERAH-PACKING":
                stok_delta = -berat      # keluar packing
            else:
                stok_delta = ""

            transaksi_rows.append([
                tgl, nama, tipe, kode,
                berat, ukuran, harga, jumlah,
                kas_keluar, kas_masuk,
                stok_delta, notes
            ])

        # Baris es balok (jika ada)
        if es:
            transaksi_rows.append([
                tgl, nama, "ES BALOK", "ES",
                "", "", "", es,
                es, "", "", ""
            ])

        if transaksi_rows:
            ws_transaksi.append_rows(transaksi_rows, value_input_option="USER_ENTERED")

        # ── OPERASI 2: KAS ───────────────────────────────────────────────────
        if kas in ("keluar", "masuk"):
            kas_keluar_total = total if kas == "keluar" else ""
            kas_masuk_total  = total if kas == "masuk"  else ""

            # Cari baris terakhir untuk formula saldo
            last_row = len(ws_kas.get_all_values()) + 1
            net_formula    = f"=C{last_row}-B{last_row}"
            saldo_formula  = f"=E{last_row-1}+D{last_row}"

            ws_kas.append_row([
                tgl,
                kas_keluar_total,
                kas_masuk_total,
                net_formula,
                saldo_formula,
                nama
            ], value_input_option="USER_ENTERED")

        # ── OPERASI 3: STOK ──────────────────────────────────────────────────
        # Baca nilai B:D baris 2–7 (6 jenis udang)
        stok_range = ws_stok.get("B2:D7")

        # Pastikan ada 6 baris
        while len(stok_range) < 6:
            stok_range.append([0, 0, 0])

        # Normalisasi ke float
        stok = []
        for row in stok_range:
            stok.append([
                float(row[0]) if len(row) > 0 and row[0] != "" else 0,
                float(row[1]) if len(row) > 1 and row[1] != "" else 0,
                float(row[2]) if len(row) > 2 and row[2] != "" else 0,
            ])

        # Tambahkan berat per item ke kolom yang tepat
        for item in items:
            kode  = (item.get("jenis_kode") or "").upper()
            berat = item.get("berat") or 0

            if kode not in JENIS_ROW:
                continue

            idx = JENIS_ROW[kode] - 2  # 0-indexed

            if kas == "keluar":
                stok[idx][0] += berat      # KG MASUK
            elif kas == "masuk":
                stok[idx][1] += berat      # KG KELUAR JUAL
            elif tipe == "MERAH-PACKING":
                stok[idx][2] += berat      # KG KELUAR PACKING

        # Tulis balik
        ws_stok.update("B2:D7", stok, value_input_option="USER_ENTERED")

        return {"status": "ok"}

    except Exception as e:
        return {"status": "error", "error": str(e)}
