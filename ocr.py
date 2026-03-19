"""
ocr.py — Modul inti OCR untuk HAR Jual Beli Udang
Mengirim foto nota ke Claude API dan memvalidasi hasilnya.
"""

import os
import json
import base64
import anthropic

# ── Client ────────────────────────────────────────────────────────────────────

_client = None

def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY tidak ditemukan di environment")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
Kamu adalah sistem pencatat nota untuk HAR Jual Beli Udang, Muara Badak.

JENIS UDANG:
T=Tiger(ukuran 20-70 ekor/kg, wajib ada ukuran)
W=White(tidak pakai ukuran)
BR=Brown(tidak pakai ukuran)
HO=Tiger Head On(ukuran 20-70, wajib ada ukuran)
WHO=White Head On(tidak pakai ukuran)
PT=Pink Tambak(ukuran 120-500 ekor/kg, wajib ada ukuran)

TIPE NOTA - deteksi dari warna kertas dan label:
PUTIH = HAR beli dari supplier/petambak, kas keluar, stok masuk peti fiber
MERAH label JUAL = HAR jual eceran/pengepul kecil, kas masuk, stok keluar
MERAH label PACKING = kemas untuk trip ke pabrik, bukan kas, stok keluar

SUPPLIER:
Besar (harga lebih tinggi): Bakri, Dahlan, Manna
Petambak biasa (harga lebih rendah): semua nama lain
Perbedaan harga antar supplier = NORMAL, jangan flag

RULES BACA NOTA:
- Jenis udang kosong di baris berikutnya = inherit dari baris sebelumnya
  dalam nota SAMA saja, jangan inherit dari nota berbeda
- Semua baris jenis kosong = flag konfirmasi jenis
- Tanggal sering terbalik DD/MM vs MM/DD = flag jika tidak masuk akal
- Digit 850 sering terbaca 800 = selalu hitung ulang 3 digit terakhir
- ES = Es Balok, bukan jenis udang, ini potongan dari total pembayaran
- Catatan timbang angka-angka di tepi nota = simpan sebagai side_notes
- Semakin kecil angka ukuran = udang lebih besar = harga lebih mahal

FORMAT HARGA DAN JUMLAH (SANGAT PENTING):
- Harga di nota ditulis dalam ribuan tanpa angka nol
  contoh: tertulis 206 maka harga = 206000 (Rp 206.000)
  contoh: tertulis 145 maka harga = 145000 (Rp 145.000)
- Jumlah (hasil perkalian) ditulis nilai ASLI penuh
  contoh: tertulis 113.300 maka jumlah_nota = 113300
- Verifikasi: berat x (angka_harga x 1000) = jumlah_nota
  contoh: 0.55 x 206000 = 113300
- Simpan harga di JSON sudah dalam nilai penuh (sudah dikali 1000)
  contoh: harga = 206000 BUKAN 206

FLAG HANYA jika:
- berat x harga tidak sama dengan jumlah di nota
- ukuran di luar range jenis
- jenis tidak dikenal
- total tidak cocok

RETURN JSON ONLY, tidak ada markdown, tidak ada penjelasan lain:
{
  "tipe": "putih|merah-jual|merah-packing",
  "kas": "keluar|masuk|tidak ada",
  "nama": "",
  "tanggal": "DD Bulan YYYY",
  "no_nota": "",
  "items": [
    {
      "no": 1,
      "jenis_kode": "T",
      "jenis_nama": "Tiger",
      "berat": 2.7,
      "ukuran": 20,
      "harga": 232,
      "jumlah_nota": 626400,
      "jumlah_hitung": 626400,
      "status": "ok"
    }
  ],
  "es_balok": null,
  "subtotal_nota": 0,
  "subtotal_hitung": 0,
  "total_nota": 0,
  "total_hitung": 0,
  "total_status": "ok|selisih",
  "selisih": 0,
  "flags": [],
  "side_notes": ""
}
""".strip()

# ── Validasi lokal (lapis kedua setelah Claude) ───────────────────────────────

UKURAN_RANGE = {
    "T":   (20, 70),
    "HO":  (20, 70),
    "PT":  (120, 500),
}

JENIS_VALID = {"T", "W", "BR", "HO", "WHO", "PT"}


def validasi_item(item: dict) -> list[str]:
    """Kembalikan daftar flag untuk satu line item."""
    flags = []
    kode  = item.get("jenis_kode", "").upper()
    berat = item.get("berat", 0) or 0
    harga = item.get("harga", 0) or 0
    ukuran = item.get("ukuran")
    jumlah_nota   = item.get("jumlah_nota", 0) or 0
    jumlah_hitung = round(berat * harga)

    # Update jumlah_hitung hasil hitung ulang
    item["jumlah_hitung"] = jumlah_hitung

    # 1. Jenis tidak dikenal
    if kode and kode not in JENIS_VALID:
        flags.append(f"Baris {item.get('no')}: jenis '{kode}' tidak dikenal")
        item["status"] = "flag"

    # 2. Verifikasi kalkulasi
    if jumlah_nota and abs(jumlah_nota - jumlah_hitung) > 1:
        selisih = jumlah_nota - jumlah_hitung
        flags.append(
            f"Baris {item.get('no')}: {berat} × {harga} = {jumlah_hitung:,} "
            f"≠ {jumlah_nota:,} di nota (selisih {selisih:+,})"
        )
        item["status"] = "mismatch"
    elif item.get("status") != "flag":
        item["status"] = "ok"

    # 3. Ukuran di luar range
    if kode in UKURAN_RANGE and ukuran is not None:
        lo, hi = UKURAN_RANGE[kode]
        if not (lo <= ukuran <= hi):
            flags.append(
                f"Baris {item.get('no')}: ukuran {ukuran} di luar range {kode} "
                f"({lo}–{hi} ekor/kg)"
            )
            item["status"] = "flag"

    # 4. Ukuran wajib tapi kosong
    if kode in UKURAN_RANGE and ukuran is None:
        flags.append(f"Baris {item.get('no')}: ukuran wajib untuk jenis {kode} tapi kosong")
        item["status"] = "flag"

    return flags


def validasi_nota(data: dict) -> dict:
    """
    Jalankan validasi lokal di atas hasil Claude.
    Tambah/perbarui flags, status item, dan total_status.
    """
    extra_flags: list[str] = []

    # Validasi per item
    for item in data.get("items", []):
        extra_flags.extend(validasi_item(item))

    # Hitung ulang total
    subtotal_hitung = sum(
        (i.get("jumlah_hitung") or 0) for i in data.get("items", [])
    )
    es = data.get("es_balok") or 0
    total_hitung = subtotal_hitung - es

    data["subtotal_hitung"] = subtotal_hitung
    data["total_hitung"]    = total_hitung
    data["selisih"]         = (data.get("total_nota") or 0) - total_hitung

    if abs(data["selisih"]) > 1:
        data["total_status"] = "selisih"
        extra_flags.append(
            f"Total nota {data.get('total_nota', 0):,} ≠ total hitung {total_hitung:,} "
            f"(selisih {data['selisih']:+,})"
        )
    else:
        data["total_status"] = "ok"

    # Gabungkan flags dari Claude + validasi lokal (hindari duplikat)
    existing = set(data.get("flags", []))
    for f in extra_flags:
        if f not in existing:
            existing.add(f)
    data["flags"] = list(existing)

    return data

# ── Main function ─────────────────────────────────────────────────────────────

def proses_nota(image_bytes: bytes, media_type: str) -> dict:
    """
    Kirim gambar ke Claude, parse JSON, jalankan validasi lokal.
    Selalu return dict (tidak raise ke caller).
    """
    try:
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")

        response = get_client().messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Baca nota ini dan kembalikan JSON sesuai format.",
                        },
                    ],
                }
            ],
        )

        raw_text = response.content[0].text.strip()

        # Strip markdown fences jika ada
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1]
            if raw_text.endswith("```"):
                raw_text = raw_text[: raw_text.rfind("```")]

        data = json.loads(raw_text)

        # Jalankan validasi lokal
        data = validasi_nota(data)
        data["ocr_status"] = "success"
        return data

    except json.JSONDecodeError as e:
        return {
            "ocr_status": "error",
            "error": f"Claude tidak mengembalikan JSON valid: {str(e)}",
            "raw": raw_text if "raw_text" in dir() else "",
        }

    except anthropic.APIError as e:
        return {
            "ocr_status": "error",
            "error": f"Anthropic API error: {str(e)}",
        }

    except Exception as e:
        return {
            "ocr_status": "error",
            "error": f"Error tidak terduga: {str(e)}",
        }
