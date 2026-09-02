// ==========================================================
// BÁO CÁO NCKH SINH VIÊN - CAMS (TYPST)
// Chuyển từ cấu trúc LaTeX modular sang Typst.
// ==========================================================

#import "config/settings.typ": report-style, report-figure-outline-entry
#import "config/commands.typ": *
#import "config/info.typ": *
#import "config/images.typ": *
#import "config/listings.typ": *

#show: report-style

// ----------------------------------------------------------
// PHẦN ĐẦU
// ----------------------------------------------------------
#set page(numbering: "i")
#counter(page).update(1)

#include "contents/00_loi_cam_doan.typ"
#include "contents/00_loi_cam_on.typ"
#include "contents/00_tom_tat.typ"
#include "contents/00_danh_muc_tu_viet_tat.typ"

#pagebreak()
#outline(title: upper[Mục lục], depth: 4)

#pagebreak()
#{
  show outline.entry: it => report-figure-outline-entry(image, [Hình], it)
  outline(
    title: upper[Danh mục hình],
    target: figure.where(kind: image),
  )
}

#pagebreak()
#{
  show outline.entry: it => report-figure-outline-entry(table, [Bảng], it)
  outline(
    title: upper[Danh mục bảng],
    target: figure.where(kind: table),
  )
}

// ----------------------------------------------------------
// NỘI DUNG CHÍNH
// ----------------------------------------------------------
#pagebreak()
#set page(numbering: "1")
#counter(page).update(1)

#include "contents/01_tong_quan.typ"
#include "contents/02_co_so_ly_thuyet.typ"
#include "contents/03_phan_tich_thiet_ke.typ"
#include "contents/04_xay_dung_phan_mem.typ"
#include "contents/05_thu_nghiem_danh_gia.typ"
#include "contents/06_ket_luan_huong_phat_trien.typ"

// ----------------------------------------------------------
// TÀI LIỆU THAM KHẢO
// ----------------------------------------------------------
#pagebreak()
#bibliography(
  "bibliography/cams_references.bib",
  title: [Tài liệu tham khảo],
  style: "ieee",
)

// ----------------------------------------------------------
// PHỤ LỤC
// ----------------------------------------------------------
#include "appendix/appendix_a_cau_truc_du_an.typ"
