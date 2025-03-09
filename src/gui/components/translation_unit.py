import re
from PyQt5.QtCore import Qt, QSize, QTimer, QEvent, pyqtSignal, QRect, QPoint
from PyQt5.QtGui import QTextOption, QTextCursor, QTextBlock, QTextDocument, QPainter, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton,
    QSplitter, QFrame, QScrollBar, QApplication, QScrollArea
)
# 添加样式导入
from src.gui.styles.style_manager import get_scrollbar_stylesheet

class SyncedTextEdit(QTextEdit):
    """
    自定义文本编辑器，支持行对齐，无内部滚动
    """
    contentChanged = pyqtSignal()
    
    def __init__(self, partner=None, parent=None):
        super().__init__(parent)
        self.partner = partner
        self.setWordWrapMode(QTextOption.WrapAnywhere)  # 按字符而非按单词换行
        self.setLineWrapMode(QTextEdit.WidgetWidth)  # 按控件宽度换行
        
        # 跟踪document内容变化和行数变化
        self.document().contentsChanged.connect(self.contentChanged)
        self.document().contentsChanged.connect(self.checkLineCountChange)
        
        # 跟踪最后计算的显示行数
        self.last_display_line_count = 0
        
        # 禁用垂直滚动条
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 应用样式 TODO: apply to and use style_manager.py
        self.setStyleSheet("""
            QTextEdit {
                font-family: 'Source Code Pro', 'Consolas', monospace;
                font-size: 14px;
                line-height: 1.5;
                background-color: #f8f8f8;
                border: 1px solid #ddd;
            }
        """)
    
    def setPartner(self, partner):
        """设置伙伴编辑器"""
        self.partner = partner
    
    def resizeEvent(self, event):
        """重写调整大小事件，检测宽度变化导致的行数变化"""
        if event.oldSize().width() != event.size().width():
            # 当宽度变化时，可能会影响换行，需要重新计算高度
            QTimer.singleShot(0, self.checkLineCountChange)
        super().resizeEvent(event)
    
    def checkLineCountChange(self):
        """检查显示行数是否变化，如果变化则调整高度"""
        # 计算当前显示的行数（包含换行后的行）
        current_display_line_count = self.getDisplayLineCount()
        
        # 如果显示行数变化，调整高度
        if current_display_line_count != self.last_display_line_count:
            self.last_display_line_count = current_display_line_count
            self.adjustHeightToContent()
    
    def getDisplayLineCount(self):
        """计算文档显示的总行数，包含换行产生的行"""
        doc = self.document()
        total_lines = 0
        
        # 遍历所有块（逻辑行）
        for i in range(doc.blockCount()):
            block = doc.findBlockByNumber(i)
            layout = block.layout()
            
            # 统计这个块的显示行数（可能因换行而增加）
            if layout is not None:
                total_lines += layout.lineCount()
            else:
                total_lines += 1  # 如果layout不可用，至少计为1行
                
        return total_lines
    
    def adjustHeightToContent(self):
        """调整高度以适应所有内容"""
        # 计算文档高度
        doc_height = self.document().size().height()
        # 添加额外空间，确保所有内容可见
        padding = 30  # 增加更多空间确保所有内容都可见
        self.setMinimumHeight(int(doc_height + padding))
    
    def createMimeDataFromSelection(self):
        """重写以确保复制的文本不包含控制字符"""
        mime_data = super().createMimeDataFromSelection()
        if mime_data.hasText():
            text = mime_data.text()
            # 移除可能的零宽空格等控制字符
            text = re.sub(r'[\u200B-\u200F\u2028-\u202E]', '', text)
            mime_data.setText(text)
        return mime_data


class EditorPanel(QScrollArea):
    """
    编辑器面板基类，包含标题和文本编辑器
    现在是一个可滚动区域，内部内容可垂直滚动
    """
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.init_ui()
    
    def init_ui(self):
        # 设置滚动区域属性
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建内容容器
        self.content_widget = QWidget()
        self.setWidget(self.content_widget)
        
        # 创建布局
        self.layout = QVBoxLayout(self.content_widget)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        # 标题
        title_layout = QHBoxLayout()
        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        
        # 添加标题布局
        self.layout.addLayout(title_layout)
        
        # 文本编辑器实例将由子类创建
        self.editor = None
        
        # 应用美化的滚动条样式
        self.setStyleSheet("""
            QScrollArea {
                background-color: #f5f5f5;
                border: none;
            }
        """ + get_scrollbar_stylesheet())


class OriginalPanel(EditorPanel):
    """原文编辑面板"""
    
    translateRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Original Text", parent)
    
    def init_ui(self):
        super().init_ui()
        
        # 添加翻译按钮到标题栏
        translate_button = QPushButton("Translate")
        translate_button.setFixedWidth(100)
        translate_button.clicked.connect(self.translateRequested)
        title_layout = self.layout.itemAt(0).layout()
        title_layout.insertWidget(1, translate_button)
        
        # 添加系统提示区域
        self.layout.addWidget(QLabel("System Prompt:"))
        self.system_prompt = QTextEdit()
        self.system_prompt.setMaximumHeight(80)
        self.layout.addWidget(self.system_prompt)
        
        # 添加范围说明区域
        self.layout.addWidget(QLabel("Range Summary:"))
        self.range_summary = QTextEdit()
        self.range_summary.setMaximumHeight(60)
        self.layout.addWidget(self.range_summary)
        
        # 添加历史结果区域
        self.layout.addWidget(QLabel("History Results:"))
        self.history_results = QTextEdit()
        self.history_results.setMaximumHeight(120)
        self.layout.addWidget(self.history_results)
        
        # 添加术语表区域
        self.layout.addWidget(QLabel("Terminology:"))
        self.terminology = QTextEdit()
        self.terminology.setMaximumHeight(100)
        self.layout.addWidget(self.terminology)
        
        # 创建原文编辑器（移到底部）
        self.layout.addWidget(QLabel("Original Content:"))
        self.editor = SyncedTextEdit(parent=self.content_widget)
        self.layout.addWidget(self.editor)
        
        # 底部翻译按钮
        bottom_translate = QPushButton("Translate")
        bottom_translate.clicked.connect(self.translateRequested)
        self.layout.addWidget(bottom_translate)


class TranslationPanel(EditorPanel):
    """译文编辑面板"""
    
    continueRequested = pyqtSignal()
    loadNextRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Translation", parent)
    
    def init_ui(self):
        super().init_ui()
        
        # 添加单个占位区域，使译文编辑器的垂直偏移与原文编辑器一致
        single_spacer = QWidget()
        # 计算占位高度：系统提示(80) + 范围说明(60) + 历史结果(120) + 术语表(100) + 标签高度和间距
        spacer_height = 400  # 估算高度，包含了所有原文面板中上下文区域的高度总和
        single_spacer.setFixedHeight(spacer_height)
        self.layout.addWidget(single_spacer)
        
        # 创建译文编辑器（移到底部）
        self.layout.addWidget(QLabel("Translation Content:"))
        self.editor = SyncedTextEdit(parent=self.content_widget)
        self.layout.addWidget(self.editor)
        
        # 添加按钮区域
        button_layout = QHBoxLayout()
        continue_button = QPushButton("Continue")
        continue_button.clicked.connect(self.continueRequested)
        
        load_next_button = QPushButton("→")
        load_next_button.setToolTip("Load to next unit")
        load_next_button.clicked.connect(self.loadNextRequested)
        
        button_layout.addWidget(continue_button)
        button_layout.addWidget(load_next_button)
        self.layout.addLayout(button_layout)


class TranslationUnit(QWidget):
    """
    翻译单元组件，包含原文和译文两个面板
    """
    def __init__(self, unit_id=None, parent=None):
        super().__init__(parent)
        self.unit_id = unit_id or "L1-L100"
        self.init_ui()
        self.setup_panel_sync()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建分割器
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)
        
        # 创建原文面板
        self.original_panel = OriginalPanel()
        
        # 创建译文面板
        self.translation_panel = TranslationPanel()
        
        # 添加面板到分割器
        self.splitter.addWidget(self.original_panel)
        self.splitter.addWidget(self.translation_panel)
        
        # 设置初始大小
        self.splitter.setSizes([400, 400])
        
        # 添加分割器到布局
        layout.addWidget(self.splitter)
        
        # 设置最小宽度
        self.setMinimumWidth(800)
        
        # 设置样式
        self.setStyleSheet("""
            QSplitter::handle {
                background-color: #ccc;
            }
        """)
    
    def setup_panel_sync(self):
        """设置面板滚动同步机制"""
        # 设置编辑器伙伴关系
        self.original_panel.editor.setPartner(self.translation_panel.editor)
        self.translation_panel.editor.setPartner(self.original_panel.editor)
        
        # 连接面板滚动条信号
        self.original_panel.verticalScrollBar().valueChanged.connect(self.sync_panel_scroll)
        self.translation_panel.verticalScrollBar().valueChanged.connect(self.sync_panel_scroll)
        
        # 滚动同步标志
        self.original_panel.syncing_scroll = False
        self.translation_panel.syncing_scroll = False
    
    def sync_panel_scroll(self, value):
        """同步面板滚动位置，使用多段变换策略"""
        sender = self.sender()
        
        # 确定目标面板和源面板
        if sender == self.original_panel.verticalScrollBar():
            target_panel = self.translation_panel
            source_panel = self.original_panel
        else:
            target_panel = self.original_panel
            source_panel = self.translation_panel
        
        # 避免递归滚动
        if not source_panel.syncing_scroll and not target_panel.syncing_scroll:
            # 获取文本框标签
            source_editor_label = None
            target_editor_label = None
            
            for label in source_panel.content_widget.findChildren(QLabel, "", Qt.FindChildrenRecursively):
                if "Content:" in label.text():
                    source_editor_label = label
                    break
            
            for label in target_panel.content_widget.findChildren(QLabel, "", Qt.FindChildrenRecursively):
                if "Content:" in label.text():
                    target_editor_label = label
                    break
            
            if source_editor_label and target_editor_label:
                # 获取文本框标签在面板中的位置
                source_pos = source_editor_label.mapTo(source_panel.content_widget, QPoint(0, 0)).y()
                target_pos = target_editor_label.mapTo(target_panel.content_widget, QPoint(0, 0)).y()
                
                # 获取面板当前滚动位置
                source_scroll = source_panel.verticalScrollBar().value()
                
                # 判断文本框是否已滚动到面板顶部
                # 如果标签位置小于滚动位置，说明标签已滚动到面板上方或顶部
                source_reached_top = source_pos <= source_scroll + 10  # 添加少量容差
                
                # 设置目标面板滚动位置
                target_panel.syncing_scroll = True
                
                if not source_reached_top:
                    # 阶段1: 文本框未到达面板顶部，保持相同偏移量
                    # 计算源面板中文本框距离顶部的偏移量
                    source_offset = source_scroll
                    # 将同样的偏移量应用到目标面板
                    target_panel.verticalScrollBar().setValue(source_offset)
                else:
                    # 阶段2: 文本框已到达面板顶部，使用比例滚动
                    # 计算超出文本框顶部的部分，即滚动值减去文本框位置
                    source_overflow = source_scroll - source_pos
                    
                    # 计算源面板的剩余可滚动范围
                    source_max = source_panel.verticalScrollBar().maximum()
                    source_remaining = source_max - source_pos
                    
                    if source_remaining <= 0:
                        ratio = 1
                    else:
                        ratio = source_overflow / source_remaining
                    
                    # 计算目标面板的可滚动范围
                    target_max = target_panel.verticalScrollBar().maximum()
                    target_remaining = target_max - target_pos
                    
                    # 计算目标面板应该滚动的值
                    target_scroll = target_pos + (ratio * target_remaining)
                    target_panel.verticalScrollBar().setValue(int(target_scroll))
                
                # 延迟重置标志
                QTimer.singleShot(10, lambda: setattr(target_panel, 'syncing_scroll', False))
            else:
                # 回退到默认的比例滚动
                source_max = source_panel.verticalScrollBar().maximum()
                if source_max == 0:
                    ratio = 0
                else:
                    ratio = value / source_max
                
                target_panel.syncing_scroll = True
                target_max = target_panel.verticalScrollBar().maximum()
                target_panel.verticalScrollBar().setValue(int(ratio * target_max))
                QTimer.singleShot(10, lambda: setattr(target_panel, 'syncing_scroll', False))
    
    def set_title(self, title):
        """设置翻译单元标题"""
        self.original_panel.title_label.setText(f"{title} - Original")
        self.translation_panel.title_label.setText(f"{title} - Translation")
    
    def set_content(self, original_text, translation_text=""):
        """设置原文和译文内容"""
        # 设置内容
        self.original_panel.editor.setPlainText(original_text)
        self.translation_panel.editor.setPlainText(translation_text)
        
        # 重置行数统计
        self.original_panel.editor.last_display_line_count = 0
        self.translation_panel.editor.last_display_line_count = 0
        
        # 确保内容变化后重新计算行数和高度
        QTimer.singleShot(100, self.original_panel.editor.checkLineCountChange)
        QTimer.singleShot(100, self.translation_panel.editor.checkLineCountChange)
        
        # 确保文本框在面板中的位置对齐
        QTimer.singleShot(200, self.ensure_editor_alignment)
        
        # 确保文本框完全扩展以显示所有内容
        QTimer.singleShot(300, self.ensure_editors_fully_expanded)
    
    def ensure_editors_fully_expanded(self):
        """确保两个编辑器都完全展开以显示所有内容"""
        # 强制重新计算编辑器高度
        self.original_panel.editor.checkLineCountChange()
        self.translation_panel.editor.checkLineCountChange()
        
        # 更新布局
        self.original_panel.content_widget.updateGeometry()
        self.translation_panel.content_widget.updateGeometry()
    
    def ensure_editor_alignment(self):
        """确保两个面板中的文本框位置对齐"""
        # 获取原文面板中文本框的位置
        original_editor_label = self.original_panel.content_widget.findChild(QLabel, "", Qt.FindChildrenRecursively)
        for label in self.original_panel.content_widget.findChildren(QLabel, "", Qt.FindChildrenRecursively):
            if label.text() == "Original Content:":
                original_editor_label = label
                break
        
        # 获取译文面板中文本框的位置
        translation_editor_label = None
        for label in self.translation_panel.content_widget.findChildren(QLabel, "", Qt.FindChildrenRecursively):
            if label.text() == "Translation Content:":
                translation_editor_label = label
                break
        
        if original_editor_label and translation_editor_label:
            # 计算原文面板中文本框的垂直位置
            original_pos = original_editor_label.mapTo(self.original_panel.content_widget, QPoint(0, 0)).y()
            
            # 计算译文面板中文本框的垂直位置
            translation_pos = translation_editor_label.mapTo(self.translation_panel.content_widget, QPoint(0, 0)).y()
            
            # 如果位置不同，调整空白区域的高度
            if original_pos != translation_pos:
                diff = original_pos - translation_pos
                
                # 找到译文面板中的所有占位空间
                spacers = []
                for i in range(self.translation_panel.layout.count()):
                    widget = self.translation_panel.layout.itemAt(i).widget()
                    if isinstance(widget, QWidget) and not isinstance(widget, QLabel) and not isinstance(widget, SyncedTextEdit) and not isinstance(widget, QPushButton):
                        spacers.append(widget)
                
                # 调整最后一个占位空间的高度
                if spacers and diff != 0:
                    last_spacer = spacers[-1]
                    new_height = last_spacer.height() + diff
                    if new_height > 0:
                        last_spacer.setFixedHeight(new_height)


# 测试代码
if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    # 创建测试文本
    original_text = """{L1} This is a test of the translation unit.
{L2} It supports CJK characters like 你好世界.
{L3} Lines should be properly aligned between panels.
{L4} Even with very long lines that need to be wrapped to the next line, the alignment should still work properly.
{L5} 这是一个非常长的中文句子，它应该会自动折行，我们需要确保折行后的对齐效果良好。即使一行中包含了多个词语或短语，系统也应该能够正确处理。"""
    
    translation_text = """{L1} 这是翻译单元的测试。
{L2} 它支持CJK字符如"你好世界"。
{L3} 两个面板之间的行应该正确对齐。
{L4} 即使是需要换行的很长的行，对齐仍然应该正常工作。
{L5} This is a very long Chinese sentence that should automatically wrap, we need to ensure good alignment after wrapping. Even if a line contains multiple words or phrases, the system should be able to handle it correctly."""
    
    # 创建并显示翻译单元
    unit = TranslationUnit()
    unit.set_content(original_text, translation_text)
    unit.resize(1000, 800)
    unit.show()
    
    sys.exit(app.exec_()) 