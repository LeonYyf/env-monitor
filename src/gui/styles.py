COLORS = {
    # 单一强调色 — 深青
    "primary": "#0F766E",          
    "primary_hover": "#115E59",  
    "primary_pressed": "#134E4A",
    "primary_light": "#CCFBF1",    
    "primary_pale": "#F0FDFA",    
    "ready": "#14B8A6",            
    "ready_hover": "#0D9488",     

    # 中性色 — 暖灰 (stone)
    "white": "#FFFFFF",
    "bg": "#FAFAF8",            
    "bg_subtle": "#F5F5F4",
    "border": "#E7E5E4",           
    "border_strong": "#D6D3D1",    

    # 文字 — 暖黑
    "text_primary": "#1C1917",     
    "text_secondary": "#57534E", 
    "text_hint": "#A8A29E",
    "text_on_dark": "#F0FDFA", 

    # 状态色
    "danger": "#DC2626",
    "warning": "#D97706",
    "success": "#0F766E",
    "info": "#0F766E",

    # 侧边栏 — 深青
    "sidebar_bg": "#134E4A", 
    "sidebar_hover": "#0F766E", 
    "sidebar_active": "#0D9488", 
    "sidebar_text": "#99F6E4",
    "sidebar_text_muted": "#5EEAD4",
}

GLOBAL_STYLESHEET = """
/* === 全局 === */
QMainWindow {
    background-color: #FAFAF8;
}

/* 页面堆叠容器：只设置自身背景，不覆盖内部按钮等子控件样式 */
QStackedWidget#pageStack {
    background-color: #FAFAF8;
}

QWidget {
    font-family: "PingFang SC", "Helvetica Neue", "Arial";
    font-size: 14px;
    color: #1C1917;
}

/* === 侧边栏 / 导航 === */
QListWidget#sidebar {
    background-color: #134E4A;
    border: none;
    font-size: 14px;
    padding: 8px;
    outline: none;
}

QListWidget#sidebar::item {
    color: #99F6E4;
    padding: 12px 16px;
    margin: 2px 8px;
    border-radius: 8px;
    border: none;
}

QListWidget#sidebar::item:hover {
    background-color: #0F766E;
    color: #F0FDFA;
}

QListWidget#sidebar::item:selected {
    background-color: #0D9488;
    color: #FFFFFF;
    font-weight: bold;
    border-left: 3px solid #5EEAD4;
    padding-left: 13px;
}

QListWidget#sidebar::item:disabled {
    color: #3E6B66;
}

/* === 页面标题 === */
QLabel#pageTitle {
    font-size: 22px;
    font-weight: bold;
    color: #1C1917;
    padding: 16px 0px 8px 0px;
}

QLabel#pageDescription {
    font-size: 14px;
    color: #57534E;
    padding-bottom: 16px;
}

/* === 主按钮 (Primary) === */
QPushButton#primaryBtn {
    background-color: #0F766E;
    color: #FFFFFF;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#primaryBtn:hover {
    background-color: #115E59;
}

QPushButton#primaryBtn:pressed {
    background-color: #134E4A;
}

QPushButton#primaryBtn:disabled {
    background-color: #E7E5E4;
    color: #57534E;
    border: 1px solid #D6D3D1;
}

/* 已加载数据但未选变量时的“置灰”态（按钮仍可点，用于悬停提示） */
QPushButton#primaryBtn[inactive="true"] {
    background-color: #E7E5E4;
    color: #57534E;
    border: 1px solid #D6D3D1;
}

/* 导入按钮 — 空闲态（尚未拖入文件，按钮禁用但必须清晰可见，避免“消失”） */
QPushButton#primaryBtn[state="idle"] {
    background-color: #CCFBF1;
    color: #0F766E;
    border: 1px solid #5EEAD4;
}

/* 导入按钮 — 就绪态（已拖入文件、可导入）：比侧边栏绿更浅的绿 */
QPushButton#primaryBtn[state="ready"] {
    background-color: #14B8A6;
    color: #FFFFFF;
    border: 1px solid transparent;
}

QPushButton#primaryBtn[state="ready"]:hover {
    background-color: #0D9488;
}

QPushButton#primaryBtn[state="ready"]:pressed {
    background-color: #0F766E;
}

/* 导入按钮 — 完成态（导入成功）：与侧边栏绿一致 */
QPushButton#primaryBtn[state="done"] {
    background-color: #134E4A;
    color: #F0FDFA;
    border: 1px solid transparent;
}

/* === 次要按钮 === */
QPushButton#secondaryBtn {
    background-color: #FFFFFF;
    color: #0F766E;
    border: 1px solid #0F766E;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
}

QPushButton#secondaryBtn:hover {
    background-color: #F0FDFA;
    border-color: #115E59;
}

QPushButton#secondaryBtn:pressed {
    background-color: #0F766E;   /* 边框青色填充进按钮 */
    color: #FFFFFF;
    border-color: #0F766E;
}

/* === 成功/确认按钮 === */
QPushButton#successBtn {
    background-color: #0F766E;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: 600;
}

QPushButton#successBtn:hover {
    background-color: #115E59;
}

QPushButton#successBtn:pressed {
    background-color: #134E4A;
}

/* === 危险按钮 === */
QPushButton#dangerBtn {
    background-color: #FFFFFF;
    color: #DC2626;
    border: 1px solid #DC2626;
    border-radius: 8px;
    padding: 10px 24px;
    font-size: 14px;
}

QPushButton#dangerBtn:hover {
    background-color: #FEF2F2;
}

QPushButton#dangerBtn:pressed {
    background-color: #DC2626;   /* 边框红色填充进按钮 */
    color: #FFFFFF;
    border-color: #DC2626;
}

/* === 输入框 === */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    border: 1px solid #E7E5E4;
    border-radius: 8px;
    padding: 8px 12px;
    background-color: #FFFFFF;
    min-height: 20px;
    color: #1C1917;
    selection-background-color: #CCFBF1;
    selection-color: #1C1917;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #0F766E;
    border-width: 2px;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #E7E5E4;
    selection-background-color: #CCFBF1;
    selection-color: #1C1917;
}

/* === 表格 === */
QTableView, QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E7E5E4;
    border-radius: 8px;
    gridline-color: #F5F5F4;
    selection-background-color: #CCFBF1;
    selection-color: #134E4A;
    alternate-background-color: #FAFAF8;
}

QTableView, QTableWidget {
    font-family: "Menlo", "Monaco", "SF Mono";
    font-size: 12px;
}

QHeaderView::section {
    background-color: #F5F5F4;
    color: #57534E;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #E7E5E4;
    font-weight: 600;
    font-family: "PingFang SC", "Helvetica Neue", "Arial";
    font-size: 12px;
}

/* === 选项卡 === */
QTabWidget::pane {
    border: 1px solid #E7E5E4;
    border-radius: 8px;
    background-color: #FFFFFF;
}

QTabBar::tab {
    background-color: #F5F5F4;
    color: #57534E;
    padding: 8px 20px;
    border: 1px solid #E7E5E4;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #0F766E;
    font-weight: 600;
    border-bottom: 2px solid #0F766E;
}

QTabBar::tab:hover:!selected {
    background-color: #F0FDFA;
}

/* === 分组框 === */
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E7E5E4;
    border-radius: 10px;
    margin-top: 12px;
    padding: 16px;
    font-weight: 600;
    color: #1C1917;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0px 8px;
    color: #0F766E;
}

/* === 进度条 === */
QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: #E7E5E4;
    height: 8px;
    text-align: center;
    font-size: 11px;
    color: transparent;
}

QProgressBar::chunk {
    background-color: #0F766E;
    border-radius: 4px;
}

/* === 滚动条 === */
QScrollBar:vertical {
    background-color: transparent;
    width: 10px;
    border: none;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background-color: #D6D3D1;
    border-radius: 5px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background-color: #A8A29E;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 10px;
    border: none;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background-color: #D6D3D1;
    border-radius: 5px;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #A8A29E;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* === 提示文本 / 状态栏 === */
QStatusBar {
    background-color: #134E4A;
    color: #99F6E4;
    border-top: none;
}

/* === 单选按钮 / 复选框 === */
QRadioButton, QCheckBox {
    spacing: 8px;
    color: #1C1917;
}

QRadioButton::indicator, QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #D6D3D1;
    border-radius: 4px;
    background-color: #FFFFFF;
}

QRadioButton::indicator {
    border-radius: 9px;
}

QRadioButton::indicator:checked, QCheckBox::indicator:checked {
    background-color: #0F766E;
    border-color: #0F766E;
}

/* === 分割线 === */
QFrame#line {
    background-color: #E7E5E4;
    max-height: 1px;
}

/* === 日志/输出文本框 === */
QTextEdit#logOutput {
    background-color: #FAFAF8;
    border: 1px solid #E7E5E4;
    border-radius: 8px;
    font-family: "Menlo", "Monaco", "SF Mono";
    font-size: 12px;
    color: #57534E;
    padding: 8px;
}

QTextEdit {
    background-color: #FFFFFF;
    border: 1px solid #E7E5E4;
    border-radius: 8px;
    color: #1C1917;
    selection-background-color: #CCFBF1;
    selection-color: #134E4A;
}

/* === 卡片容器 === */
QFrame#card {
    background-color: #FFFFFF;
    border: 1px solid #E7E5E4;
    border-radius: 12px;
    padding: 16px;
}

/* === 拖拽上传区 === */
QFrame#dropZone {
    background-color: #F0FDFA;
    border: 2px dashed #0F766E;
    border-radius: 12px;
}

QFrame#dropZone[dragging="true"] {
    background-color: #CCFBF1;
    border: 2px dashed #115E59;
}

QLabel#dropIcon {
    font-size: 40px;
}

QLabel#dropHint {
    font-size: 16px;
    font-weight: 600;
    color: #1C1917;
}

QLabel#dropSubHint {
    font-size: 13px;
    color: #A8A29E;
}

QLabel#fileNameLabel {
    font-size: 16px;
    font-weight: bold;
    color: #1C1917;
}

QLabel#fileMetaLabel {
    font-size: 13px;
    color: #57534E;
}

QLabel#sheetSummaryLabel {
    font-size: 13px;
    color: #57534E;
}

/* === 导入进度状态文字 === */
QLabel#statusLabel {
    font-size: 14px;
    font-weight: 600;
    color: #0F766E;
}

/* === 导入概览卡片 === */
QLabel#cardTitle {
    font-size: 15px;
    font-weight: 600;
    color: #1C1917;
    padding-bottom: 8px;
}

QLabel#statValue {
    font-family: "Menlo", "Monaco", "SF Mono";
    font-size: 24px;
    font-weight: bold;
    color: #0F766E;
}

QLabel#statLabel {
    font-size: 12px;
    color: #57534E;
}

/* === 步骤指示器 === */
QLabel#stepActive {
    background-color: #0F766E;
    color: #FFFFFF;
    border-radius: 16px;
    min-width: 32px;
    min-height: 32px;
    font-weight: 600;
    font-size: 14px;
}

QLabel#stepCompleted {
    background-color: #0F766E;
    color: #FFFFFF;
    border-radius: 16px;
    min-width: 32px;
    min-height: 32px;
    font-weight: 600;
    font-size: 14px;
}

QLabel#stepPending {
    background-color: #E7E5E4;
    color: #A8A29E;
    border-radius: 16px;
    min-width: 32px;
    min-height: 32px;
    font-size: 14px;
}
"""
