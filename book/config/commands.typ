// Các helper dùng lặp lại trong báo cáo.

#let cover-institution(body) = text(
  size: 14pt,
  weight: "bold",
  body,
)

#let cover-report-label(body) = text(
  size: 14pt,
  body,
)

#let cover-project-title(body) = text(
  size: 16pt,
  weight: "bold",
  body,
)

#let cover-metadata(body) = text(
  size: 14pt,
  body,
)

#let front-heading(title, outlined: true) = {
  heading(level: 1, numbering: none, outlined: outlined)[#title]
}

#let appendix-heading(title) = {
  heading(level: 1, numbering: none, outlined: true)[#title]
}

#let appendix-section(label, title) = {
  heading(level: 2, numbering: none, outlined: true)[#label #title]
}

#let report-note(body) = block(
  width: 100%,
  inset: 10pt,
  radius: 4pt,
  stroke: 0.5pt,
  fill: luma(245),
  body,
)

#let todo(body) = block(
  width: 100%,
  inset: 8pt,
  stroke: 0.5pt,
  [*TODO:* #body],
)
