# B-Spline Advanced - 2D & 3D Surface Editor 🚀

![C++](https://img.shields.io/badge/C++-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)
![OpenGL](https://img.shields.io/badge/OpenGL-FFFFFF?style=for-the-badge&logo=opengl)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

Một ứng dụng C++ đồ họa tương tác mạnh mẽ được xây dựng bằng **OpenGL**, **FreeGLUT** và **Win32 API**. Phần mềm mô phỏng các công cụ thiết kế CAD chuyên nghiệp, cho phép người dùng vẽ, chỉnh sửa và điêu khắc hình học dựa trên thuật toán B-Spline cho cả bề mặt 2D và 3D.

---

## ✨ Tính Năng Nổi Bật (Key Features)

### 📐 1. Trình thiết kế đường cong 2D (2D Curve Editor)
- Vẽ các đường cong mượt mà bằng thuật toán **B-Spline**.
- Tương tác thời gian thực: Click chuột trái để di chuyển điểm, Click chuột phải để xóa, Click chuột giữa để chèn điểm mới (Insert Point) trực tiếp lên đoạn nối.
- **Symmetry Mode (Chế độ Đối Xứng):** Tự động phản chiếu bản vẽ qua trục trung tâm.
- **Animation Engine:** Mô phỏng sự chuyển động nội suy của các tham số $t$ chạy dọc theo chiều dài nét vẽ.

### 🏔️ 2. Trình điêu khắc bề mặt 3D (3D Surface Sculpting)
- Xây dựng mạng lưới bề mặt (Surface Mesh) dựa trên thuật toán **Tensor Product B-Spline**.
- Tương tác nặn hình: Sử dụng chuột phải để chọn vùng và lăn chuột (Scroll) để tăng/giảm cao độ (Trục Y) của bề mặt như đất sét.
- **Seamless 3D Camera:** Tự do xoay (Orbit), di chuyển (Pan) và thu phóng (Zoom) không gian 3 chiều.
- Hiển thị lồng ghép đường cong 2D bay lơ lửng ngay trong không gian 3D.

### 🖥️ 3. Giao Diện CAD Chuyên Nghiệp (Pro UI/UX)
- **ViewBar Tọa Độ:** Hệ thống Dockable Pane nguyên bản của Windows liệt kê tọa độ Real-time của các điểm điều khiển.
- **Native Menu Bar:** Trình đơn Win32 tích hợp hoàn hảo.
- **Axis Triad:** Khung biểu tượng gốc tọa độ X-Y-Z thông minh quay theo camera.
- Menu nổi tùy chỉnh Độ Dày (Width) và Màu Sắc (Color) mượt mà với hiệu ứng pha trộn (Alpha Blending).

---

## 🛠️ Công Nghệ Sử Dụng (Tech Stack)
- **Ngôn ngữ:** C++ (Chuẩn C++11 trở lên)
- **Đồ họa:** Cốt lõi OpenGL (glBegin/glEnd rendering pipeline)
- **Thư viện cửa sổ:** FreeGLUT
- **Giao diện & Hệ thống:** Native Windows API (HWND, HMENU, GDI Font)

---

## 🎮 Hướng Dẫn Cài Đặt & Biên Dịch (How to Build)

Dự án này được thiết kế để biên dịch dễ dàng trên môi trường Windows thông qua `g++` (MinGW-w64).

### Yêu cầu tiên quyết
- Đã cài đặt [MSYS2](https://www.msys2.org/) (hoặc MinGW).
- Thư viện FreeGLUT cho MinGW (`pacman -S mingw-w64-x86_64-freeglut`).

### Biên dịch (Compile)
Mở Terminal/PowerShell tại thư mục chứa code và chạy lệnh:
```powershell
g++ -fdiagnostics-color=always -g -finput-charset=UTF-8 "B_spline.cpp" -o "B_spline.exe" -lfreeglut -lopengl32 -lglu32 -lcomdlg32 -lgdi32
```
*Lưu ý: Thêm `-I` và `-L` trỏ tới đường dẫn include/lib của MinGW nếu trình biên dịch của bạn yêu cầu.*

### Khởi chạy (Run)
```powershell
./B_spline.exe
```

---

## ⌨️ Phím Tắt & Điều Khiển (Controls)

| Thao Tác | Chế Độ 2D | Chế Độ 3D |
|----------|-----------|-----------|
| **Chuột Trái (Kéo)** | Vẽ đường thẳng / Di chuyển điểm | Xoay Camera 3D (Orbit) |
| **Chuột Phải (Click)** | Xóa điểm | Chọn điểm trên lưới bề mặt |
| **Chuột Giữa (Click)** | Chèn điểm điều khiển mới | *Không* |
| **Chuột Giữa (Kéo)** | Di chuyển vùng vẽ (Pan) | Di chuyển Camera (Pan) |
| **Lăn Chuột (Scroll)** | Phóng to/Thu nhỏ (Zoom) | Nâng hạ điểm lưới (Trục Y) |

---
*Phát triển bởi [VoThanhQuan-Pentest](https://github.com/VoThanhQuan-Pentest).*
