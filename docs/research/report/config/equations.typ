// Phương trình khối dùng cú pháp toán native của Typst.
// Kiểu đánh số (chương.thứ-tự), căn phải và tham chiếu theo nhãn
// được thiết lập tập trung trong settings.typ.
//
// Ví dụ:
// $ E = m c^2 $ <eq-energy>
//
// Tham chiếu bằng @eq-energy.

#let report-equation(body, label: none) = {
  let equation = math.equation(
    block: true,
    body,
  )

  if label == none {
    equation
  } else {
    [#equation #label]
  }
}
