// ==========================================================
// CAMS MANUAL BOOK
// ==========================================================

#import "config/settings.typ": report-style, report-figure-outline-entry
#import "config/commands.typ": *
#import "config/info.typ": *
#import "config/images.typ": *
#import "config/listings.typ": *
#import "config/diagrams.typ": *

#show: report-style

// ----------------------------------------------------------
// PHẦN ĐẦU
// ----------------------------------------------------------
#set page(numbering: "i")
#counter(page).update(1)

#include "contents/00_loi_mo_dau.typ"

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
#include "contents/02_cai_dat_su_dung.typ"
#include "contents/03_giao_dien_dieu_huong.typ"
#include "contents/04_quan_ly_thiet_bi.typ"

// ----------------------------------------------------------
// PHỤ LỤC
// ----------------------------------------------------------
// #include "appendix/appendix_a_cau_truc_du_an.typ"
