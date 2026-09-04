# Scripts

Cập nhật: **2026-08-16**.

- `build_databases.py`: build atomically DB runtime từ schema chuẩn; chạy lại sẽ thay DB đích nên cần backup dữ liệu cần giữ.
- `validate_structure.py`: kiểm tra README bắt buộc, README/status feature,
  `qmldir`, runtime artifact, path tuyệt đối và ranh giới core/session; chỉ đọc
  repository.
