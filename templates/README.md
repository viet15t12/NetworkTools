# User-facing templates

Trạng thái: **implemented** cho các template import/export mà người dùng có thể
tải hoặc điền. Template sinh lệnh thiết bị không đặt tại đây; chúng phải nằm cạnh
feature tương ứng trong `features/<name>/templates/`.

Mỗi file mới cần có consumer runtime hoặc test, dữ liệu mẫu không chứa thông tin
thật và định dạng phải được kiểm tra trước khi phát hành. Nếu một template không
còn được UI/service tham chiếu, xóa cả file và cập nhật hướng dẫn nhập dữ liệu.
