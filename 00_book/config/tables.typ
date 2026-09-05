// Bảng dùng chung cho báo cáo nghiên cứu khoa học.
// - Chú thích đặt phía trên bảng, tương tự cách trình bày của IEEE.
// - Giữ đường kẻ dọc để dễ theo dõi dữ liệu theo cột.
// - Chỉ dùng đường kẻ ngang ở đầu bảng, sau tiêu đề và cuối bảng.
// - Cỡ chữ nhỏ hơn thân bài để bảng gọn nhưng vẫn dễ đọc trên khổ A4.
// - Nội dung ô được neo lên trên mặc định (valign: top) để dòng đầu của
//   mọi cột luôn ngang hàng với nhau; có thể chọn horizon (giữa ô) hoặc
//   bottom (cuối ô) nếu muốn neo khác đi.
//
// Ví dụ:
// #report-table(
//   columns: (1fr, 2fr),
//   header: ([Cột A], [Cột B]),
//   rows: (
//     ([A1], [B1]),
//     ([A2], [B2]),
//   ),
//   caption: [Tên bảng],
// ) <tab-example>

#let report-table(
  columns: auto,
  header: (),
  rows: (),
  caption: none,
  figure-label: none,
  cell-align: left,
  // Neo dọc nội dung trong ô: top (trên), horizon (giữa), bottom (cuối).
  valign: top,
  width: 100%,
  note: none,
) = {
  let header-cells = header.map(cell => table.cell(
    fill: rgb("#e8e8e8"),
  )[#strong(cell)])
  let body-cells = rows.fold((), (cells, row) => cells + row)

  let table-content = block(
    width: width,
    breakable: false,
  )[
    #set text(size: 11pt)
    #set par(first-line-indent: 0pt, leading: 0.7em)

    #table(
      columns: columns,
      align: cell-align + valign,
      inset: (x: 6pt, y: 6pt),
      // Chỉ tạo các đường dọc bằng viền trái/phải của ô. Các đường
      // ngang cần thiết được khai báo tường minh bằng table.hline.
      stroke: (x, y) => (
        left: 0.45pt + rgb("#666666"),
        right: 0.45pt + rgb("#666666"),
      ),
      table.header(
        table.hline(stroke: 0.8pt + black),
        ..header-cells,
        table.hline(stroke: 0.55pt + black),
      ),
      ..body-cells,
      table.hline(stroke: 0.8pt + black),
    )

    #if note != none {
      v(3pt)
      text(size: 9pt, style: "italic")[Ghi chú: #note]
    }
  ]

  if caption == none {
    table-content
  } else {
    set figure.caption(position: top)
    show figure: set block(breakable: false)

    let result = figure(
      table-content,
      kind: table,
      caption: caption,
    )
    if figure-label == none {
      result
    } else {
      [#result#figure-label]
    }
  }
}
