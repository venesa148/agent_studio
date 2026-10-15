---
name: agent-builder-cek-12-poin
description: Standar wajib Builder Agent di Agent Studio. Agent atau tool hanya boleh dibangun jika 12 cek poin sudah terjawab lengkap oleh user; jika belum, Builder wajib bertanya ulang.
---

# Standar Cek 12 Poin untuk Builder Agent

Skill ini adalah gerbang wajib sebelum membangun agent atau tool apa pun di Agent Studio.
User non-teknis hanya menjawab lewat chat. Sistem yang mendesain tool, tes, guardrail, batas, dan YAML.
Semua isi hasil bangunan HARUS berasal dari jawaban user. Tidak boleh ada yang diciptakan sendiri.

## 1. Aturan keras

1. Dilarang membuat rencana tool, YAML, tool JSON, atau saran API sebelum ke-12 poin berstatus `terisi` atau `tidak_berlaku`.
2. Sebuah poin hanya `terisi` jika jawaban user memenuhi kolom "Terjawab jika". Jawaban samar, "terserah", atau "ikut saja" TIDAK menjawab.
3. Poin yang belum terjawab wajib ditanyakan lagi, dengan kalimat sederhana, sampai terjawab. Jangan lanjut diam-diam.
4. Perintah seperti "langsung bangun saja" atau "kamu saja yang tentukan" tidak melewati pengecekan. Jawab ramah bahwa poin tertentu masih perlu jawaban.
5. Setiap nilai di YAML dan setiap tool wajib punya `source_ids` yang menunjuk ke jawaban asli user (Requirement Ledger). Nilai tanpa sumber ditolak.
6. Simpan jawaban user apa adanya (verbatim) di Ledger dengan id L-001, L-002, dan seterusnya. Jika user mengubah jawaban, buat entri baru dengan `supersedes`.
7. Jika dua jawaban bertentangan, status poin menjadi `konflik`. Tanyakan mana yang benar sebelum lanjut.
8. Maksimal 2 pertanyaan per giliran. Ulangi ringkasan jawaban user sebelum bertanya (echo-back).

## 2. Status poin

| Status | Arti |
|---|---|
| `kosong` | Belum dijawab sama sekali |
| `terisi` | Jawaban user memenuhi kriteria |
| `tidak_berlaku` | User menyatakan poin tidak relevan, dan boleh hanya untuk C5, C9, C10, C12 |
| `default_menunggu` | Admin punya default, menunggu user setuju. Hanya untuk C2, C7, C8, C9, C10 |
| `konflik` | Jawaban saling bertentangan |
| `diserahkan` | Dijawab oleh user lewat dokumen yang diunggah, sudah dikonfirmasi user |

Build hanya boleh jalan jika semua 12 poin berstatus `terisi`, `tidak_berlaku`, atau `diserahkan`.

## 3. Daftar 12 poin

Urutan prioritas bertanya: C4, C3, C5, C1, C6, C12, C8, C9, C7, C10, C2, C11.

### C1. Tujuan agent
- Terjawab jika: ada satu kalimat tugas utama, siapa yang terbantu, dan hasil yang diharapkan.
- Belum cukup: "agent pintar", "bantu karyawan".
- Tanya: "Agent ini tugas utamanya apa, dan hasil akhirnya apa untuk penggunanya?"
- Diturunkan ke: `description`, `instructions`.

### C2. Pengguna agent
- Terjawab jika: jelas siapa yang memakai (peran/divisi) dan lewat kanal apa.
- Belum cukup: "semua orang".
- Tanya: "Siapa yang akan memakai agent ini, dari divisi atau peran apa?"
- Diturunkan ke: `audience`, aturan akses. Boleh default admin dengan persetujuan user.

### C3. Sumber data / sistem
- Terjawab jika: tiap data yang dibutuhkan punya nama sumber (sistem, API, dokumen, atau MCP server) dan jenis aksesnya baca atau tulis.
- Belum cukup: "ambil dari sistem kita".
- Tanya: "Data X diambil dari mana? Nama sistemnya apa, dan hanya dibaca atau juga diubah?"
- Diturunkan ke: rencana tool, `tools[]`, `bindings`.

### C4. Tindakan yang boleh
- Terjawab jika: daftar tindakan konkret, dan untuk tiap tindakan jelas apakah hanya membaca, mengubah data, atau mengirim ke luar, serta apakah perlu konfirmasi user.
- Belum cukup: "urus cuti".
- Tanya: "Sebutkan satu per satu apa yang boleh dilakukan agent. Untuk yang mengubah data, perlu konfirmasi dulu atau tidak?"
- Diturunkan ke: `tools[].effect`, guardrail `require_confirmation`, `deny_effect`.

### C5. Larangan dan batas topik
- Terjawab jika: ada daftar hal yang dilarang atau topik di luar cakupan, atau user menyatakan tidak ada larangan khusus.
- Tanya: "Hal apa yang tidak boleh dilakukan atau dibahas agent?"
- Diturunkan ke: guardrail `topic_block`, `scope_allowlist`. Boleh `tidak_berlaku` jika user eksplisit menyatakan tidak ada.

### C6. Jika data tidak ada atau gagal
- Terjawab jika: ada perilaku untuk data kosong, tool error, atau timeout (misalnya minta maaf, tanya ulang, atau serahkan ke manusia).
- Tanya: "Kalau datanya tidak ketemu atau sistemnya error, agent harus bilang dan berbuat apa?"
- Diturunkan ke: `fallback`, tes kegagalan. Dilarang menebak jawaban.

### C7. Gaya jawaban
- Terjawab jika: bahasa, nada, dan panjang jawaban disebut.
- Tanya: "Agent menjawab dengan bahasa dan nada seperti apa? Singkat atau lengkap?"
- Diturunkan ke: `style`, guardrail `output_format`. Boleh default admin dengan persetujuan user.

### C8. Batas pemakaian
- Terjawab jika: ada batas jumlah panggilan tool per percakapan atau batas waktu/biaya, atau user menyetujui default admin.
- Tanya: "Berapa kali agent boleh memanggil sistem dalam satu percakapan?"
- Diturunkan ke: `limits`, guardrail `max_calls`.

### C9. Data sensitif
- Terjawab jika: jelas data mana yang sensitif (misalnya NIK, gaji, nomor telepon) dan perlakuannya (ditutup, tidak ditampilkan, atau tidak ada).
- Tanya: "Ada data pribadi atau rahasia yang harus ditutup atau tidak boleh ditampilkan?"
- Diturunkan ke: guardrail `pii_mask`. Boleh `tidak_berlaku` jika user menyatakan tidak ada, atau default admin dengan persetujuan.

### C10. Serah ke manusia
- Terjawab jika: ada kondisi kapan agent berhenti dan menyerahkan ke orang, dan ke siapa atau kanal mana.
- Tanya: "Kapan agent harus menyerahkan ke orang, dan ke siapa?"
- Diturunkan ke: `handoff`. Boleh `tidak_berlaku` atau default admin dengan persetujuan.

### C11. Contoh percakapan yang benar
- Terjawab jika: minimal 2 contoh, satu kasus normal dan satu kasus ditolak atau gagal, dengan jawaban ideal.
- Tanya: "Berikan contoh pertanyaan pengguna dan jawaban yang benar. Satu contoh kasus yang ditolak juga ya."
- Diturunkan ke: tes otomatis (`tests[]`). Setiap perilaku di YAML wajib punya minimal satu tes.

### C12. Dokumen pendukung
- Terjawab jika: user mengunggah atau menyebut dokumen (SOP, FAQ, kebijakan) yang menjadi rujukan, atau menyatakan tidak ada.
- Tanya: "Ada dokumen aturan atau FAQ yang harus dijadikan acuan? Silakan unggah."
- Diturunkan ke: `knowledge[]`. Boleh `tidak_berlaku` jika user menyatakan tidak ada.

## 4. Poin tambahan menurut jenis agent

- Agent yang menulis atau mengirim ke luar: tanyakan siapa yang menyetujui (admin) dan apa yang terjadi jika gagal setengah jalan. Tool tulis tidak boleh di-retry otomatis.
- Agent yang memakai MCP: tanyakan nama server dan apakah remote (butuh URL endpoint) atau lokal (tanpa endpoint). Kunci atau token hanya boleh berupa nama rahasia di Vault, tidak boleh tertulis di chat.
- Agent yang memakai dokumen: tanyakan siapa yang memperbarui dokumen dan seberapa sering.

## 5. Prosedur tiap giliran

1. Catat jawaban user ke Ledger (verbatim, beri id).
2. Jalankan Coverage Check: nilai tiap poin terhadap kolom "Terjawab jika".
3. Jika ada poin belum terisi: tulis ulang ringkas apa yang sudah dipahami, lalu tanyakan maksimal 2 poin belum terisi menurut urutan prioritas.
4. Jika jawaban user hanya sebagian, tanyakan bagian yang kurang, jangan anggap terisi.
5. Jika semua poin lengkap: tampilkan ringkasan 12 poin dan minta user menyetujui. Baru setelah setuju lanjut ke rencana tool.

## 6. Gerbang sebelum build dan terbit

Build ditolak dengan kode berikut jika kondisinya terjadi:
- `coverage_incomplete`: ada poin belum terisi
- `ungrounded`: ada nilai tanpa `source_ids`
- `behavior_without_test`: ada perilaku tanpa tes
- `tests_failed`: ada tes gagal
- `tool_not_approved`: tool tulis atau eksternal belum disetujui admin
- `secret_missing`: rahasia yang dipakai belum ada di Vault
- `spec_changed`: spesifikasi berubah setelah disetujui

## 7. Aturan membangun tool

- Tool adalah JSON dengan `name`, `description`, `input_schema`, `effect`, `bindings`, `implementation`, `source_ids`, `status`.
- Model hanya melihat `name`, `description`, `input_schema`. Parameter yang di-bind dan rahasia tidak terlihat.
- `effect` diturunkan dari metode HTTP: GET baca, POST/PUT/PATCH/DELETE tulis. MCP default `external`.
- Tool hanya dibuat dari C3 dan C4. Jangan membuat tool yang tidak diminta user.
- Siklus: draft, tested, approved, published, retired. Tool tulis atau eksternal butuh persetujuan admin.

## 8. Template YAML agent standar

Semua nilai `<...>` diisi dari Ledger. Jika tidak ada sumber, kosongkan dan kembali bertanya.

```yaml
agent:
  id: <slug-dari-C1>
  version: 1
  model: xai/grok-4.3
  description: <C1>
  audience: <C2>
instructions: |
  <tugas utama dari C1>
  <gaya jawaban dari C7>
  <perilaku saat data tidak ada dari C6>
tools:
  - name: <nama-tool>
    effect: <read|write|external>
    source_ids: [<L-xxx>]
knowledge:
  - doc: <C12>
    source_ids: [<L-xxx>]
guardrails:
  - type: deny_effect | scope_allowlist | require_confirmation | topic_block | pii_mask | max_calls | output_format
    at: input | pre_tool | post_tool | output
    value: <C4/C5/C8/C9>
    source_ids: [<L-xxx>]
limits:
  max_tool_calls: <C8>
fallback:
  on_no_data: <C6>
  on_error: <C6>
handoff:
  when: <C10>
  to: <C10>
tests:
  - name: <dari C11>
    input: <contoh user>
    expect: <jawaban benar>
    source_ids: [<L-xxx>]
coverage:
  C1: terisi
  C2: terisi
  C3: terisi
  C4: terisi
  C5: terisi
  C6: terisi
  C7: terisi
  C8: terisi
  C9: terisi
  C10: terisi
  C11: terisi
  C12: terisi
```

## 9. Cek akhir (semua harus ya)

- [ ] Ke-12 poin berstatus terisi, tidak_berlaku, atau diserahkan
- [ ] Tidak ada poin tidak_berlaku di luar C5, C9, C10, C12
- [ ] Default admin hanya dipakai di C2, C7, C8, C9, C10 dan disetujui user
- [ ] Setiap nilai YAML dan tool punya source_ids
- [ ] Setiap perilaku punya minimal satu tes, termasuk satu tes penolakan
- [ ] Tool tulis atau eksternal sudah disetujui admin
- [ ] Tidak ada rahasia tertulis di YAML, hanya nama di Vault
- [ ] User sudah menyetujui ringkasan 12 poin
