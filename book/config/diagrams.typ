// Các thành phần dùng chung để tạo sơ đồ luồng đơn giản.
//
// Ví dụ:
// #flow-diagram(
//   [Bắt đầu],
//   [Kiểm tra thiết bị],
//   [Tạo cấu hình],
//   [Xem và đẩy cấu hình],
//   [Triển khai],
//   max-per-row: 3,
//   max-node-width: 42mm,
//   max-node-height: 21mm,
// )

// Nút hình chữ nhật bo góc, theo tỷ lệ của sơ đồ draw.io tham chiếu.
// Chiều rộng và chiều cao luôn bị giới hạn bởi các giá trị `max-*`.
#let diagram-node(
  body,
  width: 40mm,
  height: 20mm,
  max-width: 42mm,
  max-height: 22mm,
  inset: 5pt,
  radius: 5pt,
  fill: white,
  stroke: 0.7pt + rgb("#555555"),
  text-size: 10pt,
) = {
  let node-width = calc.min(width, max-width)
  let node-height = calc.min(height, max-height)

  block(
    width: node-width,
    height: node-height,
    inset: inset,
    radius: radius,
    fill: fill,
    stroke: stroke,
    clip: true,
  )[
    #set text(size: text-size)
    #set par(justify: false, first-line-indent: 0pt, leading: 0.7em)
    #align(center + horizon, body)
  ]
}

// Biến thể hình vuông khi một sơ đồ cụ thể cần nút có hai cạnh bằng nhau.
#let diagram-square(
  body,
  size: 28mm,
  max-size: 32mm,
  ..options,
) = diagram-node(
  body,
  width: size,
  height: size,
  max-width: max-size,
  max-height: max-size,
  ..options.named(),
)

// Mũi tên nối các nút. Các hướng hợp lệ: "right", "left" và "down".
#let diagram-arrow(
  direction: "right",
  size: 8mm,
  color: rgb("#555555"),
  text-size: 16pt,
) = {
  let mark = if direction == "right" {
    [→]
  } else if direction == "left" {
    [←]
  } else if direction == "down" {
    [↓]
  } else {
    panic("diagram-arrow: direction must be right, left, or down")
  }

  box(
    width: size,
    height: size,
    fill: none,
  )[
    #align(center + horizon, text(size: text-size, fill: color, mark))
  ]
}

// Sắp xếp các nút theo thứ tự dạng rắn (trái -> phải, xuống dòng,
// phải -> trái). Số nút trên mỗi dòng và kích thước tối đa của nút
// đều có thể cấu hình. Nếu chiều rộng trang nhỏ, nút sẽ tự động thu nhỏ.
// Toàn bộ sơ đồ là một khối không thể ngắt trang.
#let flow-diagram(
  ..items,
  max-per-row: 4,
  node-width: 40mm,
  node-height: 20mm,
  max-node-width: 42mm,
  max-node-height: 22mm,
  node-inset: 5pt,
  arrow-size: 8mm,
  row-gap: 4mm,
  radius: 5pt,
  fill: white,
  stroke: 0.7pt + rgb("#555555"),
  text-size: 10pt,
  arrow-color: rgb("#555555"),
) = {
  let nodes = items.pos()

  assert(max-per-row >= 1, message: "flow-diagram: max-per-row must be at least 1")
  assert(node-width > 0pt, message: "flow-diagram: node-width must be positive")
  assert(node-height > 0pt, message: "flow-diagram: node-height must be positive")
  assert(max-node-width > 0pt, message: "flow-diagram: max-node-width must be positive")
  assert(max-node-height > 0pt, message: "flow-diagram: max-node-height must be positive")

  if nodes.len() > 0 {
    block(width: 100%, breakable: false)[
      #layout(size => {
        let per-row = calc.min(max-per-row, nodes.len())
        let capped-width = calc.min(node-width, max-node-width)
        let rendered-height = calc.min(node-height, max-node-height)
        let available-node-width = (
          size.width - arrow-size * (per-row - 1)
        ) / per-row
        let rendered-width = calc.min(capped-width, available-node-width)
        let diagram-width = rendered-width * per-row + arrow-size * (per-row - 1)
        let rows = nodes.chunks(per-row)
        let parts = ()

        for (row-index, row) in rows.enumerate() {
          let goes-left = calc.rem(row-index, 2) == 1
          let displayed-row = if goes-left { row.rev() } else { row }
          let columns = ()
          let cells = ()

          for (node-index, node) in displayed-row.enumerate() {
            columns.push(rendered-width)
            cells.push(diagram-node(
              node,
              width: rendered-width,
              height: rendered-height,
              max-width: rendered-width,
              max-height: rendered-height,
              inset: node-inset,
              radius: radius,
              fill: fill,
              stroke: stroke,
              text-size: text-size,
            ))

            if node-index < displayed-row.len() - 1 {
              columns.push(arrow-size)
              cells.push(diagram-arrow(
                direction: if goes-left { "left" } else { "right" },
                size: arrow-size,
                color: arrow-color,
              ))
            }
          }

          let row-align = if rows.len() == 1 {
            center
          } else if goes-left {
            right
          } else {
            left
          }

          parts.push(block(width: diagram-width)[
            #align(row-align, grid(
              columns: columns,
              align: center + horizon,
              ..cells,
            ))
          ])

          if row-index < rows.len() - 1 {
            let connector-inset = (rendered-width - arrow-size) / 2
            let connector = diagram-arrow(
              direction: "down",
              size: arrow-size,
              color: arrow-color,
            )

            parts.push(block(width: diagram-width, height: row-gap + arrow-size)[
              #if goes-left {
                align(left, pad(left: connector-inset, connector))
              } else {
                align(right, pad(right: connector-inset, connector))
              }
            ])
          }
        }

        align(center, stack(dir: ttb, spacing: 0pt, ..parts))
      })
    ]
  }
}
