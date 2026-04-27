// B_spline.cpp - Advanced version with Native Windows Menu, 3D Surface, Animation, Symmetry
#define NOMINMAX
#include <windows.h>
#include <GL/freeglut.h>
#include <vector>
#include <cmath>
#include <iostream>
#include <string>
#include <ctime>
#include <fstream>
#include <sstream>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// Define Menu IDs
#define IDM_FILE_LOAD       1001
#define IDM_FILE_SAVE       1002
#define IDM_FILE_SAVE_IMG   1003
#define IDM_FILE_EXIT       1004

#define IDM_EDIT_UNDO       2001
#define IDM_EDIT_CLEAR      2002

#define IDM_VIEW_POLY       3001
#define IDM_VIEW_LABELS     3002
#define IDM_VIEW_GRID       3003
#define IDM_VIEW_SNAP       3004
#define IDM_VIEW_CLOSE      3005
#define IDM_VIEW_SYM        3006
#define IDM_VIEW_ANIM       3007
#define IDM_VIEW_POINTS     3008
#define IDM_VIEW_SURFACE    3009
#define IDM_VIEW_BAR        3010

#define IDM_TOOLS_COLOR     4001
#define IDM_TOOLS_WIDTH     4002

#define IDM_BSPLINE_INC     5001
#define IDM_BSPLINE_DEC     5002

#define IDM_HELP_SHOW       6001

#define IDM_MODE_2D         7001
#define IDM_MODE_3D         7002

struct Point2D {
    float x, y;
    Point2D(float x = 0.0f, float y = 0.0f) : x(x), y(y) {}
    Point2D operator+(const Point2D& other) const { return Point2D(x + other.x, y + other.y); }
    Point2D operator*(float scalar) const { return Point2D(x * scalar, y * scalar); }
    Point2D operator-(const Point2D& other) const { return Point2D(x - other.x, y - other.y); }
};

struct Point3D {
    float x, y, z;
    Point3D(float x = 0.0f, float y = 0.0f, float z = 0.0f) : x(x), y(y), z(z) {}
    Point3D operator+(const Point3D& other) const { return Point3D(x + other.x, y + other.y, z + other.z); }
    Point3D operator*(float scalar) const { return Point3D(x * scalar, y * scalar, z * scalar); }
    Point3D operator-(const Point3D& other) const { return Point3D(x - other.x, y - other.y, z - other.z); }
};

enum AppMode { MODE_2D, MODE_3D };

void drawRoundedRect(float x, float y, float w, float h, float r) {
    int numSegments = 10;
    glBegin(GL_POLYGON);
    for(int i = 0; i <= numSegments; i++) {
        float theta = i * M_PI / (2 * numSegments); 
        glVertex2f(x + w - r + cos(theta)*r, y + h - r + sin(theta)*r);
    }
    for(int i = 0; i <= numSegments; i++) {
        float theta = i * M_PI / (2 * numSegments) + 0.5f * M_PI; 
        glVertex2f(x + r + cos(theta)*r, y + h - r + sin(theta)*r);
    }
    for(int i = 0; i <= numSegments; i++) {
        float theta = i * M_PI / (2 * numSegments) + M_PI; 
        glVertex2f(x + r + cos(theta)*r, y + r + sin(theta)*r);
    }
    for(int i = 0; i <= numSegments; i++) {
        float theta = i * M_PI / (2 * numSegments) + 1.5f * M_PI; 
        glVertex2f(x + w - r + cos(theta)*r, y + r + sin(theta)*r);
    }
    glEnd();
}

HWND hListBox = NULL;
HWND hGroupBox = NULL;

GLuint fontBase = 0;
void buildFontW() {
    HFONT hFont = CreateFontW(-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, 
                              DEFAULT_CHARSET, OUT_TT_PRECIS, CLIP_DEFAULT_PRECIS, 
                              ANTIALIASED_QUALITY, FF_DONTCARE | DEFAULT_PITCH, L"Arial");
    HDC hdc = wglGetCurrentDC();
    HFONT hOldFont = (HFONT)SelectObject(hdc, hFont);
    fontBase = glGenLists(8192);
    wglUseFontBitmapsW(hdc, 0, 8192, fontBase);
    SelectObject(hdc, hOldFont);
    DeleteObject(hFont);
}

void printTextW(float x, float y, const wchar_t* text) {
    if (fontBase == 0) buildFontW();
    glRasterPos2f(x, y);
    glPushAttrib(GL_LIST_BIT);
    glListBase(fontBase);
    glCallLists(wcslen(text), GL_UNSIGNED_SHORT, text);
    glPopAttrib();
}

class BSplineCurve {
private:
    std::vector<std::vector<Point2D>> curves;
    int degree = 3;
    float lineWidth = 3.5f;
    bool drawing = false;
    bool panning = false;
    float lastPanX = 0, lastPanY = 0;
    
    int winW = 1050, winH = 720;
    int vpX = 0, vpW = 1050;
    int viewBarWidth = 200;
    float toolbarHeight = 0.0f;
    unsigned int bgTexture = 0;
    bool hasBG = false;
    bool showHelp = false;

    int selectedStroke = -1;
    int selectedPoint = -1;

    bool isColorMenuOpen = false;
    bool isWidthMenuOpen = false;

    float zoomFactor = 1.0f;
    float panX = 0.0f;
    float panY = 0.0f;

    float curveR = 0.9f, curveG = 0.9f, curveB = 1.0f;
    float pointR = 1.0f, pointG = 0.25f, pointB = 0.25f;

    // --- 3D Surface State ---
    std::vector<std::vector<Point3D>> surfaceGrid;
    int gridU = 5, gridV = 5;
    int degreeU = 3, degreeV = 3;
    float camRotX = 30.0f, camRotY = -45.0f;
    float camDist = 1200.0f;
    float camPanX = 0.0f, camPanY = 0.0f;
    int selGridU = -1, selGridV = -1;
    bool isRotating3D = false;
    bool isPanning3D = false;

    void drawHelpOverlay() const;
    void drawAxisTriad() const;
    void createBackground();
    void drawGrid() const;
    void drawColorMenu() const;
    void drawWidthMenu() const;
    bool processMenuClick(float mx, float my);

    std::vector<Point2D>& getCurrentCurve();
    std::vector<float> generateKnots(int n, int p) const;
    Point2D deBoor(float t, const std::vector<Point2D>& pts, const std::vector<float>& knots) const;
    
    Point3D deBoor1D(float t, int p, const std::vector<Point3D>& pts, const std::vector<float>& knots) const;
    Point3D deBoor3D(float u, float v) const;

public:
    AppMode currentMode = MODE_2D;
    
    bool showPolygon = true;
    bool showPoints = true;
    bool showSurface = true;
    bool showViewBar = true;
    bool showLabels = false;
    bool showGrid = false;
    bool snapToGrid = false;
    bool isClosed = false;
    bool isSymmetric = false;
    bool isAnimating = false;
    float animT = 0.0f;

    BSplineCurve();
    void initSurface();
    void setSize(int w, int h);
    void addPoint(float mx, float my);
    void clear();
    void undo();
    void changeDegree(int d);
    void setColor(int id);
    void saveImage();
    void savePoints();
    void loadPoints();
    void toggleHelp();
    void draw() const;
    
    void handleMouse(int btn, int state, int x, int y);
    void handleMotion(int x, int y);
    void handleMouseWheel(int wheel, int direction, int x, int y);
    void handleKeyboard(unsigned char key, int x, int y);
    void updateAnim();

    void setMode(AppMode m) { currentMode = m; glutPostRedisplay(); }
    void showColorMenu() { isColorMenuOpen = true; isWidthMenuOpen = false; glutPostRedisplay(); }
    void showWidthMenu() { isWidthMenuOpen = true; isColorMenuOpen = false; glutPostRedisplay(); }
    void togglePolygon() { showPolygon = !showPolygon; glutPostRedisplay(); }
    void togglePoints() { showPoints = !showPoints; glutPostRedisplay(); }
    void toggleSurface() { showSurface = !showSurface; glutPostRedisplay(); }
    void toggleViewBar() { showViewBar = !showViewBar; setSize(winW, winH); glutPostRedisplay(); }
    void toggleLabels() { showLabels = !showLabels; glutPostRedisplay(); }
    void toggleGrid() { showGrid = !showGrid; glutPostRedisplay(); }
    void toggleSnap() { snapToGrid = !snapToGrid; glutPostRedisplay(); }
    void toggleClosed() { isClosed = !isClosed; glutPostRedisplay(); }
    void toggleSymmetric() { isSymmetric = !isSymmetric; glutPostRedisplay(); }
    void toggleAnimating() { isAnimating = !isAnimating; glutPostRedisplay(); }

    void updateViewBar() {
        if (!hListBox) return;
        SendMessage(hListBox, LB_RESETCONTENT, 0, 0);
        if (currentMode == MODE_2D) {
            int pCount = 0;
            for (size_t s = 0; s < curves.size(); s++) {
                for (size_t p = 0; p < curves[s].size(); p++) {
                    char buf[64];
                    sprintf(buf, "P%d: (%.1f, %.1f)", pCount++, curves[s][p].x, curves[s][p].y);
                    SendMessageA(hListBox, LB_ADDSTRING, 0, (LPARAM)buf);
                }
            }
        } else {
            for (int i = 0; i < gridU; i++) {
                for (int j = 0; j < gridV; j++) {
                    char buf[64];
                    sprintf(buf, "[%d,%d]: Y=%.1f", i, j, surfaceGrid[i][j].y);
                    SendMessageA(hListBox, LB_ADDSTRING, 0, (LPARAM)buf);
                }
            }
        }
    }

    Point2D screenToWorld(float sx, float sy) const {
        return Point2D((sx - panX) / zoomFactor, (sy - panY) / zoomFactor);
    }
};

BSplineCurve bspline;

BSplineCurve::BSplineCurve() { 
    createBackground(); 
    initSurface();
}

void BSplineCurve::initSurface() {
    surfaceGrid.clear();
    surfaceGrid.resize(gridU, std::vector<Point3D>(gridV));
    float startX = -400.0f;
    float startY = -400.0f;
    float stepX = 800.0f / (gridU - 1);
    float stepY = 800.0f / (gridV - 1);
    for (int i = 0; i < gridU; ++i) {
        for (int j = 0; j < gridV; ++j) {
            surfaceGrid[i][j] = Point3D(startX + i * stepX, 0.0f, startY + j * stepY);
        }
    }
}

void BSplineCurve::updateAnim() {
    if (isAnimating && currentMode == MODE_2D) {
        animT += 0.005f;
        if (animT > 1.0f) animT = 0.0f;
    }
}

void BSplineCurve::setSize(int w, int h) { 
    winW = w; winH = h; 
    vpX = showViewBar ? viewBarWidth : 0;
    vpW = w - vpX;
    if (vpW < 1) vpW = 1;

    if (hListBox && hGroupBox) {
        if (showViewBar) {
            ShowWindow(hGroupBox, SW_SHOW);
            ShowWindow(hListBox, SW_SHOW);
            MoveWindow(hGroupBox, 5, 5, 190, h - 10, TRUE);
            MoveWindow(hListBox, 15, 25, 170, h - 40, TRUE);
        } else {
            ShowWindow(hGroupBox, SW_HIDE);
            ShowWindow(hListBox, SW_HIDE);
        }
    }

    if (currentMode == MODE_2D) {
        glViewport(vpX, 0, vpW, h);
        glMatrixMode(GL_PROJECTION);
        glLoadIdentity();
        gluOrtho2D(0, vpW, 0, h);
        glMatrixMode(GL_MODELVIEW);
        glLoadIdentity();
    } else {
        glViewport(vpX, 0, vpW, h);
        glMatrixMode(GL_PROJECTION);
        glLoadIdentity();
        gluPerspective(45.0, (double)vpW / (double)h, 1.0, 10000.0);
        glMatrixMode(GL_MODELVIEW);
        glLoadIdentity();
    }
}

void BSplineCurve::addPoint(float mx, float my) {
    if (my >= winH - toolbarHeight) return;
    
    Point2D worldPos = screenToWorld(mx, my);
    
    if (snapToGrid) {
        float gridSize = 40.0f;
        worldPos.x = std::round(worldPos.x / gridSize) * gridSize;
        worldPos.y = std::round(worldPos.y / gridSize) * gridSize;
    }

    auto& curr = getCurrentCurve();
    if (!curr.empty()) {
        auto last = curr.back();
        if (std::hypot(last.x - worldPos.x, last.y - worldPos.y) < 6) return;
    }
    curr.emplace_back(worldPos.x, worldPos.y);
    updateViewBar();
}

void BSplineCurve::clear() { 
    if (currentMode == MODE_2D) {
        curves.clear(); 
    } else {
        initSurface();
    }
    updateViewBar();
    glutPostRedisplay(); 
}

void BSplineCurve::undo() { 
    if (currentMode == MODE_2D && !curves.empty()) {
        if (!curves.back().empty()) curves.back().pop_back();
        if (curves.back().empty()) curves.pop_back();
        updateViewBar();
    }
    glutPostRedisplay(); 
}

void BSplineCurve::changeDegree(int d) {
    if (currentMode == MODE_2D) {
        int nd = degree + d;
        if (nd >= 2 && nd <= 5) degree = nd;
    } else {
        int ndU = degreeU + d;
        if (ndU >= 2 && ndU <= 4) { degreeU = ndU; degreeV = ndU; }
    }
    glutPostRedisplay();
}

void BSplineCurve::setColor(int id) {
    switch (id) {
        case 1: curveR=0.1f; curveG=0.6f; curveB=1.0f; break;
        case 2: curveR=0.7f; curveG=0.2f; curveB=0.9f; break;
        case 3: curveR=1.0f; curveG=0.55f; curveB=0.1f; break;
        case 4: curveR=1.0f; curveG=0.3f; curveB=0.7f; break;
        case 5: curveR=0.95f; curveG=0.95f; curveB=1.0f; break;
        case 6: curveR=0.0f; curveG=0.85f; curveB=0.9f; break;
        case 7: curveR=0.9f; curveG=0.1f; curveB=0.85f; break;
        case 8: curveR=1.0f; curveG=0.05f; curveB=0.55f; break;
        case 9: curveR=1.0f; curveG=0.9f; curveB=0.1f; break;
        case 10: curveR=0.95f; curveG=0.1f; curveB=0.15f; break;
        case 11: curveR=0.2f; curveG=0.9f; curveB=0.2f; break;
        case 12: curveR=0.75f; curveG=0.75f; curveB=0.78f; break;
    }
}

void BSplineCurve::saveImage() {
    OPENFILENAMEA ofn;
    char szFile[260] = "bspline.bmp";
    ZeroMemory(&ofn, sizeof(ofn));
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = NULL;
    ofn.lpstrFile = szFile;
    ofn.nMaxFile = sizeof(szFile);
    ofn.lpstrFilter = "Bitmap Images\0*.bmp\0All Files\0*.*\0";
    ofn.nFilterIndex = 1;
    ofn.lpstrDefExt = "bmp";
    ofn.Flags = OFN_PATHMUSTEXIST | OFN_OVERWRITEPROMPT | OFN_NOCHANGEDIR;

    if (GetSaveFileNameA(&ofn) == TRUE) {
        std::string filename = ofn.lpstrFile;
        int dataSize = winW * winH * 3;
        std::vector<unsigned char> pixels(dataSize);
        glReadPixels(0, 0, winW, winH, GL_BGR_EXT, GL_UNSIGNED_BYTE, pixels.data());
        unsigned char bmpFileHeader[14] = {'B','M', 0,0,0,0, 0,0, 0,0, 54,0,0,0};
        unsigned char bmpInfoHeader[40] = {40,0,0,0, 0,0,0,0, 0,0,0,0, 1,0, 24,0};
        int fileSize = 54 + dataSize;
        bmpFileHeader[2] = (unsigned char)(fileSize);
        bmpFileHeader[3] = (unsigned char)(fileSize >> 8);
        bmpFileHeader[4] = (unsigned char)(fileSize >> 16);
        bmpFileHeader[5] = (unsigned char)(fileSize >> 24);
        bmpInfoHeader[4] = (unsigned char)(winW);
        bmpInfoHeader[5] = (unsigned char)(winW >> 8);
        bmpInfoHeader[6] = (unsigned char)(winW >> 16);
        bmpInfoHeader[7] = (unsigned char)(winW >> 24);
        bmpInfoHeader[8] = (unsigned char)(winH);
        bmpInfoHeader[9] = (unsigned char)(winH >> 8);
        bmpInfoHeader[10] = (unsigned char)(winH >> 16);
        bmpInfoHeader[11] = (unsigned char)(winH >> 24);
        std::ofstream file(filename, std::ios::binary);
        if(file) {
            file.write((char*)bmpFileHeader, 14);
            file.write((char*)bmpInfoHeader, 40);
            file.write((char*)pixels.data(), dataSize);
            file.close();
            std::cout << "[SAVE IMG] Luu thanh cong: " << filename << "\n";
        }
    }
}

void BSplineCurve::savePoints() {
    if (currentMode == MODE_3D) {
        std::cout << "[SAVE] Tinh nang Save hien chi ho tro 2D.\n";
        return;
    }
    OPENFILENAMEA ofn;
    char szFile[260] = "points.txt";
    ZeroMemory(&ofn, sizeof(ofn));
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = NULL;
    ofn.lpstrFile = szFile;
    ofn.nMaxFile = sizeof(szFile);
    ofn.lpstrFilter = "Text Files\0*.txt\0All Files\0*.*\0";
    ofn.nFilterIndex = 1;
    ofn.lpstrDefExt = "txt";
    ofn.Flags = OFN_PATHMUSTEXIST | OFN_OVERWRITEPROMPT | OFN_NOCHANGEDIR;

    if (GetSaveFileNameA(&ofn) == TRUE) {
        std::string filename = ofn.lpstrFile;
        std::ofstream f(filename);
        if (!f) return;
        f << "# B-Spline Multi-Stroke - degree " << degree << "\n";
        for (size_t s = 0; s < curves.size(); s++) {
            for (auto& p : curves[s]) f << s << " " << p.x << " " << p.y << "\n";
        }
        f.close();
        std::cout << "[SAVE TXT] Luu file thanh cong: " << filename << "\n";
    }
}

void BSplineCurve::loadPoints() {
    if (currentMode == MODE_3D) return;
    OPENFILENAMEA ofn;
    char szFile[260] = {0};
    ZeroMemory(&ofn, sizeof(ofn));
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = NULL;
    ofn.lpstrFile = szFile;
    ofn.nMaxFile = sizeof(szFile);
    ofn.lpstrFilter = "Text Files\0*.txt\0All Files\0*.*\0";
    ofn.nFilterIndex = 1;
    ofn.Flags = OFN_PATHMUSTEXIST | OFN_FILEMUSTEXIST | OFN_NOCHANGEDIR;

    if (GetOpenFileNameA(&ofn) == TRUE) {
        std::string filename = ofn.lpstrFile;
        std::ifstream f(filename);
        if (!f) { std::cout << "[LOAD] Khong the mo file: " << filename << "\n"; return; }
        curves.clear();
        std::string line; int c = 0, lastStroke = -1;
        while (std::getline(f, line)) {
            if (line.empty() || line[0] == '#') continue;
            std::istringstream is(line);
            int strokeId; float x, y;
            if (is >> strokeId >> x >> y) {
                if (strokeId != lastStroke) {
                    curves.emplace_back();
                    lastStroke = strokeId;
                }
                curves.back().emplace_back(x, y);
                c++;
            }
        }
        std::cout << "[LOAD TXT] Da load " << curves.size() << " net ve tu " << filename << "\n";
        updateViewBar();
        glutPostRedisplay();
    }
}

void BSplineCurve::drawColorMenu() const {
    if (!isColorMenuOpen) return;
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,vpW,0,winH);
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity();

    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    glColor4f(0.1f, 0.1f, 0.15f, 0.95f);
    float startX = vpW / 2 - 130, startY = winH / 2 - 100;
    drawRoundedRect(startX, startY, 260, 200, 10.0f);
    glDisable(GL_BLEND);

    glColor3f(1, 1, 1);
    printTextW(startX + 60, startY + 175, L"=== CHỌN MÀU (COLOR) ===");

    for (int i=1; i<=12; i++) {
        float r=0, g=0, b=0;
        switch (i) {
            case 1: r=0.1f; g=0.6f; b=1.0f; break; case 2: r=0.7f; g=0.2f; b=0.9f; break;
            case 3: r=1.0f; g=0.55f; b=0.1f; break; case 4: r=1.0f; g=0.3f; b=0.7f; break;
            case 5: r=0.95f; g=0.95f; b=1.0f; break; case 6: r=0.0f; g=0.85f; b=0.9f; break;
            case 7: r=0.9f; g=0.1f; b=0.85f; break; case 8: r=1.0f; g=0.05f; b=0.55f; break;
            case 9: r=1.0f; g=0.9f; b=0.1f; break; case 10: r=0.95f; g=0.1f; b=0.15f; break;
            case 11: r=0.2f; g=0.9f; b=0.2f; break; case 12: r=0.75f; g=0.75f; b=0.78f; break;
        }
        glColor3f(r, g, b);
        int col = (i-1) % 4, row = (i-1) / 4;
        float bx = startX + 20 + col * 55, by = startY + 120 - row * 50;
        drawRoundedRect(bx, by, 40, 35, 4.0f);
    }
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW);
}

void BSplineCurve::drawWidthMenu() const {
    if (!isWidthMenuOpen) return;
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,vpW,0,winH);
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity();

    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    glColor4f(0.1f, 0.1f, 0.15f, 0.95f);
    float startX = vpW / 2 - 130, startY = winH / 2 - 100;
    drawRoundedRect(startX, startY, 260, 200, 10.0f);
    glDisable(GL_BLEND);

    glColor3f(1, 1, 1);
    printTextW(startX + 50, startY + 175, L"=== CHỌN ĐỘ DÀY (WIDTH) ===");

    float widths[] = {2.0, 3.5, 5.0, 6.5, 8.0, 10.0};
    for (int i=0; i<6; i++) {
        int col = i % 3, row = i / 3;
        float bx = startX + 20 + col * 75, by = startY + 100 - row * 70;
        glColor3f(0.2f, 0.4f, 0.7f); drawRoundedRect(bx, by, 60, 45, 4.0f);
        glColor3f(1, 1, 1);
        std::string wStr = std::to_string(widths[i]).substr(0, 3);
        glRasterPos2f(bx + 18, by + 18);
        for (char c : wStr) glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, c);
    }
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW);
}

bool BSplineCurve::processMenuClick(float mx, float my) {
    if (isColorMenuOpen) {
        float startX = vpW / 2 - 130, startY = winH / 2 - 100;
        if (mx < startX || mx > startX + 260 || my < startY || my > startY + 200) { isColorMenuOpen = false; return true; }
        for (int i=1; i<=12; i++) {
            int col = (i-1) % 4, row = (i-1) / 4;
            float bx = startX + 20 + col * 55, by = startY + 120 - row * 50;
            if (mx >= bx && mx <= bx+40 && my >= by && my <= by+35) { setColor(i); isColorMenuOpen = false; return true; }
        }
        return true;
    }
    if (isWidthMenuOpen) {
        float startX = vpW / 2 - 130, startY = winH / 2 - 100;
        if (mx < startX || mx > startX + 260 || my < startY || my > startY + 200) { isWidthMenuOpen = false; return true; }
        float widths[] = {2.0, 3.5, 5.0, 6.5, 8.0, 10.0};
        for (int i=0; i<6; i++) {
            int col = i % 3, row = i / 3;
            float bx = startX + 20 + col * 75, by = startY + 100 - row * 70;
            if (mx >= bx && mx <= bx+60 && my >= by && my <= by+45) { lineWidth = widths[i]; isWidthMenuOpen = false; return true; }
        }
        return true;
    }
    return false;
}

void BSplineCurve::createBackground() {
    if (hasBG) glDeleteTextures(1, &bgTexture);
    glGenTextures(1, &bgTexture);
    glBindTexture(GL_TEXTURE_2D, bgTexture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    int w = 512, h = 512;
    std::vector<unsigned char> data(w*h*3);
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            int i = (y*w + x)*3;
            data[i] = 12; data[i+1] = 28 + (y*160)/h; data[i+2] = 45 + (x*70)/w;
        }
    }
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, data.data());
    hasBG = true;
}

void BSplineCurve::toggleHelp() {
    showHelp = !showHelp;
    std::cout << "[HELP] Trang thai bang huong dan: " << (showHelp ? "MO" : "DONG") << "\n";
    glutPostRedisplay();
}

std::vector<Point2D>& BSplineCurve::getCurrentCurve() {
    if (curves.empty()) curves.emplace_back();
    return curves.back();
}

std::vector<float> BSplineCurve::generateKnots(int n, int p) const {
    if (n < p) return {};
    int nk = n + p + 2;
    std::vector<float> k(nk, 0.0f);
    for (int i = 0; i <= p; i++) k[i] = 0.0f, k[nk-1-i] = 1.0f;
    float d = static_cast<float>(n - p + 1);
    for (int i = 1; i <= n - p; i++) k[p + i] = static_cast<float>(i) / d;
    return k;
}

Point2D BSplineCurve::deBoor(float t, const std::vector<Point2D>& pts, const std::vector<float>& knots) const {
    int n = pts.size() - 1; int p = degree;
    if (n < p) return pts.empty() ? Point2D(winW/2.0f, winH/2.0f) : pts[0];
    t = std::max(0.0f, std::min(1.0f, t));
    int k = p;
    for (int i = p; i <= n; i++) if (t < knots[i+1]) { k = i; break; }
    if (t >= knots[n+1]) k = n;
    std::vector<Point2D> d(p+1);
    for (int i = 0; i <= p; i++) d[i] = pts[k-p+i];
    for (int r = 1; r <= p; r++) {
        for (int j = p; j >= r; j--) {
            int i = k - p + j;
            float den = knots[i+p+1-r] - knots[i];
            float alpha = (den > 0.0001f) ? (t - knots[i]) / den : 0.0f;
            d[j] = d[j-1]*(1-alpha) + d[j]*alpha;
        }
    }
    return d[p];
}

Point3D BSplineCurve::deBoor1D(float t, int p, const std::vector<Point3D>& pts, const std::vector<float>& knots) const {
    int n = pts.size() - 1;
    if (n < p) return pts.empty() ? Point3D() : pts[0];
    t = std::max(0.0f, std::min(1.0f, t));
    int k = p;
    for (int i = p; i <= n; i++) if (t < knots[i+1]) { k = i; break; }
    if (t >= knots[n+1]) k = n;
    std::vector<Point3D> d(p+1);
    for (int i = 0; i <= p; i++) d[i] = pts[k-p+i];
    for (int r = 1; r <= p; r++) {
        for (int j = p; j >= r; j--) {
            int i = k - p + j;
            float den = knots[i+p+1-r] - knots[i];
            float alpha = (den > 0.0001f) ? (t - knots[i]) / den : 0.0f;
            d[j] = d[j-1]*(1-alpha) + d[j]*alpha;
        }
    }
    return d[p];
}

Point3D BSplineCurve::deBoor3D(float u, float v) const {
    auto knotsU = generateKnots(gridU - 1, degreeU);
    auto knotsV = generateKnots(gridV - 1, degreeV);
    if (knotsU.empty() || knotsV.empty()) return Point3D();

    std::vector<Point3D> temp(gridU);
    for (int i = 0; i < gridU; i++) {
        temp[i] = deBoor1D(v, degreeV, surfaceGrid[i], knotsV);
    }
    return deBoor1D(u, degreeU, temp, knotsU);
}

void BSplineCurve::drawGrid() const {
    if (!showGrid) return;
    glColor3f(0.2f, 0.2f, 0.3f);
    glLineWidth(1.0f);
    glBegin(GL_LINES);
    float gridSize = 40.0f;
    for (float x = -2000; x < 3000; x += gridSize) { glVertex2f(x, -2000); glVertex2f(x, 3000); }
    for (float y = -2000; y < 3000; y += gridSize) { glVertex2f(-2000, y); glVertex2f(3000, y); }
    glEnd();
}

void BSplineCurve::drawHelpOverlay() const {
    if (!showHelp) return;
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0,vpW,0,winH);
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity();

    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    glColor4f(0.0f, 0.0f, 0.0f, 0.9f);
    glBegin(GL_QUADS);
    glVertex2f(60, 80); glVertex2f(vpW - 60, 80);
    glVertex2f(vpW - 60, winH - 60); glVertex2f(60, winH - 60);
    glEnd(); glDisable(GL_BLEND);

    glColor3f(0.4f, 0.7f, 1.0f); glLineWidth(5);
    glBegin(GL_LINE_LOOP);
    glVertex2f(60, 80); glVertex2f(vpW - 60, 80);
    glVertex2f(vpW - 60, winH - 60); glVertex2f(60, winH - 60);
    glEnd(); glLineWidth(1);

    glColor3f(1.0f, 1.0f, 1.0f);
    int y = winH - 110;
    const wchar_t* lines[] = {
        L"=== HƯỚNG DẪN SỬ DỤNG B-SPLINE NÂNG CAO ===", L"",
        L"[CHẾ ĐỘ 2D CURVE]",
        L"- CLICK TRÁI + KÉO       : Vẽ đường B-Spline",
        L"- CLICK TRÁI vào điểm    : DI CHUYỂN điểm điều khiển",
        L"- CLICK PHẢI vào điểm    : XÓA điểm đó",
        L"- CLICK CHUỘT GIỮA       : CHÈN điểm vào giữa đoạn nét đứt",
        L"- GIỮ CHUỘT GIỮA + KÉO   : Pan màn hình, LĂN CHUỘT : Zoom",
        L"",
        L"[CHẾ ĐỘ 3D SURFACE]",
        L"- GIỮ CHUỘT TRÁI + KÉO   : Xoay Camera 3D (Orbit)",
        L"- GIỮ CHUỘT GIỮA + KÉO   : Di chuyển Camera 3D (Pan)",
        L"- LĂN CHUỘT              : Phóng to/Thu nhỏ Camera 3D",
        L"- CLICK PHẢI vào lưới    : Chọn điểm điều khiển trên mặt cong",
        L"- LĂN CHUỘT trên điểm    : Nâng lên / Hạ xuống điểm đã chọn (Trục Y)",
        L"",
        L"[THANH MENU WINDOWS Ở TRÊN CÙNG]",
        L"- Chứa các lệnh chuyển Mode, bật Đối Xứng (Symmetry), Animation...",
        L"Nhấn ESC hoặc Click để đóng bảng này."
    };
    for (auto line : lines) { printTextW(90, y, line); y -= 22; }
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW);
}

void BSplineCurve::drawAxisTriad() const {
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); 
    glOrtho(0, vpW, 0, winH, -1000.0, 1000.0);
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity();
    
    float ax = 60.0f, ay = 60.0f, len = 40.0f;
    glDisable(GL_DEPTH_TEST);
    glLineWidth(2.0f);
    
    // Origin
    glColor3f(0.0f, 0.0f, 1.0f); glPointSize(8.0f);
    glBegin(GL_POINTS); glVertex2f(ax, ay); glEnd();
    
    if (currentMode == MODE_2D) {
        // Red X
        glColor3f(1.0f, 0.0f, 0.0f);
        glBegin(GL_LINES); glVertex2f(ax, ay); glVertex2f(ax + len, ay); glEnd();
        glBegin(GL_TRIANGLES); glVertex2f(ax + len + 5, ay); glVertex2f(ax + len, ay + 3); glVertex2f(ax + len, ay - 3); glEnd();
        glRasterPos2f(ax + len + 10, ay - 4); glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, 'X');
        // Green Y
        glColor3f(0.0f, 1.0f, 0.0f);
        glBegin(GL_LINES); glVertex2f(ax, ay); glVertex2f(ax, ay + len); glEnd();
        glBegin(GL_TRIANGLES); glVertex2f(ax, ay + len + 5); glVertex2f(ax - 3, ay + len); glVertex2f(ax + 3, ay + len); glEnd();
        glRasterPos2f(ax - 4, ay + len + 10); glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, 'Y');
    } else {
        glTranslatef(ax, ay, 0);
        glRotatef(camRotX, 1.0f, 0.0f, 0.0f);
        glRotatef(camRotY, 0.0f, 1.0f, 0.0f);
        // Red X
        glColor3f(1.0f, 0.0f, 0.0f);
        glBegin(GL_LINES); glVertex3f(0,0,0); glVertex3f(len,0,0); glEnd();
        glRasterPos3f(len+5, 0, 0); glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, 'X');
        // Green Y
        glColor3f(0.0f, 1.0f, 0.0f);
        glBegin(GL_LINES); glVertex3f(0,0,0); glVertex3f(0,len,0); glEnd();
        glRasterPos3f(0, len+5, 0); glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, 'Y');
        // Blue Z
        glColor3f(0.0f, 0.5f, 1.0f);
        glBegin(GL_LINES); glVertex3f(0,0,0); glVertex3f(0,0,len); glEnd();
        glRasterPos3f(0, 0, len+5); glutBitmapCharacter(GLUT_BITMAP_HELVETICA_12, 'Z');
    }
    
    glPopMatrix(); glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW);
}

void BSplineCurve::draw() const {
    glClearColor(0.05f, 0.05f, 0.15f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

    auto drawCore = [&](bool isMirrored) {
        if (showPolygon) {
            glColor3f(0.4f, 0.4f, 0.5f); glEnable(GL_LINE_STIPPLE); glLineStipple(1, 0xAAAA);
            for (const auto& stroke : curves) {
                if (stroke.size() < 2) continue;
                glBegin(GL_LINE_STRIP);
                for (const auto& p : stroke) glVertex2f(p.x, p.y);
                if (isClosed && stroke.size() > 2) glVertex2f(stroke[0].x, stroke[0].y);
                glEnd();
            }
            glDisable(GL_LINE_STIPPLE);
        }
        if (showPoints) {
            glPointSize(10); glColor3f(pointR, pointG, pointB);
        }
        int strokeIdx = 0;
        for (const auto& stroke : curves) {
            int pointIdx = 0;
            for (const auto& p : stroke) {
                if (showPoints) {
                    if (strokeIdx == selectedStroke && pointIdx == selectedPoint && !isMirrored && currentMode == MODE_2D) {
                        glColor3f(1.0f, 1.0f, 0.0f); glBegin(GL_POINTS); glVertex2f(p.x, p.y); glEnd();
                        glColor3f(pointR, pointG, pointB);
                    } else { glBegin(GL_POINTS); glVertex2f(p.x, p.y); glEnd(); }
                }
                
                if (showLabels && !isMirrored) {
                    glColor3f(0.8f, 0.8f, 0.8f); std::string label = "P" + std::to_string(pointIdx);
                    glRasterPos2f(p.x + 8 / zoomFactor, p.y + 8 / zoomFactor);
                    for (char c : label) glutBitmapCharacter(GLUT_BITMAP_8_BY_13, c);
                    glColor3f(pointR, pointG, pointB);
                }
                pointIdx++;
            }
            strokeIdx++;
        }
        glColor3f(curveR, curveG, curveB); glLineWidth(lineWidth);
        for (const auto& stroke : curves) {
            std::vector<Point2D> drawStroke = stroke;
            if (isClosed && drawStroke.size() > degree) { for(int i = 0; i < degree; i++) drawStroke.push_back(stroke[i]); }
            if (drawStroke.size() < degree + 1) continue;
            auto knots = generateKnots(drawStroke.size() - 1, degree);
            if (knots.empty()) continue;
            
            glBegin(GL_LINE_STRIP);
            for (int i = 0; i <= 900; i++) {
                float t = i / 900.0f;
                auto pt = deBoor(t, drawStroke, knots);
                glVertex2f(pt.x, pt.y);
            }
            glEnd();

            if (isAnimating) {
                auto ptAnim = deBoor(animT, drawStroke, knots);
                glColor3f(1.0f, 0.0f, 0.0f);
                glPointSize(15.0f);
                glBegin(GL_POINTS); glVertex2f(ptAnim.x, ptAnim.y); glEnd();
                glColor3f(curveR, curveG, curveB);
            }
        }
        glLineWidth(1.0f);
    };

    if (currentMode == MODE_2D) {
        if (hasBG) {
            glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, bgTexture); glColor3f(1,1,1);
            glBegin(GL_QUADS);
            glTexCoord2f(0,0); glVertex2f(0, 0); glTexCoord2f(1,0); glVertex2f(vpW, 0);
            glTexCoord2f(1,1); glVertex2f(vpW, winH - toolbarHeight); glTexCoord2f(0,1); glVertex2f(0, winH - toolbarHeight);
            glEnd(); glDisable(GL_TEXTURE_2D);
        }

        glPushMatrix(); 
        glTranslatef(panX, panY, 0.0f); 
        glScalef(zoomFactor, zoomFactor, 1.0f);
        
        drawGrid();

        if (isSymmetric) {
            glColor3f(1.0f, 0.3f, 0.3f); glLineWidth(2.0f);
            glBegin(GL_LINES); 
            float centerX = (vpW/2.0f - panX) / zoomFactor;
            glVertex2f(centerX, -2000); 
            glVertex2f(centerX, 3000); 
            glEnd();
        }



        drawCore(false);

        if (isSymmetric) {
            glPushMatrix();
            float centerX = (winW/2.0f - panX) / zoomFactor;
            glTranslatef(centerX, 0, 0); 
            glScalef(-1, 1, 1); 
            glTranslatef(-centerX, 0, 0);
            drawCore(true);
            glPopMatrix();
        }

        glPopMatrix();

    } else {
        // --- MODE 3D SURFACE ---
        glEnable(GL_DEPTH_TEST);
        glPushMatrix();
        glTranslatef(camPanX, camPanY, -camDist);
        glRotatef(camRotX, 1.0f, 0.0f, 0.0f);
        glRotatef(camRotY, 0.0f, 1.0f, 0.0f);

        if (showGrid) {
            glColor3f(0.3f, 0.3f, 0.3f);
            glBegin(GL_LINES);
            for(float i=-1000; i<=1000; i+=100) {
                glVertex3f(i, -200, -1000); glVertex3f(i, -200, 1000);
                glVertex3f(-1000, -200, i); glVertex3f(1000, -200, i);
            }
            glEnd();
        }

        if (showPolygon) {
            glColor3f(0.5f, 0.5f, 0.6f);
            glLineWidth(1.5f);
            for (int i = 0; i < gridU; i++) {
                glBegin(GL_LINE_STRIP);
                for (int j = 0; j < gridV; j++) glVertex3f(surfaceGrid[i][j].x, surfaceGrid[i][j].y, surfaceGrid[i][j].z);
                glEnd();
            }
            for (int j = 0; j < gridV; j++) {
                glBegin(GL_LINE_STRIP);
                for (int i = 0; i < gridU; i++) glVertex3f(surfaceGrid[i][j].x, surfaceGrid[i][j].y, surfaceGrid[i][j].z);
                glEnd();
            }
        }

        if (showPoints) {
            glPointSize(10.0f);
            for (int i = 0; i < gridU; i++) {
                for (int j = 0; j < gridV; j++) {
                    if (i == selGridU && j == selGridV) glColor3f(1.0f, 1.0f, 0.0f);
                    else glColor3f(pointR, pointG, pointB);
                    glBegin(GL_POINTS); glVertex3f(surfaceGrid[i][j].x, surfaceGrid[i][j].y, surfaceGrid[i][j].z); glEnd();
                }
            }
        }

        if (showSurface) {
            glColor3f(curveR, curveG, curveB);
            glLineWidth(2.0f);
            int resolution = 40;
            for (int i = 0; i < resolution; i++) {
                glBegin(GL_LINE_STRIP);
                for (int j = 0; j <= resolution; j++) {
                    float u = (float)i / resolution;
                    float v = (float)j / resolution;
                    Point3D p = deBoor3D(u, v);
                    glVertex3f(p.x, p.y, p.z);
                }
                glEnd();
            }
            for (int j = 0; j < resolution; j++) {
                glBegin(GL_LINE_STRIP);
                for (int i = 0; i <= resolution; i++) {
                    float u = (float)i / resolution;
                    float v = (float)j / resolution;
                    Point3D p = deBoor3D(u, v);
                    glVertex3f(p.x, p.y, p.z);
                }
                glEnd();
            }
        }

        // Draw 2D Curves in 3D Space (Floating above the 3D surface)
        glPushMatrix();
        glTranslatef(-vpW / 2.0f, 0.0f, -winH / 2.0f); // Center the 2D drawing to the 3D origin
        glRotatef(90.0f, 1.0f, 0.0f, 0.0f);             // Lay it flat on the X-Z plane (optional, but looks better)
        
        drawCore(false);

        if (isSymmetric) {
            glPushMatrix();
            float centerX = (vpW/2.0f - panX) / zoomFactor;
            glTranslatef(centerX, 0, 0); 
            glScalef(-1, 1, 1); 
            glTranslatef(-centerX, 0, 0);
            drawCore(true);
            glPopMatrix();
        }
        glPopMatrix();

        glPopMatrix();
        glDisable(GL_DEPTH_TEST);
    }

    drawAxisTriad();
    drawColorMenu();
    drawWidthMenu();
    drawHelpOverlay();
    glutSwapBuffers();
}

void BSplineCurve::handleMouse(int btn, int state, int x, int y) {
    if (showViewBar && x < viewBarWidth) return;
    
    float mx = x;
    if (showViewBar) mx -= viewBarWidth;
    float my = winH - y;

    if (showHelp) { if (state == GLUT_DOWN) toggleHelp(); glutPostRedisplay(); return; }
    if (state == GLUT_DOWN && processMenuClick(mx, my)) { glutPostRedisplay(); return; }

    if (currentMode == MODE_2D) {
        Point2D worldPos = screenToWorld(mx, my);
        if (btn == GLUT_LEFT_BUTTON) {
            if (state == GLUT_DOWN) {
                selectedStroke = -1; selectedPoint = -1;
                float threshold = 12.0f / zoomFactor; 
                for (size_t s = 0; s < curves.size(); ++s) {
                    for (size_t p = 0; p < curves[s].size(); ++p) {
                        float dist = std::hypot(curves[s][p].x - worldPos.x, curves[s][p].y - worldPos.y);
                        if (dist < threshold) { selectedStroke = s; selectedPoint = p; break; }
                    }
                    if (selectedStroke != -1) break;
                }
                if (selectedStroke == -1) { drawing = true; addPoint(mx, my); }
            } else if (state == GLUT_UP) { drawing = false; selectedStroke = -1; selectedPoint = -1; }
        } 
        else if (btn == GLUT_RIGHT_BUTTON && state == GLUT_DOWN) {
            float threshold = 12.0f / zoomFactor; bool deleted = false;
            for (size_t s = 0; s < curves.size(); ++s) {
                for (size_t p = 0; p < curves[s].size(); ++p) {
                    float dist = std::hypot(curves[s][p].x - worldPos.x, curves[s][p].y - worldPos.y);
                    if (dist < threshold) { curves[s].erase(curves[s].begin() + p); deleted = true; break; }
                }
                if (deleted) break;
            }
            if (!deleted && (curves.empty() || !curves.back().empty())) curves.emplace_back();
            updateViewBar();
        }
        else if (btn == 1 /*GLUT_MIDDLE_BUTTON*/) { 
            if (state == GLUT_DOWN) {
                bool inserted = false; float insertThreshold = 15.0f / zoomFactor;
                for (size_t s = 0; s < curves.size(); ++s) {
                    if (curves[s].size() < 2) continue;
                    for (size_t p = 0; p < curves[s].size() - 1; ++p) {
                        Point2D p1 = curves[s][p], p2 = curves[s][p+1];
                        float l2 = std::pow(p2.x - p1.x, 2) + std::pow(p2.y - p1.y, 2);
                        float t = std::max(0.0f, std::min(1.0f, ((worldPos.x - p1.x) * (p2.x - p1.x) + (worldPos.y - p1.y) * (p2.y - p1.y)) / l2));
                        Point2D proj(p1.x + t * (p2.x - p1.x), p1.y + t * (p2.y - p1.y));
                        float dist = std::hypot(worldPos.x - proj.x, worldPos.y - proj.y);
                        if (dist < insertThreshold) { curves[s].insert(curves[s].begin() + p + 1, worldPos); inserted = true; break; }
                    }
                    if (inserted) break;
                }
                if (!inserted) { panning = true; lastPanX = mx; lastPanY = my; }
                else { updateViewBar(); }
            } else if (state == GLUT_UP) { panning = false; }
        }
    } else {
        // --- 3D Mouse Handling ---
        if (btn == GLUT_LEFT_BUTTON) {
            if (state == GLUT_DOWN) { isRotating3D = true; lastPanX = mx; lastPanY = my; }
            else if (state == GLUT_UP) { isRotating3D = false; }
        } else if (btn == 1 /* MIDDLE */) {
            if (state == GLUT_DOWN) { isPanning3D = true; lastPanX = mx; lastPanY = my; }
            else if (state == GLUT_UP) { isPanning3D = false; }
        } else if (btn == GLUT_RIGHT_BUTTON && state == GLUT_DOWN) {
            GLint viewport[4]; GLdouble modelview[16], projection[16];
            glGetIntegerv(GL_VIEWPORT, viewport);
            glGetDoublev(GL_MODELVIEW_MATRIX, modelview);
            glGetDoublev(GL_PROJECTION_MATRIX, projection);
            
            float minDist = 99999.0f;
            selGridU = -1; selGridV = -1;
            for (int i = 0; i < gridU; i++) {
                for (int j = 0; j < gridV; j++) {
                    GLdouble sx, sy, sz;
                    gluProject(surfaceGrid[i][j].x, surfaceGrid[i][j].y, surfaceGrid[i][j].z, 
                               modelview, projection, viewport, &sx, &sy, &sz);
                    float dx = sx - mx; float dy = sy - my;
                    float dist = std::sqrt(dx*dx + dy*dy);
                    if (dist < 20.0f && dist < minDist) { minDist = dist; selGridU = i; selGridV = j; }
                }
            }
        }
    }
    glutPostRedisplay();
}

void BSplineCurve::handleMotion(int x, int y) {
    if (showViewBar && x < viewBarWidth) return;
    
    float mx = x;
    if (showViewBar) mx -= viewBarWidth;
    float my = winH - y;
    
    if (currentMode == MODE_2D) {
        if (panning) { panX += (mx - lastPanX); panY += (my - lastPanY); lastPanX = mx; lastPanY = my; }
        else if (selectedStroke != -1 && selectedPoint != -1) {
            Point2D worldPos = screenToWorld(mx, my);
            if (snapToGrid) {
                float gridSize = 40.0f;
                worldPos.x = std::round(worldPos.x / gridSize) * gridSize;
                worldPos.y = std::round(worldPos.y / gridSize) * gridSize;
            }
            curves[selectedStroke][selectedPoint].x = worldPos.x;
            curves[selectedStroke][selectedPoint].y = worldPos.y;
            updateViewBar();
        } 
        else if (drawing) { addPoint(mx, my); }
    } else {
        if (isRotating3D) {
            camRotY += (mx - lastPanX) * 0.5f;
            camRotX -= (my - lastPanY) * 0.5f;
            lastPanX = mx; lastPanY = my;
        } else if (isPanning3D) {
            camPanX += (mx - lastPanX);
            camPanY += (my - lastPanY);
            lastPanX = mx; lastPanY = my;
        }
    }
    glutPostRedisplay();
}

void BSplineCurve::handleMouseWheel(int wheel, int direction, int x, int y) {
    if (showViewBar && x < viewBarWidth) return;
    
    float mx = x;
    if (showViewBar) mx -= viewBarWidth;
    float my = winH - y;
    
    if (currentMode == MODE_2D) {
        float worldX_before = (mx - panX) / zoomFactor, worldY_before = (my - panY) / zoomFactor;
        if (direction > 0) zoomFactor *= 1.1f; else zoomFactor /= 1.1f;
        if (zoomFactor < 0.1f) zoomFactor = 0.1f; if (zoomFactor > 10.0f) zoomFactor = 10.0f;
        panX = mx - worldX_before * zoomFactor; panY = my - worldY_before * zoomFactor;
    } else {
        if (selGridU != -1 && selGridV != -1) {
            surfaceGrid[selGridU][selGridV].y += direction * 30.0f;
            updateViewBar();
        } else {
            camDist -= direction * 100.0f;
            if (camDist < 10.0f) camDist = 10.0f;
        }
    }
    glutPostRedisplay();
}

void BSplineCurve::handleKeyboard(unsigned char key, int x, int y) {
    if (key == 27) { if (showHelp) toggleHelp(); else glutLeaveMainLoop(); }
}

// WIN32 MENU
WNDPROC oldWndProc;

void updateMenuChecks(HWND hwnd) {
    HMENU hMenu = GetMenu(hwnd);
    if (!hMenu) return;
    CheckMenuItem(hMenu, IDM_VIEW_POLY, MF_BYCOMMAND | (bspline.showPolygon ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(hMenu, IDM_VIEW_POINTS, MF_BYCOMMAND | (bspline.showPoints ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(hMenu, IDM_VIEW_SURFACE, MF_BYCOMMAND | (bspline.showSurface ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(hMenu, IDM_VIEW_BAR, MF_BYCOMMAND | (bspline.showViewBar ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(hMenu, IDM_VIEW_LABELS, MF_BYCOMMAND | (bspline.showLabels ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(hMenu, IDM_VIEW_GRID, MF_BYCOMMAND | (bspline.showGrid ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(hMenu, IDM_VIEW_SNAP, MF_BYCOMMAND | (bspline.snapToGrid ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(hMenu, IDM_VIEW_CLOSE, MF_BYCOMMAND | (bspline.isClosed ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(hMenu, IDM_VIEW_SYM, MF_BYCOMMAND | (bspline.isSymmetric ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(hMenu, IDM_VIEW_ANIM, MF_BYCOMMAND | (bspline.isAnimating ? MF_CHECKED : MF_UNCHECKED));
    
    CheckMenuItem(hMenu, IDM_MODE_2D, MF_BYCOMMAND | (bspline.currentMode == MODE_2D ? MF_CHECKED : MF_UNCHECKED));
    CheckMenuItem(hMenu, IDM_MODE_3D, MF_BYCOMMAND | (bspline.currentMode == MODE_3D ? MF_CHECKED : MF_UNCHECKED));
}

LRESULT CALLBACK MyWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    if (msg == WM_SIZE && hListBox && hGroupBox) {
        if (bspline.showViewBar) {
            int h = HIWORD(lParam);
            MoveWindow(hGroupBox, 5, 5, 190, h - 10, TRUE);
            MoveWindow(hListBox, 15, 25, 170, h - 40, TRUE);
        }
    }
    if (msg == WM_COMMAND) {
        int id = LOWORD(wParam);
        switch (id) {
            case IDM_FILE_LOAD: bspline.loadPoints(); break;
            case IDM_FILE_SAVE: bspline.savePoints(); break;
            case IDM_FILE_SAVE_IMG: bspline.saveImage(); break;
            case IDM_FILE_EXIT: glutLeaveMainLoop(); break;
            
            case IDM_EDIT_UNDO: bspline.undo(); break;
            case IDM_EDIT_CLEAR: bspline.clear(); break;
            
            case IDM_VIEW_POLY: bspline.togglePolygon(); updateMenuChecks(hwnd); break;
            case IDM_VIEW_POINTS: bspline.togglePoints(); updateMenuChecks(hwnd); break;
            case IDM_VIEW_SURFACE: bspline.toggleSurface(); updateMenuChecks(hwnd); break;
            case IDM_VIEW_BAR: bspline.toggleViewBar(); updateMenuChecks(hwnd); break;
            case IDM_VIEW_LABELS: bspline.toggleLabels(); updateMenuChecks(hwnd); break;
            case IDM_VIEW_GRID: bspline.toggleGrid(); updateMenuChecks(hwnd); break;
            case IDM_VIEW_SNAP: bspline.toggleSnap(); updateMenuChecks(hwnd); break;
            case IDM_VIEW_CLOSE: bspline.toggleClosed(); updateMenuChecks(hwnd); break;
            case IDM_VIEW_SYM: bspline.toggleSymmetric(); updateMenuChecks(hwnd); break;
            case IDM_VIEW_ANIM: bspline.toggleAnimating(); updateMenuChecks(hwnd); break;
            
            case IDM_TOOLS_COLOR: bspline.showColorMenu(); break;
            case IDM_TOOLS_WIDTH: bspline.showWidthMenu(); break;
            
            case IDM_BSPLINE_INC: bspline.changeDegree(1); break;
            case IDM_BSPLINE_DEC: bspline.changeDegree(-1); break;
            
            case IDM_HELP_SHOW: bspline.toggleHelp(); break;
            
            case IDM_MODE_2D: bspline.setMode(MODE_2D); bspline.setSize(glutGet(GLUT_WINDOW_WIDTH), glutGet(GLUT_WINDOW_HEIGHT)); updateMenuChecks(hwnd); break;
            case IDM_MODE_3D: bspline.setMode(MODE_3D); bspline.setSize(glutGet(GLUT_WINDOW_WIDTH), glutGet(GLUT_WINDOW_HEIGHT)); updateMenuChecks(hwnd); break;
        }
    }
    return CallWindowProc(oldWndProc, hwnd, msg, wParam, lParam);
}

void createWindowsMenu(HWND hwnd) {
    HMENU hMenu = CreateMenu();
    
    HMENU hMode = CreatePopupMenu();
    AppendMenuA(hMode, MF_STRING, IDM_MODE_2D, "2D Curve Editor");
    AppendMenuA(hMode, MF_STRING, IDM_MODE_3D, "3D Surface Editor");
    AppendMenuA(hMenu, MF_POPUP, (UINT_PTR)hMode, "Mode");
    
    HMENU hFile = CreatePopupMenu();
    AppendMenuA(hFile, MF_STRING, IDM_FILE_LOAD, "Load TXT...");
    AppendMenuA(hFile, MF_STRING, IDM_FILE_SAVE, "Save TXT...");
    AppendMenuA(hFile, MF_STRING, IDM_FILE_SAVE_IMG, "Save Image (.bmp)...");
    AppendMenuA(hFile, MF_SEPARATOR, 0, NULL);
    AppendMenuA(hFile, MF_STRING, IDM_FILE_EXIT, "Exit");
    AppendMenuA(hMenu, MF_POPUP, (UINT_PTR)hFile, "File");
    
    HMENU hEdit = CreatePopupMenu();
    AppendMenuA(hEdit, MF_STRING, IDM_EDIT_UNDO, "Undo");
    AppendMenuA(hEdit, MF_STRING, IDM_EDIT_CLEAR, "Clear Canvas");
    AppendMenuA(hMenu, MF_POPUP, (UINT_PTR)hEdit, "Edit");
    
    HMENU hView = CreatePopupMenu();
    AppendMenuA(hView, MF_STRING, IDM_VIEW_POLY, "Control Polygon");
    AppendMenuA(hView, MF_STRING, IDM_VIEW_POINTS, "Control Points");
    AppendMenuA(hView, MF_STRING, IDM_VIEW_SURFACE, "3D Surface Mesh");
    AppendMenuA(hView, MF_STRING, IDM_VIEW_BAR, "Toggle ViewBar");
    AppendMenuA(hView, MF_STRING, IDM_VIEW_LABELS, "Point Labels");
    AppendMenuA(hView, MF_STRING, IDM_VIEW_GRID, "Show Grid");
    AppendMenuA(hView, MF_SEPARATOR, 0, NULL);
    AppendMenuA(hView, MF_STRING, IDM_VIEW_SNAP, "Snap to Grid");
    AppendMenuA(hView, MF_STRING, IDM_VIEW_CLOSE, "Closed Curve");
    AppendMenuA(hView, MF_SEPARATOR, 0, NULL);
    AppendMenuA(hView, MF_STRING, IDM_VIEW_SYM, "Toggle Symmetry (Doi Xung)");
    AppendMenuA(hView, MF_STRING, IDM_VIEW_ANIM, "Toggle Animation (Dien Hoat)");
    AppendMenuA(hMenu, MF_POPUP, (UINT_PTR)hView, "View");
    
    HMENU hTools = CreatePopupMenu();
    AppendMenuA(hTools, MF_STRING, IDM_TOOLS_COLOR, "Select Color...");
    AppendMenuA(hTools, MF_STRING, IDM_TOOLS_WIDTH, "Select Line Width...");
    AppendMenuA(hMenu, MF_POPUP, (UINT_PTR)hTools, "Tools");
    
    HMENU hBSpline = CreatePopupMenu();
    AppendMenuA(hBSpline, MF_STRING, IDM_BSPLINE_INC, "Increase Degree (+1)");
    AppendMenuA(hBSpline, MF_STRING, IDM_BSPLINE_DEC, "Decrease Degree (-1)");
    AppendMenuA(hMenu, MF_POPUP, (UINT_PTR)hBSpline, "B-Spline");
    
    HMENU hHelp = CreatePopupMenu();
    AppendMenuA(hHelp, MF_STRING, IDM_HELP_SHOW, "Instructions");
    AppendMenuA(hMenu, MF_POPUP, (UINT_PTR)hHelp, "Help");
    
    SetMenu(hwnd, hMenu);
    updateMenuChecks(hwnd);
}

void timerFunc(int val) {
    bspline.updateAnim();
    glutPostRedisplay();
    glutTimerFunc(16, timerFunc, 0);
}

int main(int argc, char** argv) {
    glutInit(&argc, argv);
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH);
    glutInitWindowSize(1050, 720);
    int winId = glutCreateWindow("B-Spline Advanced - 2D & 3D Surface");

    glutDisplayFunc([](){ bspline.draw(); });
    glutMouseFunc([](int b, int s, int x, int y){ bspline.handleMouse(b, s, x, y); });
    glutMotionFunc([](int x, int y){ bspline.handleMotion(x, y); });
    glutMouseWheelFunc([](int wheel, int dir, int x, int y){ bspline.handleMouseWheel(wheel, dir, x, y); });
    glutKeyboardFunc([](unsigned char k, int x, int y){ bspline.handleKeyboard(k, x, y); });
    glutReshapeFunc([](int w, int h){ bspline.setSize(w, h); });

    // Inject Native Windows Menu
    HWND hwnd = FindWindowA("FREEGLUT", "B-Spline Advanced - 2D & 3D Surface");
    if (!hwnd) hwnd = FindWindowA(NULL, "B-Spline Advanced - 2D & 3D Surface");
    if (hwnd) {
        hGroupBox = CreateWindowExA(0, "BUTTON", "ViewBar",
            WS_CHILD | WS_VISIBLE | BS_GROUPBOX,
            5, 5, 190, 710, hwnd, NULL, NULL, NULL);

        hListBox = CreateWindowExA(WS_EX_CLIENTEDGE, "LISTBOX", NULL,
            WS_CHILD | WS_VISIBLE | WS_VSCROLL | LBS_NOINTEGRALHEIGHT | LBS_NOTIFY,
            15, 25, 170, 680, hwnd, NULL, NULL, NULL);

        HFONT hFont = CreateFontA(15, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, ANSI_CHARSET, 
            OUT_TT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY, DEFAULT_PITCH | FF_DONTCARE, "Consolas");
        SendMessage(hListBox, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hGroupBox, WM_SETFONT, (WPARAM)hFont, TRUE);

        createWindowsMenu(hwnd);
        oldWndProc = (WNDPROC)SetWindowLongPtr(hwnd, GWLP_WNDPROC, (LONG_PTR)MyWndProc);
    } else {
        std::cout << "[ERROR] Could not find HWND to attach menu.\n";
    }

    std::cout << "Phien ban dac biet DHMT - 3D Surface & Animation:\n";
    
    glutTimerFunc(16, timerFunc, 0);

    glutMainLoop();
    return 0;
}
