"use strict";
// Language: English (default) or Bahasa Melayu. The choice is kept in this browser only. Loaded before app.js.
// t(text, vars): the page's own text. The key is the English text; {name} parts are filled from vars.
// tm(text): a message from the server (finished English sentences, some kept in files from earlier), translated by
// exact match or by the patterns below; anything not listed is shown in English rather than half-translated.
// Labels copied from Million Payroll's Edit Payroll screen stay in English on purpose, so they match that program.

const LANG = (() => { try { return localStorage.getItem("lang") === "ms" ? "ms" : "en"; } catch (_) { return "en"; } })();
document.documentElement.lang = LANG;
const LOCALE = LANG === "ms" ? "ms-MY" : undefined;

const MS = {
  // ---- page (index.html)
  "Checking Claude…": "Menyemak Claude…",
  "Payroll": "Gaji",
  "Quit Table Reader": "Tutup Table Reader",
  "Close Table Reader on this computer": "Tutup Table Reader pada komputer ini",
  "Choose files to read": "Pilih fail untuk dibaca",
  "Drop scans or photos here": "Letakkan imbasan atau foto di sini",
  "PDF, JPG or PNG — or": "PDF, JPG atau PNG — atau",
  "click to choose files": "klik untuk memilih fail",
  "Recent files": "Fail terkini",
  "Nothing here yet. Add a file above to get started.": "Belum ada apa-apa di sini. Tambah fail di atas untuk bermula.",
  "No files for this company. Choose “All companies” to see every file.": "Tiada fail untuk syarikat ini. Pilih “Semua syarikat” untuk melihat semua fail.",
  "← All files": "← Semua fail",
  "Cancel reading": "Batalkan bacaan",
  "Continue reading": "Teruskan bacaan",
  "Download CSV": "Muat turun CSV",
  "Payroll for Million Payroll": "Gaji untuk Million Payroll",
  "Download payroll CSV": "Muat turun CSV gaji",
  "Pick the month and mark the days, add each employee and tick their time-card files. Table Reader adds up days worked and overtime from the cells you have already checked. Anything it cannot work out is listed, never guessed, and you can type over any figure.":
    "Pilih bulan dan tandakan hari, tambah setiap pekerja dan tandakan fail kad perakam waktu mereka. Table Reader mengira hari bekerja dan kerja lebih masa daripada sel yang telah anda semak. Apa-apa yang tidak dapat dikira akan disenaraikan, tidak sekali-kali diteka, dan anda boleh menaip semula mana-mana angka.",
  "1. Month and days": "1. Bulan dan hari",
  "2. Employees and their time cards": "2. Pekerja dan kad perakam waktu mereka",
  "Add employee": "Tambah pekerja",
  "3. Results": "3. Keputusan",
  "Change the language": "Tukar bahasa",

  // ---- app.js
  "Clear": "Jelas", "Mostly clear": "Kebanyakannya jelas", "Faded or small print": "Pudar atau tulisan kecil", "Hard to read": "Sukar dibaca",
  "Table Reader is not running any more. Close this tab and open Table Reader again.": "Table Reader tidak berjalan lagi. Tutup tab ini dan buka Table Reader semula.",
  "Table Reader was updated while it was open. Close its window, open Table Reader again, then reload this page.": "Table Reader telah dikemas kini semasa ia dibuka. Tutup tetingkapnya, buka Table Reader semula, kemudian muat semula halaman ini.",
  "Something went wrong. Reload the page and try again.": "Berlaku masalah. Muat semula halaman dan cuba lagi.",
  "✓ Claude connected": "✓ Claude disambungkan",
  "Claude is not connected.": "Claude tidak disambungkan.",
  "Sign in": "Log masuk",
  "Finish signing in in the browser window that just opened…": "Selesaikan log masuk dalam tetingkap pelayar yang baru dibuka…",
  "Connect your Claude account first (top right), then add your files.": "Sambungkan akaun Claude anda dahulu (atas kanan), kemudian tambah fail anda.",
  "Adding {n} file…": "Menambah {n} fail…", "Adding {n} files…": "Menambah {n} fail…",
  "Waiting…": "Menunggu…",
  "Reading page {a} of {b}…": "Membaca halaman {a} daripada {b}…",
  "Preparing…": "Menyediakan…",
  "Finished": "Selesai",
  "Stopped": "Berhenti",
  "Cancelled": "Dibatalkan",
  "Cancel": "Batal",
  "Open": "Buka",
  "Save": "Simpan",
  "Company": "Syarikat",
  "Company name": "Nama syarikat",
  "Company for {name}": "Syarikat untuk {name}",
  "Set company": "Tetapkan syarikat",
  "Click to change the company": "Klik untuk menukar syarikat",
  "Choose the client company of this file": "Pilih syarikat pelanggan bagi fail ini",
  "Check the name. Other files that start with it will go under it too.": "Semak nama ini. Fail lain yang bermula dengannya juga akan diletakkan di bawahnya.",
  "{n} other file starting with “{c}” was put under this company too.": "{n} fail lain yang bermula dengan “{c}” juga diletakkan di bawah syarikat ini.",
  "{n} other files starting with “{c}” were put under this company too.": "{n} fail lain yang bermula dengan “{c}” juga diletakkan di bawah syarikat ini.",
  "Show files of": "Tunjukkan fail bagi",
  "All companies ({n})": "Semua syarikat ({n})",
  "No company yet ({n})": "Belum ada syarikat ({n})",
  "All companies": "Semua syarikat",
  "No company yet": "Belum ada syarikat",
  "Claude was not sure about this cell.": "Claude tidak pasti tentang sel ini.",
  "Cell to check. Type the correct value.": "Sel untuk disemak. Taip nilai yang betul.",
  "Cell value": "Nilai sel",
  "Please check this cell.": "Sila semak sel ini.",
  "Claude saw: {x}": "Claude nampak: {x}",
  "Use this": "Guna ini",
  "It's empty": "Ia kosong",
  "Undo my change": "Buat asal perubahan saya",
  "Page {a} of {b}": "Halaman {a} daripada {b}",
  "Picture quality: {q}. Check the highlighted cells carefully.": "Kualiti gambar: {q}. Semak sel yang ditandakan dengan teliti.",
  "Claude's notes": "Catatan Claude",
  "No table was found on this page.": "Tiada jadual dijumpai pada halaman ini.",
  "Original, page {n}": "Asal, halaman {n}",
  "Click the picture to open it larger.": "Klik gambar untuk membukanya dengan lebih besar.",
  "Waiting for the other files to finish…": "Menunggu fail lain selesai…",
  "Reading page {a} of {b}… This takes about a minute per page. You can keep this window open and add more files.":
    "Membaca halaman {a} daripada {b}… Ini mengambil masa kira-kira seminit bagi setiap halaman. Anda boleh biarkan tetingkap ini terbuka dan tambah lebih banyak fail.",
  "Preparing the pages…": "Menyediakan halaman…",
  "Finished, but no table could be read from this file. See the message below the picture.": "Selesai, tetapi tiada jadual dapat dibaca daripada fail ini. Lihat mesej di bawah gambar.",
  "Finished. {n} cell to check — highlighted in yellow. Type the correct value, or use Claude's suggestion.": "Selesai. {n} sel perlu disemak — ditandakan kuning. Taip nilai yang betul, atau guna cadangan Claude.",
  "Finished. {n} cells to check — highlighted in yellow. Type the correct value, or use Claude's suggestion.": "Selesai. {n} sel perlu disemak — ditandakan kuning. Taip nilai yang betul, atau guna cadangan Claude.",
  "Finished. Nothing was marked as unsure, but have a look before you rely on it.": "Selesai. Tiada apa-apa yang ditanda sebagai tidak pasti, tetapi semak dahulu sebelum anda bergantung padanya.",
  "Cancelled after {a} of {b} pages. Nothing more will be read unless you press Continue.": "Dibatalkan selepas {a} daripada {b} halaman. Tiada lagi yang akan dibaca melainkan anda tekan Teruskan.",
  "Stopped after {a} of {b} pages.": "Berhenti selepas {a} daripada {b} halaman.",
  "Stopped.": "Berhenti.",
  " Use “All files” to go back and add a corrected file.": " Guna “Semua fail” untuk kembali dan tambah fail yang telah dibetulkan.",
  "Go to next cell to check ({n})": "Pergi ke sel seterusnya untuk disemak ({n})",
  "Go to next cell to check": "Pergi ke sel seterusnya untuk disemak",
  "Opening…": "Membuka…",
  "{n} file is still being read. They will be stopped, and you can press Continue next time. ": "{n} fail masih dibaca. Bacaan akan dihentikan, dan anda boleh tekan Teruskan lain kali. ",
  "{n} files are still being read. They will be stopped, and you can press Continue next time. ": "{n} fail masih dibaca. Bacaan akan dihentikan, dan anda boleh tekan Teruskan lain kali. ",
  "Close Table Reader?": "Tutup Table Reader?",
  "Table Reader has closed.": "Table Reader telah ditutup.",
  "You can close this tab. To use it again, open Table Reader from your desktop.": "Anda boleh tutup tab ini. Untuk menggunakannya semula, buka Table Reader dari desktop anda.",
  "{n} cell is still highlighted. In the CSV they will be left blank with a note. Download anyway?": "{n} sel masih ditandakan. Dalam CSV, sel itu akan dibiarkan kosong dengan catatan. Muat turun juga?",
  "{n} cells are still highlighted. In the CSV they will be left blank with a note. Download anyway?": "{n} sel masih ditandakan. Dalam CSV, sel-sel itu akan dibiarkan kosong dengan catatan. Muat turun juga?",

  // ---- payroll.js (the planning parts; the Edit Payroll copy stays in English)
  "January": "Januari", "February": "Februari", "March": "Mac", "April": "April", "May": "Mei", "June": "Jun",
  "July": "Julai", "August": "Ogos", "September": "September", "October": "Oktober", "November": "November", "December": "Disember",
  "Sun": "Ahd", "Mon": "Isn", "Tue": "Sel", "Wed": "Rab", "Thu": "Kha", "Fri": "Jum", "Sat": "Sab",
  "Working day": "Hari bekerja", "Rest day": "Hari rehat", "Public holiday": "Cuti umum",
  "unclear: fix it in the document": "tidak jelas: betulkan dalam dokumen",
  "written twice, differs": "ditulis dua kali, berbeza",
  "no entry": "tiada catatan",
  "Saving…": "Menyimpan…", "Saved": "Disimpan", "Not saved": "Tidak disimpan",
  "Month": "Bulan", "Year": "Tahun",
  "Normal hours in a working day (overtime starts after this)": "Jam biasa dalam sehari bekerja (kerja lebih masa bermula selepas ini)",
  "Click a day to change it: working day → rest day → public holiday. Sundays start as rest days. Mark every public holiday of the month.":
    "Klik pada hari untuk menukarnya: hari bekerja → hari rehat → cuti umum. Hari Ahad ditetapkan sebagai hari rehat. Tandakan setiap cuti umum dalam bulan ini.",
  "Colours:": "Warna:",
  "white = working day": "putih = hari bekerja",
  "grey = rest day": "kelabu = hari rehat",
  "yellow = public holiday": "kuning = cuti umum",
  "{d}: {w} (click to change)": "{d}: {w} (klik untuk menukar)",
  "Day {d}, {w}. Click to change.": "Hari {d}, {w}. Klik untuk menukar.",
  "{w} working days, {r} rest days, {h} public holiday.": "{w} hari bekerja, {r} hari rehat, {h} cuti umum.",
  "{w} working days, {r} rest days, {h} public holidays.": "{w} hari bekerja, {r} hari rehat, {h} cuti umum.",
  "Find a file…": "Cari fail…", "Find a file": "Cari fail",
  "Show files of company": "Tunjukkan fail bagi syarikat",
  " (used for {who})": " (digunakan untuk {who})",
  "another employee": "pekerja lain",
  "No file matches.": "Tiada fail yang sepadan.",
  "No finished files yet. Read your time cards on the start page first.": "Belum ada fail yang selesai. Baca kad perakam waktu anda di halaman utama dahulu.",
  "e.g. MJ(1)": "cth. MJ(1)",
  "Name as in Million Payroll": "Nama seperti dalam Million Payroll",
  "Column with the daily hours": "Lajur dengan jam harian",
  "Automatic (the Total column)": "Automatik (lajur Total)",
  "Remove employee": "Buang pekerja",
  "Remove this employee from the payroll? Their documents are not deleted.": "Buang pekerja ini daripada senarai gaji? Dokumen mereka tidak dipadam.",
  "Employee No.": "No. Pekerja",
  "Name": "Nama",
  "Hours column": "Lajur jam",
  "Time-card files for this employee (tick every card of the month):": "Fail kad perakam waktu untuk pekerja ini (tandakan setiap kad bagi bulan ini):",
  "Company ": "Syarikat ",
  "No employees yet. Press “Add employee”.": "Belum ada pekerja. Tekan “Tambah pekerja”.",
  "Worked out: {v} – use it": "Dikira: {v} – guna ini",
  "{name} for this employee": "{name} untuk pekerja ini",
  "Remove “{name}” from the list for every employee?": "Buang “{name}” daripada senarai untuk semua pekerja?",
  " {n} employee has a figure on it this month; it will be cleared.": " {n} pekerja mempunyai angka padanya bulan ini; angka itu akan dikosongkan.",
  " {n} employees have a figure on it this month; it will be cleared.": " {n} pekerja mempunyai angka padanya bulan ini; angka itu akan dikosongkan.",
  "Remove “{name}” from the list": "Buang “{name}” daripada senarai",
  "Remove {name}": "Buang {name}",
  "Leave balance is kept in Million Payroll": "Baki cuti disimpan dalam Million Payroll",
  "{name} balance (kept in Million Payroll)": "Baki {name} (disimpan dalam Million Payroll)",
  "No lines yet.": "Belum ada baris.",
  "Name, exactly as in Million Payroll": "Nama, sama seperti dalam Million Payroll",
  "New {title} line": "Baris {title} baharu",
  "Add": "Tambah",
  "“{n}” is already in the {title} list.": "“{n}” sudah ada dalam senarai {title}.",
  "+ Add a {what} line": "+ Tambah baris {what}",
  "benefit": "manfaat", "leave": "cuti", "allowance": "elaun", "deduction": "potongan",
  "The line is added for every employee. Use the same name as in Million Payroll so the import matches.":
    "Baris ini ditambah untuk semua pekerja. Guna nama yang sama seperti dalam Million Payroll supaya import sepadan.",
  "Results appear here once you add an employee.": "Keputusan dipaparkan di sini selepas anda menambah pekerja.",
  "Complete": "Lengkap",
  "Needs checking": "Perlu disemak",
  "Not on a time card: keep these in Million Payroll.": "Tiada dalam kad perakam waktu: simpan ini dalam Million Payroll.",
  "Please check:": "Sila semak:",
  "Nothing to check for this employee.": "Tiada apa-apa untuk disemak bagi pekerja ini.",
  "Day by day (how the figures were worked out)": "Hari demi hari (cara angka dikira)",
  "Day": "Hari", "Type": "Jenis", "Hours written": "Jam yang ditulis", "Note": "Catatan",
  "Employee {a} of {b}": "Pekerja {a} daripada {b}",
  "Changes are saved automatically.": "Perubahan disimpan secara automatik.",
  "{n} employee is marked \"Needs checking\". In the file they are marked INCOMPLETE in the Notes column. Download anyway?":
    "{n} pekerja ditanda \"Perlu disemak\". Dalam fail, mereka ditanda INCOMPLETE dalam lajur Notes. Muat turun juga?",
  "{n} employees are marked \"Needs checking\". In the file they are marked INCOMPLETE in the Notes column. Download anyway?":
    "{n} pekerja ditanda \"Perlu disemak\". Dalam fail, mereka ditanda INCOMPLETE dalam lajur Notes. Muat turun juga?",

  // ---- server messages, word for word
  "Claude Code is not installed on this computer. Install it from claude.com/claude-code, then open this app again.":
    "Claude Code tidak dipasang pada komputer ini. Pasangkannya dari claude.com/claude-code, kemudian buka aplikasi ini semula.",
  "Claude Code is signed in with an API account, not with your Claude plan, so reading would be billed per use. Sign in again with your Claude account.":
    "Claude Code dilog masuk dengan akaun API, bukan dengan pelan Claude anda, jadi setiap bacaan akan dicaj. Log masuk semula dengan akaun Claude anda.",
  "Could not check whether Claude is signed in. Close this app and open it again.": "Tidak dapat menyemak sama ada Claude telah dilog masuk. Tutup aplikasi ini dan buka semula.",
  "You are not signed in to Claude. Press Sign in and finish the steps in your browser.": "Anda belum log masuk ke Claude. Tekan Log masuk dan selesaikan langkah dalam pelayar anda.",
  "Claude did not report this cell": "Claude tidak melaporkan sel ini",
  "Reading was cancelled. Pages already read are kept; press Continue to read the rest.": "Bacaan dibatalkan. Halaman yang sudah dibaca disimpan; tekan Teruskan untuk membaca selebihnya.",
  "Some characters could not be read": "Sesetengah aksara tidak dapat dibaca",
  "Could not be read with confidence": "Tidak dapat dibaca dengan yakin",
  "Claude's answer was not in the expected form. Try this file again.": "Jawapan Claude tidak dalam bentuk yang dijangka. Cuba fail ini sekali lagi.",
  "Claude's answer was not in the expected form, so nothing was read. Try this file again.": "Jawapan Claude tidak dalam bentuk yang dijangka, jadi tiada apa-apa yang dibaca. Cuba fail ini sekali lagi.",
  "Claude was not sure which way up this page is. Check every cell against the picture.": "Claude tidak pasti arah mana bahagian atas halaman ini. Semak setiap sel berbanding gambar.",
  "Your Claude plan has reached its usage limit for now. Wait until the limit resets (Claude Code shows when), then press Continue; pages already read are kept.":
    "Pelan Claude anda telah mencapai had penggunaan buat masa ini. Tunggu sehingga had ditetapkan semula (Claude Code menunjukkan bila), kemudian tekan Teruskan; halaman yang sudah dibaca disimpan.",
  "Your Claude sign-in has expired. Press Sign in (top right), then press Continue.": "Log masuk Claude anda telah tamat tempoh. Tekan Log masuk (atas kanan), kemudian tekan Teruskan.",
  "That correction does not match a cell in this document. Reload the page and try again.": "Pembetulan itu tidak sepadan dengan sel dalam dokumen ini. Muat semula halaman dan cuba lagi.",
  "That document was not found. It may have been moved or deleted.": "Dokumen itu tidak dijumpai. Ia mungkin telah dipindahkan atau dipadam.",
  "The company name could not be saved. Use up to 80 characters.": "Nama syarikat tidak dapat disimpan. Guna sehingga 80 aksara.",
  "That page is not available yet.": "Halaman itu belum tersedia.",
  "This document has not been read completely yet. Wait until it says it is finished (or press Continue), then download.":
    "Dokumen ini belum habis dibaca. Tunggu sehingga ia menunjukkan selesai (atau tekan Teruskan), kemudian muat turun.",
  "Table Reader is already reading this document. Wait for it to finish.": "Table Reader sedang membaca dokumen ini. Tunggu sehingga ia selesai.",
  "Reading stopped before it finished (the app was closed). Press Continue to read the rest; pages that were already read are kept.":
    "Bacaan berhenti sebelum selesai (aplikasi telah ditutup). Tekan Teruskan untuk membaca selebihnya; halaman yang sudah dibaca disimpan.",
  "Something went wrong while reading this document. Press Continue to try again. If it keeps happening, tell your support person.":
    "Berlaku masalah semasa membaca dokumen ini. Tekan Teruskan untuk cuba lagi. Jika ia berulang, maklumkan kepada pegawai sokongan anda.",
  "No table was found on this page. If there is one, check that the whole page is in the picture, then add the file again.":
    "Tiada jadual dijumpai pada halaman ini. Jika ada, pastikan seluruh halaman berada dalam gambar, kemudian tambah fail sekali lagi.",
  "Claude could not read this page: the picture is too blurry, dark or small. Take the photo again in good light (or scan it) and add it as a new file.":
    "Claude tidak dapat membaca halaman ini: gambar terlalu kabur, gelap atau kecil. Ambil foto semula dalam cahaya yang baik (atau imbas) dan tambahkannya sebagai fail baharu.",
  "Something went wrong inside Table Reader. Reload the page and try again. If it keeps happening, tell your support person.":
    "Berlaku masalah dalam Table Reader. Muat semula halaman dan cuba lagi. Jika ia berulang, maklumkan kepada pegawai sokongan anda.",
  "That correction could not be understood. Reload the page and try again.": "Pembetulan itu tidak dapat difahami. Muat semula halaman dan cuba lagi.",
  "Add at least one employee before downloading the payroll file.": "Tambah sekurang-kurangnya seorang pekerja sebelum memuat turun fail gaji.",
  "This app can only be opened on this computer.": "Aplikasi ini hanya boleh dibuka pada komputer ini.",
  "This request did not come from the Table Reader page.": "Permintaan ini bukan daripada halaman Table Reader.",
  "The payroll settings could not be understood. Reload the page and try again.": "Tetapan gaji tidak dapat difahami. Muat semula halaman dan cuba lagi.",
  "Choose a month and a year for the payroll.": "Pilih bulan dan tahun untuk gaji.",
  "Figures must be numbers (0 or more).": "Angka mestilah nombor (0 atau lebih).",
  "Normal hours per day must be a number from 1 to 24.": "Jam biasa sehari mestilah nombor dari 1 hingga 24.",
  "The message is too long (2000 characters at most).": "Mesej terlalu panjang (paling banyak 2000 aksara).",
  "No document chosen for this employee yet.": "Belum ada dokumen dipilih untuk pekerja ini.",
  "Employee No. is empty. Type it exactly as in Million Payroll.": "No. Pekerja kosong. Taipkannya sama seperti dalam Million Payroll.",
  "Each line needs a name (up to 80 characters).": "Setiap baris perlu ada nama (sehingga 80 aksara).",
  "One of the chosen documents was not found. It may have been moved or deleted.": "Salah satu dokumen yang dipilih tidak dijumpai. Ia mungkin telah dipindahkan atau dipadam.",
  "A document can belong to one employee only. Untick it from the other employee first.": "Satu dokumen hanya boleh dimiliki oleh seorang pekerja. Nyahtanda dokumen itu daripada pekerja lain dahulu.",
};

// "card.pdf, page 2" -> "card.pdf, halaman 2" (where a payroll message says which document it is about)
const msWhere = (w) => w.replace(/, page (\d+)$/, ", halaman $1");

// Server sentences that have names or numbers in them. Each: [pattern, Malay (with $1…) or a function of the match].
const MS_PATTERNS = [
  [/^Page (\d+) of (\d+): ([\s\S]*)$/, (m) => `Halaman ${m[1]} daripada ${m[2]}: ${tm(m[3])}`],
  [/^Claude was not sure \((\d+)% confident\)$/, "Claude tidak pasti (yakin $1%)"],
  [/^Claude reported a doubt it could not place \(([\s\S]*)\)\. Check the page\.$/, "Claude melaporkan keraguan yang tidak dapat diletakkan pada sel ($1). Semak halaman ini."],
  [/^Claude reported a problem: ([\s\S]*)\. Try this file again\.$/, "Claude melaporkan masalah: $1. Cuba fail ini sekali lagi."],
  [/^Claude's answer did not match the expected form \(([\s\S]*)\), so nothing was read\. Try this file again\.$/, "Jawapan Claude tidak sepadan dengan bentuk yang dijangka ($1), jadi tiada apa-apa yang dibaca. Cuba fail ini sekali lagi."],
  [/^Claude Code did not return a reading( \([\s\S]*\))?\. Try again; if it keeps happening, open Claude Code once on its own to check that it works\.$/, (m) => `Claude Code tidak memberikan bacaan${m[1] || ""}. Cuba lagi; jika ia berulang, buka Claude Code sekali secara berasingan untuk memastikan ia berfungsi.`],
  [/^Claude took longer than (\d+) minutes on this page\. Try again, or use a smaller or clearer picture\.$/, "Claude mengambil masa lebih daripada $1 minit untuk halaman ini. Cuba lagi, atau guna gambar yang lebih kecil atau lebih jelas."],
  [/^Claude Code could not be started \(([\s\S]*)\)\. Reinstall Claude Code or restart the computer, then try again\.$/, "Claude Code tidak dapat dimulakan ($1). Pasang semula Claude Code atau mulakan semula komputer, kemudian cuba lagi."],
  [/^The file (.+) was not found\.$/, "Fail $1 tidak dijumpai."],
  [/^(.+) is not a picture file\. Use JPG or PNG\.$/, "$1 bukan fail gambar. Guna JPG atau PNG."],
  [/^(.+) could not be opened as a picture\. Check that the file is not damaged, or take the photo again\.$/, "$1 tidak dapat dibuka sebagai gambar. Pastikan fail tidak rosak, atau ambil foto semula."],
  [/^(.+) is not a PDF or a picture \(JPG, PNG\)\. Save or scan it as a PDF, JPG or PNG and add it again\.$/, "$1 bukan PDF atau gambar (JPG, PNG). Simpan atau imbas sebagai PDF, JPG atau PNG dan tambahkannya semula."],
  [/^(.+) is empty\. Check the file and add it again\.$/, "$1 kosong. Semak fail dan tambahkannya semula."],
  [/^That entry is too long \(over (\d+) characters\)\.$/, "Catatan itu terlalu panjang (melebihi $1 aksara)."],
  [/^(.+) could not be opened\. It may be damaged or password-protected\. Open it on your computer to check, then add it again\.$/, "$1 tidak dapat dibuka. Ia mungkin rosak atau dilindungi kata laluan. Buka pada komputer anda untuk menyemak, kemudian tambahkannya semula."],
  [/^(.+) has no pages\.$/, "$1 tidak mempunyai halaman."],
  [/^(.+) has (\d+) pages; Table Reader takes up to (\d+) at a time\. Split the file and add the parts separately\.$/, "$1 mempunyai $2 halaman; Table Reader menerima sehingga $3 halaman pada satu masa. Pecahkan fail dan tambah bahagiannya secara berasingan."],
  [/^Page (\d+) of (.+) could not be drawn\. Open the file on your computer to check it, then add it again\.$/, "Halaman $1 bagi $2 tidak dapat dipaparkan. Buka fail pada komputer anda untuk menyemaknya, kemudian tambahkannya semula."],
  [/^(.+) is larger than 150 MB\. Scan it at a lower quality or split it into smaller files\.$/, "$1 lebih besar daripada 150 MB. Imbas pada kualiti yang lebih rendah atau pecahkan kepada fail yang lebih kecil."],
  [/^(.+) has not been read completely yet\.$/, "$1 belum habis dibaca."],
  [/^(.+) could not be saved\. Check that the computer has free disk space, then add it again\.$/, "$1 tidak dapat disimpan. Pastikan komputer mempunyai ruang cakera yang mencukupi, kemudian tambahkannya semula."],
  [/^'(.+)' is in the (.+) list twice\. Use another name\.$/, "'$1' ada dua kali dalam senarai $2. Guna nama lain."],
  [/^No entry found for day (.+) in the chosen documents\. These days were counted as not worked: add the other card if there is one\.$/, "Tiada catatan dijumpai untuk hari $1 dalam dokumen yang dipilih. Hari-hari ini dikira sebagai tidak bekerja: tambah kad yang satu lagi jika ada."],
  [/^(.+): no column with the daily hours was found\. Choose it in the 'Hours column' list\.$/, (m) => `${msWhere(m[1])}: tiada lajur dengan jam harian dijumpai. Pilihnya dalam senarai 'Lajur jam'.`],
  [/^(.+), day (\d+): the hours are still unclear\. Check the yellow cell in the document\.$/, (m) => `${msWhere(m[1])}, hari ${m[2]}: jam masih tidak jelas. Semak sel kuning dalam dokumen.`],
  [/^(.+), day (\d+): '([\s\S]*)' is not a number of hours\. Correct it in the document\.$/, (m) => `${msWhere(m[1])}, hari ${m[2]}: '${m[3]}' bukan bilangan jam. Betulkannya dalam dokumen.`],
  [/^Day (\d+) appears more than once \((.+) and (.+)\)\. It was left out until you fix it\.$/, (m) => `Hari ${m[1]} muncul lebih daripada sekali (${msWhere(m[2])} dan ${msWhere(m[3])}). Ia tidak dikira sehingga anda membetulkannya.`],
  [/^(.+), row (\d+): the date is unclear, so its hours were left out\. Fix the date in the document\.$/, (m) => `${msWhere(m[1])}, baris ${m[2]}: tarikh tidak jelas, jadi jamnya tidak dikira. Betulkan tarikh dalam dokumen.`],
  [/^(.+), row (\d+): the date (.+) is not in the chosen month, so its hours were left out\.$/, (m) => `${msWhere(m[1])}, baris ${m[2]}: tarikh ${m[3]} bukan dalam bulan yang dipilih, jadi jamnya tidak dikira.`],
  [/^(.+), row (\d+): the date could not be read, so its hours were left out\.$/, (m) => `${msWhere(m[1])}, baris ${m[2]}: tarikh tidak dapat dibaca, jadi jamnya tidak dikira.`],
  [/^(.+), row (\d+): day (\d+) is not in this month, so its hours were left out\.$/, (m) => `${msWhere(m[1])}, baris ${m[2]}: hari ${m[3]} bukan dalam bulan ini, jadi jamnya tidak dikira.`],
];

function fill(text, vars) {
  return vars ? text.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : text;
}

function t(text, vars) {
  return fill(LANG === "ms" && MS[text] !== undefined ? MS[text] : text, vars);
}

// The English sentence for one or for many (Malay has no plural), then translated.
function tn(n, one, many, vars) {
  return t(n === 1 ? one : many, { n, ...vars });
}

function tm(text) {
  if (LANG !== "ms" || !text) return text;
  if (MS[text] !== undefined) return MS[text];
  for (const [re, out] of MS_PATTERNS) {
    const m = text.match(re);
    if (m) return typeof out === "function" ? out(m) : text.replace(re, out);
  }
  return text;
}

// Static text in index.html: elements marked data-t (their text), data-t-title, data-t-aria, data-t-placeholder.
function translatePage() {
  const key = (s) => s.replace(/\s+/g, " ").trim();
  document.querySelectorAll("[data-t]").forEach((n) => { n.textContent = t(key(n.textContent)); });
  document.querySelectorAll("[data-t-title]").forEach((n) => { n.title = t(n.title); });
  document.querySelectorAll("[data-t-aria]").forEach((n) => n.setAttribute("aria-label", t(n.getAttribute("aria-label"))));
  const sw = document.getElementById("lang");
  if (sw) {
    sw.textContent = LANG === "ms" ? "English" : "Bahasa Melayu";
    sw.setAttribute("lang", LANG === "ms" ? "en" : "ms");
    sw.title = t("Change the language");
    sw.addEventListener("click", () => {
      try { localStorage.setItem("lang", LANG === "ms" ? "en" : "ms"); } catch (_) { /* private window: stays as is */ }
      location.reload();
    });
  }
}

translatePage();     // this file is loaded at the end of the page, so the page above is already there
