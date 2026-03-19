"""
sheets.py — Tulis data nota ke Google Sheets HAR

3 operasi per konfirmasi:
  1. Append ke TRANSAKSI (satu baris per item + baris total)
  2. Append ke KAS (satu baris per nota)
  3. Update STOK (per jenis + per ukuran untuk T, HO, PT)
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Jenis tanpa ukuran — satu baris di STOK
JENIS_TANPA_UKURAN = {
    "W":   "White (W)",
    "BR":  "Brown (BR)",
    "WHO": "White Head On (WHO)",
}

# Jenis dengan ukuran — dipecah per ukuran di STOK
JENIS_DENGAN_UKURAN = {
    "T":  ("Tiger", 20, 70, 10),    # (nama, min, max, step)
    "HO": ("Tiger Head On", 20, 70, 10),
    "PT": ("Pink Tambak", 120, 500, 20),
}

_spreadsheet = None

def get_sheet():
    global _spreadsheet
    if _spreadsheet is None:
        json_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "./credentials.json")
        json_str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if json_str:
            import json, tempfile
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            tmp.write(json_str)
            tmp.close()
            json_path = tmp.name

        creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
        import gspread
        gc = gspread.authorize(creds)
        sheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID")
        if not sheet_id:
            raise RuntimeError("GOOGLE_SHEETS_SPREADSHEET_ID tidak ditemukan")
        _spreadsheet = gc.open_by_key(sheet_id)
    return _spreadsheet


def fmt_rp(n):
    """Format angka sebagai Rp 1.234.567"""
    try:
        return "Rp " + f"{int(n):,}".replace(",", ".")
    except:
        return str(n)


def tulis(data: dict) -> dict:
    try:
        sh        = get_sheet()
        ws_t      = sh.worksheet("TRANSAKSI")
        ws_k      = sh.worksheet("KAS")
        ws_s      = sh.worksheet("STOK")

        tgl   = data.get("tanggal", "")
        nama  = data.get("nama", "")
        tipe  = (data.get("tipe") or "").upper()
        kas   = data.get("kas", "")
        items = data.get("items", [])
        es    = data.get("es_balok") or 0
        total = data.get("total_nota") or 0
        notes = data.get("side_notes") or ""

        # ── OPERASI 1: TRANSAKSI ─────────────────────────────────────────────
        transaksi_rows = []
        total_kg = 0

        for item in items:
            kode   = (item.get("jenis_kode") or "").upper()
            berat  = item.get("berat") or 0
            ukuran = item.get("ukuran") or ""
            harga  = item.get("harga") or 0
            jumlah = item.get("jumlah_nota") or 0

            kas_keluar = fmt_rp(jumlah) if kas == "keluar" else ""
            kas_masuk  = fmt_rp(jumlah) if kas == "masuk"  else ""

            if kas == "keluar":
                stok_delta = berat
            elif kas == "masuk":
                stok_delta = -berat
            elif tipe == "MERAH-PACKING":
                stok_delta = -berat
            else:
                stok_delta = ""

            transaksi_rows.append([
                tgl, nama, tipe, kode,
                berat, ukuran, fmt_rp(harga), fmt_rp(jumlah),
                kas_keluar, kas_masuk,
                stok_delta, notes
            ])
            total_kg += berat

        # Baris es balok
        if es:
            transaksi_rows.append([
                tgl, nama, "ES BALOK", "ES",
                "", "", "", fmt_rp(es),
                fmt_rp(es), "", "", ""
            ])

        # Baris TOTAL per nota
        total_kas_keluar = fmt_rp(total) if kas == "keluar" else ""
        total_kas_masuk  = fmt_rp(total) if kas == "masuk"  else ""
        transaksi_rows.append([
            "", "", "— TOTAL —", "",
            round(total_kg, 2), "", "", fmt_rp(total),
            total_kas_keluar, total_kas_masuk,
            "", ""
        ])

        if transaksi_rows:
            ws_t.append_rows(transaksi_rows, value_input_option="USER_ENTERED")

        # ── OPERASI 2: KAS ───────────────────────────────────────────────────
        if kas in ("keluar", "masuk"):
            last_row      = len(ws_k.get_all_values()) + 1
            net_formula   = f"=C{last_row}-B{last_row}"
            saldo_formula = f"=E{last_row-1}+D{last_row}"

            ws_k.append_row([
                tgl,
                fmt_rp(total) if kas == "keluar" else "",
                fmt_rp(total) if kas == "masuk"  else "",
                net_formula,
                saldo_formula,
                nama
            ], value_input_option="USER_ENTERED")

        # ── OPERASI 3: STOK ──────────────────────────────────────────────────
        # Baca semua data STOK
        stok_data = ws_s.get_all_values()  # list of rows

        def find_or_create_row(label):
            """Cari baris dengan label, return index (0-based). Buat baru jika tidak ada."""
            for i, row in enumerate(stok_data):
                if row and row[0] == label:
                    return i
            # Buat baris baru
            ws_s.append_row([label, 0, 0, 0, "", ""], value_input_option="USER_ENTERED")
            stok_data.append([label, "0", "0", "0", "", ""])
            return len(stok_data) - 1

        def update_stok_row(row_idx, col_idx, delta):
            """Tambahkan delta ke sel tertentu di STOK."""
            row_num = row_idx + 1  # 1-indexed untuk Sheets
            cell    = ws_s.cell(row_num, col_idx + 1)
            current = float(cell.value or 0)
            ws_s.update_cell(row_num, col_idx + 1, round(current + delta, 3))
            # Update formula stok aktual
            ws_s.update_cell(row_num, 5, f"=B{row_num}-C{row_num}-D{row_num}")

        for item in items:
            kode  = (item.get("jenis_kode") or "").upper()
            berat = item.get("berat") or 0
            ukuran = item.get("ukuran")

            # Tentukan kolom berdasarkan tipe transaksi
            if kas == "keluar":
                col = 1   # KG MASUK (col B, index 1)
            elif kas == "masuk":
                col = 2   # KG KELUAR JUAL (col C, index 2)
            elif tipe == "MERAH-PACKING":
                col = 3   # KG KELUAR PACKING (col D, index 3)
            else:
                continue

            if kode in JENIS_DENGAN_UKURAN:
                # Pecah per ukuran
                nama_jenis = JENIS_DENGAN_UKURAN[kode][0]
                ukuran_label = f"{ukuran}" if ukuran else "?"
                label = f"{nama_jenis} ({kode}) — ukuran {ukuran_label}"
                row_idx = find_or_create_row(label)
                update_stok_row(row_idx, col, berat)

                # Juga update total jenis
                label_total = f"{nama_jenis} ({kode}) — TOTAL"
                row_idx_total = find_or_create_row(label_total)
                update_stok_row(row_idx_total, col, berat)

            elif kode in JENIS_TANPA_UKURAN:
                label = JENIS_TANPA_UKURAN[kode]
                row_idx = find_or_create_row(label)
                update_stok_row(row_idx, col, berat)

        return {"status": "ok"}

    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e) + "\n" + traceback.format_exc()}
