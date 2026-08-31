# CAMS – Typst report

Bộ báo cáo NCKH đã được chuyển từ cấu trúc LaTeX modular sang Typst.

## Cấu trúc

```text
reports/
├── appendix/ ------------------------- Phụ lục
├── bibliography ---------------------- Trích dẫn
├── chapters/ ------------------------- Chương
├── config/ --------------------------- Cấu hình chung
├── cover/ ---------------------------- Trang bìa
├── figures/ -------------------------- Hình ảnh
├── DETAILED_OUTLINE.md --------------- Đề cương Báo cáo Nghiên cứu khoa học
└── main.typ  
```

## Ảnh

Đặt ảnh vào `figures/`, ví dụ:

```text
figures/gui/main_window.png
```

## Bảng trong báo cáo

Dùng helper `report-table` để các bảng có chú thích ở phía trên, giữ đường kẻ dọc và chỉ dùng các đường kẻ ngang cần thiết ở đầu bảng, sau hàng tiêu đề và cuối bảng:

```typst
#import "config/tables.typ": report-table

#report-table(
  columns: (1fr, 2fr),
  header: ([Cột 1], [Cột 2]),
  rows: (
    ([Nội dung hàng 1], [Nội dung cột 2]),
    ([Nội dung hàng 2], [Nội dung cột 2]),
  ),
  caption: [Bảng mẫu ví dụ],
) <tab-test-results>
```

Có thể bỏ `caption` cho bảng không cần đánh số, hoặc thêm `note: [...]` để đặt ghi chú ngay dưới bảng.

Trong file `.typ`:

```typst
#insert-image(
  "figures/gui/main_window.png",
  width: 80%,
  caption: [Giao diện chính của CAMS],
) <fig-main-window>
```

Tham chiếu:

```typst
Xem @fig-main-window.
```

## Tài liệu tham khảo

Typst đọc trực tiếp BibLaTeX/BibTeX `.bib`:

```typst
Theo @tanenbaum2021computer, ...
```

Nếu project LaTeX gốc đã có `networktools_references.bib`, hãy chép đè file mẫu trong project này để giữ toàn bộ nguồn cũ.

## Lưu ý

- `packages.tex` và `latexmkrc` không còn cần thiết.
- Các chapter và appendix đã được tạo dựa trên đề cương hiện tại.
- Các vị trí `TODO` cần cập nhật bằng thông tin, ảnh, test và số đo thực tế trước khi nộp.
