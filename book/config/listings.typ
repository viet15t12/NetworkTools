// Helper hiển thị code/lệnh.
// Typst hỗ trợ raw block trực tiếp bằng ```lang ... ```.

#let codebox(code, caption: none) = {
  set text(font: "Cascadia Code", size: 11pt, weight: "light")
  block(
    width: 100%,
    stroke: 0.4pt + luma(120),
    inset: 10pt,
    radius: 4pt,
    code,
  )
  if caption != none {
    align(center, text(size: 10pt)[#caption])
  }
}
