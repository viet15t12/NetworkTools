// Bảng dùng chung cho báo cáo nghiên cứu khoa học.
// - Chú thích đặt phía trên bảng, tương tự cách trình bày của IEEE.
// - Giữ đường kẻ dọc để dễ theo dõi dữ liệu theo cột.
// - Chỉ dùng đường kẻ ngang ở đầu bảng, sau tiêu đề và cuối bảng.
// - Cỡ chữ nhỏ hơn thân bài để bảng gọn nhưng vẫn dễ đọc trên khổ A4.
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

#let table-code(value, size: 9pt) = {
  // Inline `raw` text is an unbreakable box in Typst. Technical identifiers in
  // narrow table columns therefore cross cell borders. Render them as
  // monospaced text and add invisible wrap opportunities at safe separators
  // and camelCase boundaries instead.
  let breakable = value
    .replace(
      regex("[a-z][A-Z]"),
      pair => pair.text.slice(0, 1) + "\u{200b}" + pair.text.slice(1, 2),
    )
    .replace("_", "_\u{200b}")
    .replace("/", "/\u{200b}")
    .replace(".", ".\u{200b}")
    .replace("-", "-\u{200b}")

  text(font: "DejaVu Sans Mono", size: size, breakable)
}

#let report-table(
  columns: auto,
  header: (),
  rows: (),
  caption: none,
  cell-align: left + horizon,
  width: 100%,
  note: none,
  text-size: 10pt,
  cell-inset: (x: 5pt, y: 5pt),
) = {
  let header-cells = header.map(cell => table.cell(
    fill: rgb("#e8e8e8"),
  )[#strong(cell)])
  let body-cells = rows.fold((), (cells, row) => cells + row)

  let table-content = block(
    width: width,
    breakable: false,
  )[
    #set text(size: text-size)
    // Nội dung trong ô cần căn trái tự nhiên. Kế thừa chế độ căn đều của
    // thân bài sẽ kéo giãn khoảng trắng, đặc biệt ở tiêu đề và cột hẹp.
    #set par(justify: false, first-line-indent: 0pt, leading: 0.7em)

    #table(
      columns: columns,
      align: cell-align,
      inset: cell-inset,
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

    figure(
      table-content,
      kind: table,
      caption: caption,
    )
  }
}
