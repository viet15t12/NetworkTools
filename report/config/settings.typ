// Thiết lập trình bày chung cho báo cáo NCKH.

#let report-heading-numbering(..numbers) = {
  let values = numbers.pos()

  if values.len() == 1 {
    [CHƯƠNG #numbering("1", ..values)]
  } else {
    numbering("1.1.1.1", ..values)
  }
}

#let report-figure-numbering(number) = context {
  let heading-number = counter(heading).get()
  let chapter = if heading-number.len() > 0 { heading-number.at(0) } else { 0 }

  if chapter > 0 {
    numbering("1.1", chapter, number)
  } else {
    numbering("1", number)
  }
}

#let report-table-numbering(number) = context {
  let heading-number = counter(heading).get()
  let chapter = if heading-number.len() > 0 { heading-number.at(0) } else { 0 }

  if chapter > 0 {
    numbering("1.1", chapter, number)
  } else {
    numbering("1", number)
  }
}

// Trong danh mục hình/bảng, hàm numbering mặc định được đánh giá tại trang
// danh mục. Đọc bộ đếm tại vị trí phần tử để số chương luôn khớp chú thích.
#let report-figure-outline-entry(kind, supplement, it) = context {
  let location = it.element.location()
  let heading-number = counter(heading).at(location)
  let chapter = if heading-number.len() > 0 { heading-number.at(0) } else { 0 }
  let figure-number = counter(figure.where(kind: kind)).at(location).at(0)
  let appendix-markers = query(<appendix-a-start>)
  let in-appendix-a = (
    appendix-markers.len() > 0 and
    location.position().page >= appendix-markers.first().location().position().page
  )
  let formatted-number = if in-appendix-a {
    [A.#figure-number]
  } else if chapter > 0 {
    numbering("1.1", chapter, figure-number)
  } else {
    numbering("1", figure-number)
  }
  let prefix = [#supplement #formatted-number]

  link(
    location,
    it.indented(prefix, it.inner()),
  )
}

#let report-equation-numbering(number) = context {
  let heading-number = counter(heading).get()
  let chapter = if heading-number.len() > 0 { heading-number.at(0) } else { 0 }
  numbering("(1.1)", chapter, number)
}

#let styled-heading(
  it,
  size: 13pt,
  weight: "regular",
  style: "normal",
  alignment: left,
  above: 10pt,
  below: 18pt,
) = block(
  width: 100%,
  breakable: false,
  above: above,
  below: below,
)[
  #set text(size: size, weight: weight, style: style)
  #set par(justify: false, spacing: 0pt)
  #align(alignment, it)
]

#let report-style(body) = {
  set page(
    paper: "a4",
    margin: (
      left: 3cm,
      right: 2cm,
      top: 2.5cm,
      bottom: 2.5cm,
    ),
    header: none,
    numbering: "1",
    number-align: center + bottom,
    footer-descent: 0.5em,
  )

  set text(
    font: "Times New Roman",
    size: 13pt,
    lang: "vi",
  )

  set par(
    justify: true,
    first-line-indent: 0pt,
    leading: 1.05em,
    spacing: 16pt,
  )

  set list(
    marker: ([•], [o], [▪]),
    indent: 0.5cm,
    body-indent: 0.5cm,
    tight: false,
    spacing: 1.4em,
  )
  set enum(
    indent: 0.5cm,
    body-indent: 0.5cm,
    tight: false,
    spacing: 1.4em,
  )

  // Bullet/enum: Times New Roman 13 pt, 1,5 dòng, 0 pt trước/sau,
  // không thụt dòng đầu và căn trái.
  show list: it => {
    set list(tight: false, spacing: 1.4em)
    set par(
      justify: false,
      first-line-indent: 0pt,
      leading: 1.05em,
      spacing: 0pt,
    )
    it
  }
  show enum: it => {
    set enum(tight: false, spacing: 1.4em)
    set par(
      justify: false,
      first-line-indent: 0pt,
      leading: 1.05em,
      spacing: 0pt,
    )
    it
  }

  show raw.where(block: false): set text(font: "Cascadia Code", size: 11pt, weight: "light", features: ("zero",))
  show raw.where(block: false): box.with(
    inset: (x: 4pt, y: 0pt),
    outset: (y: 3pt),
  )

  show raw.where(block: true): set text(font: "Cascadia Code", size: 11pt, weight: "light", features: ("zero",))
  show raw.where(block: true): block.with(
    width: 100%,
    stroke: 0.4pt + luma(120),
    inset: 10pt,
    radius: 4pt,
  )

  set heading(numbering: report-heading-numbering)
  set outline(indent: 0.46cm)
  set math.equation(
    numbering: report-equation-numbering,
    number-align: right + horizon,
    supplement: [Phương trình],
  )

  // Cấp 1 có hai vai trò: tiêu đề phần đầu không đánh số và chương có số.
  show heading.where(level: 1): it => {
    pagebreak(weak: true)

    if it.numbering == none {
      styled-heading(
        it,
        size: 13pt,
        weight: "bold",
        alignment: center,
        above: 24pt,
        below: 24pt,
      )
    } else {
      counter(figure.where(kind: image)).update(0)
      counter(figure.where(kind: table)).update(0)
      counter(math.equation).update(0)

      styled-heading(
        [
          #counter(heading).display(report-heading-numbering)
          #h(0.5em)
          #upper(it.body.text)
        ],
        size: 14pt,
        weight: "bold",
        alignment: left,
        above: 24pt,
        below: 24pt,
      )
    }
  }
  show heading.where(level: 2): it => styled-heading(
    it,
    size: 13pt,
    weight: "bold",
    above: 18pt,
    below: 12pt,
  )
  show heading.where(level: 3): it => styled-heading(
    it,
    size: 13pt,
    weight: "bold",
    style: "italic",
  )
  show heading.where(level: 4): it => styled-heading(
    it,
    size: 13pt,
    style: "italic",
  )

  // Các danh mục:Times New Roman 13 pt, không thụt đầu dòng và căn trái.
  // Không bọc trong block — giữ nguyên khoảng cách mặc định của Typst
  // để Mục lục, Danh mục hình, Danh mục bảng đều có inter-item giống nhau.
  show outline.entry: it => {
    set text(weight: if it.level == 1 { "bold" } else { "regular" })
    set par(justify: false, first-line-indent: 0pt)
    it
  }

  show figure.caption: it => {
    set text(size: 12pt, style: "italic")
    set par(
      justify: false,
      first-line-indent: 0pt,
      leading: 0.65em,
      spacing: 0pt,
    )
    block(width: 100%, above: 6pt, below: 6pt, breakable: false)[
      #align(center, it)
    ]
  }

  // Tên hình/bảng tiếng Việt.
  show figure.where(kind: image): set figure(
    supplement: [Hình],
    numbering: report-figure-numbering,
  )
  show figure.where(kind: table): set figure(
    supplement: [Bảng],
    numbering: report-table-numbering,
  )

  body
}
