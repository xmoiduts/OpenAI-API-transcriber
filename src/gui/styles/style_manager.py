def get_base_stylesheet():
    """Base styles for common widgets"""
    return """
        QMainWindow, QWidget {
            background-color: #f0f0f0;
            font-family: Arial, sans-serif;
        }
        QLabel, QPushButton, QTabBar::tab {
            color: #333333;
            font-size: 14px;
        }
    """


def get_menu_stylesheet():
    """Styles for menus, context menus and tooltips"""
    return """
        QMenu {
            background-color: #f0f0f0;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 4px;
            font-family: Arial, sans-serif;
        }
        QMenu::item {
            padding: 4px 20px;
            color: #333333;
        }
        QMenu::item:selected {
            background-color: #e0e0e0;
        }
        QMenu::separator {
            height: 1px;
            background-color: #d0d0d0;
            margin: 4px 0px;
        }
        QWidget#hms_editor {
            background-color: #f0f0f0;
            padding: 8px;
        }
        QLabel {
            background-color: #f0f0f0;
            color: #333333;
            font-size: 14px;
        }
        QLineEdit {
            background-color: white;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 4px;
            color: #333333;
            font-size: 14px;
            font-weight: bold;
        }
        QLineEdit:focus {
            border: 1px solid #4CAF50;
        }
        QToolTip {
            background-color: #f0f0f0;
            color: #333333;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 8px;
            font-size: 14px;
        }
    """

def get_time_slicer_stylesheet():
    """Styles specific to TimeSlicerTab"""
    return """
        QLabel#drop_label {
            border: 2px dashed #aaa;
            padding: 20px;
            background-color: #ffffff;
            border-radius: 8px;
            font-size: 18px;
            font-weight: bold;
            color: #888888;
        }
        QLabel#drop_label[dragOver="true"] {
            border: 2px dashed #4CAF50;
            background-color: #E8F5E9;
            color: #4CAF50;
        }
        QPushButton#open_file_button {
            background-color: #4CAF50;
            color: white;
        }
        QPushButton#open_file_button:hover {
            background-color: #45a049;
        }
        QPushButton#reload_button {
            background-color: #FFB3B3;
            color: white;
            font-weight: bold;
        }
        QPushButton#reload_button:hover {
            background-color: #FFA0A0;
        }
    """

def get_button_stylesheet():
    """Styles for buttons"""
    return """
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:disabled {
            background-color: #a0a0a0;
            color: #d0d0d0;
        }
        QPushButton#reset_button {
            background-color: #FFB3B3;
            color: white;
            padding: 6px 12px;
            font-weight: bold;
        }
        QPushButton#reset_button:hover {
            background-color: #FFA0A0;
        }
        QPushButton#stop_button {
            background-color: #8B0000;
            color: white;
            border-radius: 4px;
            font-size: 16px;
            padding: 0px;
        }
        QPushButton#stop_button:hover {
            background-color: #A00000;
        }
        QPushButton#stop_button:disabled {
            background-color: #a0a0a0;
            color: #d0d0d0;
        }
    """


def get_input_stylesheet():
    """Styles for input widgets"""
    return """
        QLineEdit {
            background-color: white;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 4px;
            color: #333333;
            font-size: 14px;
            font-weight: bold;
        }
        QLineEdit:focus {
            border: 1px solid #4CAF50;
        }
    """

def get_segment_bar_stylesheet():
    """Styles specific to SegmentBar"""
    return """
        QFrame#segment_bar {
            background-color: #d3d3d3;
            border-radius: 5px;
        }
        QWidget#hms_editor {
            background-color: #f0f0f0;
            padding: 8px;
        }
        QLabel#help_icon {
            background-color: transparent;
            color: inherit;
            font-family: inherit;
        }
    """

def get_dropdown_stylesheet():
    """Styles for dropdown/combo boxes"""
    return """
        QComboBox {
            background-color: #ffffff;
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            padding: 5px;
            min-width: 100px;
        }
        QComboBox:hover {
            border: 1px solid #4CAF50;
        }
        QComboBox:disabled {
            background-color: #f0f0f0;
            color: #a0a0a0;
        }
        QComboBox::drop-down {
            border: none;
            padding-right: 10px;
        }
        QComboBox::down-arrow {
            image: url(:/img/down-arrow.png);
            width: 12px;
            height: 12px;
        }
    """

def get_translation_button_stylesheet():
    """Styles for translation-related buttons"""
    return """
        QPushButton#open_file_btn {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        }
        QPushButton#open_file_btn:hover {
            background-color: #45a049;
        }
        
        QPushButton#load_context_btn {
            background-color: #2196F3;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        }
        QPushButton#load_context_btn:hover {
            background-color: #0b7dda;
        }
        
        QPushButton#load_to_workspace_btn {
            background-color: #FF9800;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 16px;
        }
        QPushButton#load_to_workspace_btn:hover {
            background-color: #e68a00;
        }
    """

def get_scrollbar_stylesheet():
    """
    获取美化的滚动条样式表
    """
    return """
        QScrollBar:vertical {
            background-color: #f0f0f0;
            width: 12px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background-color: #c0c0c0;
            min-height: 20px;
            border-radius: 6px;
            margin: 2px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #a0a0a0;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
            background: none;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        QScrollBar:horizontal {
            background-color: #f0f0f0;
            height: 12px;
            margin: 0px;
        }
        QScrollBar::handle:horizontal {
            background-color: #c0c0c0;
            min-width: 20px;
            border-radius: 6px;
            margin: 2px;
        }
        QScrollBar::handle:horizontal:hover {
            background-color: #a0a0a0;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
            background: none;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }
    """

def get_drop_zone_stylesheet():
    """
    获取文件拖放区域的样式表
    """
    return """
        /* 只针对有dropZone属性的Label应用拖放样式 */
        QLabel[dropZone="true"] {
            background-color: #f0f0f0;
            border: 2px dashed #ccc;
            border-radius: 5px;
            padding: 20px;
            font-size: 14px;
            transition: all 0.3s;
        }
        /* 只针对有dropZone和dragOver属性的Label应用拖拽时的样式 */
        QLabel[dropZone="true"][dragOver="true"] {
            background-color: #e6f7ff;
            border: 2px dashed #1890ff;
            color: #1890ff;
        }
    """

def get_main_window_stylesheet():
    """
    获取主窗口样式表组合
    """
    return (
        get_base_stylesheet() +
        get_menu_stylesheet() +
        get_button_stylesheet() +
        get_input_stylesheet() +
        get_dropdown_stylesheet()
    )

def get_segment_bar_combined_stylesheet():
    """
    获取分段条专用样式表组合
    """
    return (
        get_base_stylesheet() +
        get_menu_stylesheet() +
        get_segment_bar_stylesheet() +
        get_button_stylesheet() +
        get_input_stylesheet()
    )

def get_time_slicer_combined_stylesheet():
    """
    获取时间切片器专用样式表组合
    """
    return (
        get_base_stylesheet() +
        get_menu_stylesheet() +
        get_time_slicer_stylesheet() +
        get_button_stylesheet() +
        get_input_stylesheet() +
        get_scrollbar_stylesheet()
    )

def get_line_translation_combined_stylesheet():
    """
    获取行翻译专用样式表组合
    """
    return (
        get_base_stylesheet() +
        get_menu_stylesheet() +
        get_button_stylesheet() +
        get_input_stylesheet() +
        get_translation_button_stylesheet() +
        get_scrollbar_stylesheet() +
        get_drop_zone_stylesheet()
    )

def get_complete_stylesheet():
    """
    获取完整的应用样式表
    注意: 尽量避免直接使用此函数，推荐使用针对特定组件的样式表函数
    """
    return (
        get_base_stylesheet() +
        get_menu_stylesheet() +
        get_time_slicer_stylesheet() +
        get_button_stylesheet() +
        get_input_stylesheet() +
        get_segment_bar_stylesheet() +
        get_dropdown_stylesheet() +
        get_translation_button_stylesheet() +
        get_scrollbar_stylesheet()
        # 不再默认包含 drop_zone_stylesheet，避免样式污染
    )