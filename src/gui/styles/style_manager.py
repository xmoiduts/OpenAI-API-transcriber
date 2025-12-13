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
        QPushButton#settings_button {
            background-color: #607D8B;
            color: white;
            border-radius: 4px;
            font-size: 16px;
            padding: 0px;
        }
        QPushButton#settings_button:hover {
            background-color: #546E7A;
        }
        QPushButton#settings_button:disabled {
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

def get_chat_sidebar_stylesheet():
    """Styles for the AI chat sidebar in Sentence Builder tab (Light theme)."""
    return """
        /* Panel headers */
        QLabel#panelHeader {
            background-color: #f3f3f3;
            color: #333333;
            font-size: 12px;
            font-weight: bold;
            padding-left: 12px;
            border-bottom: 1px solid #e0e0e0;
        }
        
        /* File tree panel */
        QFrame#fileTreePanel {
            background-color: #f7f7f7;
            border-right: 1px solid #e0e0e0;
        }
        
        QTreeWidget#fileTree {
            background-color: #f7f7f7;
            color: #333333;
            border: none;
            font-size: 13px;
            outline: none;
        }
        
        QTreeWidget#fileTree::item {
            padding: 4px 8px;
            border: none;
        }
        
        QTreeWidget#fileTree::item:hover {
            background-color: #e8e8e8;
        }
        
        QTreeWidget#fileTree::item:selected {
            background-color: #cce5ff;
            color: #0066cc;
        }
        
        QTreeWidget#fileTree::branch {
            background-color: #f7f7f7;
        }
        
        /* Workspace panel */
        QFrame#workspacePanel {
            background-color: #ffffff;
            border-right: 1px solid #e0e0e0;
        }
        
        QFrame#workspaceContent {
            background-color: #ffffff;
        }
        
        QLabel#workspacePlaceholder {
            color: #999999;
            font-size: 14px;
            font-style: italic;
        }
        
        /* Chat sidebar panel */
        QFrame#chatSidebarPanel {
            background-color: #fafafa;
        }
        
        /* Chat history */
        QScrollArea#chatHistory {
            background-color: #fafafa;
            border: none;
        }
        
        QWidget#chatHistoryContainer {
            background-color: #fafafa;
        }
        
        /* Chat message cards */
        QFrame#chatMessage_user {
            background-color: #e3f2fd;
            border-radius: 8px;
            border-left: 3px solid #1976d2;
        }
        
        QFrame#chatMessage_assistant {
            background-color: #ffffff;
            border-radius: 8px;
            border-left: 3px solid #43a047;
            border: 1px solid #e8e8e8;
            border-left: 3px solid #43a047;
        }
        
        QLabel#messageRole {
            color: #666666;
            font-size: 11px;
        }
        
        QFrame#chatMessage_user QLabel#messageRole {
            color: #1976d2;
        }
        
        QFrame#chatMessage_assistant QLabel#messageRole {
            color: #43a047;
        }
        
        QLabel#messageContent {
            color: #333333;
            font-size: 13px;
            line-height: 1.4;
        }
        
        /* Chat input widget */
        QFrame#chatInputWidget {
            background-color: #f3f3f3;
            border-top: 1px solid #e0e0e0;
        }
        
        QPlainTextEdit#chatInput {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 8px;
            font-size: 13px;
            selection-background-color: #b3d9ff;
        }
        
        QPlainTextEdit#chatInput:focus {
            border: 1px solid #1976d2;
        }
        
        /* Chat control bar */
        QFrame#chatControlBar {
            background-color: #f3f3f3;
            border-top: 1px solid #e0e0e0;
        }
        
        QComboBox#modelSelector {
            background-color: #ffffff;
            color: #666666;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 12px;
        }
        
        QComboBox#modelSelector:disabled {
            background-color: #f0f0f0;
            color: #999999;
        }
        
        QPushButton#sendButton {
            background-color: #1976d2;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: bold;
        }
        
        QPushButton#sendButton:hover {
            background-color: #1e88e5;
        }
        
        QPushButton#sendButton:pressed {
            background-color: #1565c0;
        }
        
        QPushButton#stopButton {
            background-color: #d32f2f;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: bold;
        }
        
        QPushButton#stopButton:hover {
            background-color: #e53935;
        }
        
        /* Splitter handle */
        QSplitter::handle {
            background-color: #e0e0e0;
            width: 1px;
        }
        
        QSplitter::handle:hover {
            background-color: #1976d2;
        }
        
        /* Scrollbar styling for light theme */
        QScrollArea#chatHistory QScrollBar:vertical {
            background-color: #fafafa;
            width: 10px;
            margin: 0px;
        }
        
        QScrollArea#chatHistory QScrollBar::handle:vertical {
            background-color: #c0c0c0;
            min-height: 20px;
            border-radius: 5px;
            margin: 2px;
        }
        
        QScrollArea#chatHistory QScrollBar::handle:vertical:hover {
            background-color: #a0a0a0;
        }
        
        QScrollArea#chatHistory QScrollBar::add-line:vertical,
        QScrollArea#chatHistory QScrollBar::sub-line:vertical {
            height: 0px;
        }
        
        QScrollArea#chatHistory QScrollBar::add-page:vertical,
        QScrollArea#chatHistory QScrollBar::sub-page:vertical {
            background: none;
        }
    """


def get_sentence_builder_combined_stylesheet():
    """
    Combined stylesheet for Sentence Builder tab.
    Uses dark theme to match VSCode/Cursor aesthetic.
    """
    return get_chat_sidebar_stylesheet()


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