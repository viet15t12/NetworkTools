# Vận hành website tài liệu CAMS

MkDocs lấy nội dung từ `00_book` và tạo website tĩnh trong `site`. Các file Typst vẫn được giữ làm nguồn tham khảo nhưng bị loại khỏi website khi build.

## Chạy website trên máy cá nhân

```bash
python -m pip install -r requirements-docs.txt
mkdocs serve
```

Mở địa chỉ được MkDocs hiển thị, mặc định là <http://127.0.0.1:8000/CAMS/>.

Kiểm tra bản build giống GitHub Actions:

```bash
mkdocs build --strict
```

## Thêm các chương Markdown

Đặt file `.md` trực tiếp trong `00_book` hoặc trong `00_book/contents`. Khi chưa khai báo `nav` trong `mkdocs.yml`, MkDocs sẽ tự tạo điều hướng từ các file Markdown tìm thấy.

Nếu file chương nằm trong `00_book/contents`, đường dẫn ảnh cần đi lên một cấp, ví dụ:

```markdown
![Tổng quan Workspace](../figures/gui/chapter-03/01-workspace-overview.png)
```

Khi đã chuyển đổi xong các chương, có thể thêm mục `nav` vào `mkdocs.yml` để cố định tên và thứ tự hiển thị:

```yaml
nav:
  - Trang chủ: index.md
  - Tổng quan: contents/01_tong_quan.md
  - Cài đặt và sử dụng: contents/02_cai_dat_su_dung.md
  - Giao diện và điều hướng: contents/03_giao_dien_dieu_huong.md
```

## Publish bằng GitHub Pages

Workflow `.github/workflows/docs.yml` tự build và publish khi nội dung tài liệu được đẩy lên nhánh `main`. Trong repository GitHub, vào **Settings → Pages** và chọn **Source: GitHub Actions** một lần. Sau đó có thể chạy workflow thủ công từ tab **Actions** hoặc push thay đổi mới.
