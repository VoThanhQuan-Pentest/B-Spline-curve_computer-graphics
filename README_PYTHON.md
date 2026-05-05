# B-Spline Python

Ban nay su dung Python, OpenCV va NumPy. Chuong trinh giu bo cuc chinh cua ban cu: menu, ViewBar, canvas 2D/3D, ve va chinh diem dieu khien B-spline. Ban nay bo sung luong xu ly dung yeu cau de tai:

1. Mo anh chu viet tay.
2. Tach pixel chu va xuat `output/diempixel.dat`.
3. Doc `diempixel.dat`.
4. Tai tao B-spline non-uniform bang least-square approximation.
5. Xuat `output/bsplinecurve.dat` gom `Unum`, `Udegree`, `Uknot`, va cac diem `P4(x, y, z, w)`.

## Chay chuong trinh

```powershell
cd C:\VSCode\DHMT\REcord
python main.py
```

Can cai OpenCV va NumPy:

```powershell
python -m pip install -r requirements.txt
```

OpenCV doc duoc cac dinh dang anh thong dung nhu `PNG`, `JPG/JPEG`, `BMP`.

## Luong lam de tai

Trong app:

1. `File -> Open Image -> diempixel.dat...`
2. Chon anh chu viet tay ro net.
3. De `Auto threshold` bat mac dinh. Voi anh chup nen giay nhieu texture, nen chon `Quality = high`, `Reconstruction = Outline`, `Max points` khoang `9000`.
4. Neu muon duong mot net o giua chu thay vi vien chu, chon `Reconstruction = Centerline`.
5. Chuong trinh tu chuan hoa nen giay, tach pixel, loc nhieu, crop vung chu, lam muot duong vien/skeleton va tai tao cac net B-spline bang least-square.
6. Neu muon chinh lai bac/so diem dieu khien, chon `File -> Least-Square Reconstruction...`.
7. `File -> Export bsplinecurve.dat...`

File `bsplinecurve.dat` duoc ghi theo thu tu:

```text
Unum
Udegree
Uknot0 Uknot1 ...
x0 y0 z0 w0
x1 y1 z1 w1
...
```
