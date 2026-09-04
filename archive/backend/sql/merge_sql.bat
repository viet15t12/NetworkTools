@echo off
set "outputFile=main.sql"

echo Merging SQL files into %outputFile%...

:: Xóa file main.sql cũ nếu tồn tại
if exist "%outputFile%" del "%outputFile%"

:: Lặp qua tất cả các file .sql trong thư mục hiện tại theo thứ tự chữ cái (đã được đánh số)
for /f "delims=" %%f in ('dir /b /o:n *.sql') do (
    :: Bỏ qua file main.sql để tránh việc nối chính nó
    if /I not "%%f"=="%outputFile%" (
        echo -- ========================================================== >> "%outputFile%"
        echo -- File: %%f >> "%outputFile%"
        echo -- ========================================================== >> "%outputFile%"
        
        :: Nối nội dung file vào main.sql
        type "%%f" >> "%outputFile%"
        
        :: Thêm 2 dòng trống để phân tách giữa các file
        echo. >> "%outputFile%"
        echo. >> "%outputFile%"
        
        echo - Đã thêm %%f
    )
)

echo Hoàn thành việc nối file thành %outputFile%!
pause
