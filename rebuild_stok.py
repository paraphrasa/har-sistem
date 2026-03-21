"""
rebuild_stok.py — Rekonstruksi tab STOK dari data TRANSAKSI

Jalankan sekali:
  python rebuild_stok.py
"""

import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1vuGQFh0qzZi4dL5WfhP6tIjNsXUZeNY5o8hHzL-lvAM"

JENIS_DENGAN_UKURAN = {"T", "HO", "PT"}
JENIS_NAMA = {
    "T":   "Tiger (T)",
    "HO":  "Tiger Head On (HO)",
    "PT":  "Pink Tambak (PT)",
    "W":   "White (W)",
    "BR":  "Brown (BR)",
    "WHO": "White Head On (WHO)",
}

def get_sheet():
    json_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "./credentials.json")
    creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SPREADSHEET_ID)

def parse_rp(val):
    """Parse 'Rp 371.000' atau '371000' atau '' ke float."""
    if not val:
        return 0.0
    val = str(val).replace("Rp", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(val)
    except:
        return 0.0

def parse_float(val):
    if not val:
        return 0.0
    try:
        return float(str(val).replace(",", "."))
    except:
        return 0.0

def rebuild():
    sh    = get_sheet()
    ws_t  = sh.worksheet("TRANSAKSI")
    ws_s  = sh.worksheet("STOK")

    rows = ws_t.get_all_values()
    if not rows:
        print("TRANSAKSI kosong.")
        return

    header = rows[0]
    print(f"Header TRANSAKSI: {header}")
    print(f"Total baris data: {len(rows)-1}")
    print()

    # Mapping kolom
    try:
        col_tipe   = header.index("TIPE NOTA")
        col_jenis  = header.index("JENIS")
        col_kg     = header.index("KG")
        col_ukuran = header.index("UKURAN")
        col_kas_k  = header.index("KAS KELUAR (Rp)")
        col_kas_m  = header.index("KAS MASUK (Rp)")
    except ValueError as e:
        print(f"Kolom tidak ditemukan: {e}")
        print("Header yang ada:", header)
        return

    # Akumulasi stok
    # stok[label] = [kg_masuk, kg_keluar_jual, kg_keluar_packing]
    stok = {}

    def add_stok(label, col_idx, berat):
        if label not in stok:
            stok[label] = [0.0, 0.0, 0.0]
        stok[label][col_idx] += berat

    for i, row in enumerate(rows[1:], start=2):
        # Skip baris total dan es balok
        tipe = row[col_tipe] if len(row) > col_tipe else ""
        if tipe in ("— TOTAL —", "ES BALOK", ""):
            continue

        kode   = (row[col_jenis] if len(row) > col_jenis else "").upper()
        berat  = parse_float(row[col_kg] if len(row) > col_kg else "")
        ukuran = row[col_ukuran] if len(row) > col_ukuran else ""
        kas_k  = parse_rp(row[col_kas_k] if len(row) > col_kas_k else "")
        kas_m  = parse_rp(row[col_kas_m] if len(row) > col_kas_m else "")

        if not kode or kode == "ES" or berat == 0:
            continue

        # Tentukan kolom stok
        if kas_k > 0:
            col = 0   # KG MASUK
        elif kas_m > 0:
            col = 1   # KG KELUAR JUAL
        elif tipe.upper() == "MERAH-PACKING":
            col = 2   # KG KELUAR PACKING
        else:
            continue

        nama_jenis = JENIS_NAMA.get(kode, kode)

        if kode in JENIS_DENGAN_UKURAN:
            ukuran_label = ukuran if ukuran else "?"
            label_ukuran = f"{nama_jenis} — ukuran {ukuran_label}"
            label_total  = f"{nama_jenis} — TOTAL"
            add_stok(label_ukuran, col, berat)
            add_stok(label_total,  col, berat)
        else:
            add_stok(nama_jenis, col, berat)

    print("Rekap stok dari TRANSAKSI:")
    for label, vals in sorted(stok.items()):
        print(f"  {label}: masuk={vals[0]:.2f} jual={vals[1]:.2f} packing={vals[2]:.2f}")
    print()

    # Tulis ke STOK
    # Baca semua baris STOK untuk cari label
    stok_rows = ws_s.get_all_values()
    stok_header = stok_rows[0] if stok_rows else []

    updates = []
    for i, row in enumerate(stok_rows[1:], start=2):
        label = row[0] if row else ""
        if label in stok:
            vals = stok[label]
            aktual = vals[0] - vals[1] - vals[2]
            updates.append({
                "range": f"B{i}:E{i}",
                "values": [[
                    round(vals[0], 3),
                    round(vals[1], 3),
                    round(vals[2], 3),
                    f"=B{i}-C{i}-D{i}"
                ]]
            })
            print(f"Update baris {i}: {label} → {vals}")

    if updates:
        ws_s.batch_update(updates, value_input_option="USER_ENTERED")
        print(f"\n✓ {len(updates)} baris STOK diupdate")
    else:
        print("Tidak ada baris STOK yang cocok dengan data TRANSAKSI.")
        print("Pastikan tab STOK sudah di-setup dengan struktur yang benar.")

if __name__ == "__main__":
    rebuild()
