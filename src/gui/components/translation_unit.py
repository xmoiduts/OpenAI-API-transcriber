import re
from PyQt5.QtCore import Qt, QSize, QTimer, QEvent, pyqtSignal, QRect
from PyQt5.QtGui import QTextOption, QTextCursor, QTextBlock, QTextDocument, QPainter, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton,
    QSplitter, QFrame, QScrollBar, QApplication
)

class SyncedTextEdit(QTextEdit):
    """
    自定义文本编辑器，支持行对齐和同步滚动
    """
    contentChanged = pyqtSignal()
    
    def __init__(self, partner=None, parent=None):
        super().__init__(parent)
        self.partner = partner
        self.setWordWrapMode(QTextOption.WrapAnywhere)  # 按字符而非按单词换行
        self.setLineWrapMode(QTextEdit.WidgetWidth)  # 按控件宽度换行
        self.document().contentsChanged.connect(self.contentChanged)
        self.syncing_scroll = False
        self.line_heights = {}  # 存储每行的高度信息
        
        # 应用样式
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
        
        # 连接滚动信号
        if partner:
            self.verticalScrollBar().valueChanged.connect(self.syncPartnerScroll)
    
    def syncPartnerScroll(self, value):
        """同步伙伴编辑器的滚动位置"""
        if self.partner and not self.syncing_scroll and not self.partner.syncing_scroll:
            self.partner.syncing_scroll = True
            self.partner.verticalScrollBar().setValue(value)
            QTimer.singleShot(10, lambda: setattr(self.partner, 'syncing_scroll', False))
    
    def createMimeDataFromSelection(self):
        """重写以确保复制的文本不包含控制字符"""
        mime_data = super().createMimeDataFromSelection()
        if mime_data.hasText():
            text = mime_data.text()
            # 移除可能的零宽空格等控制字符
            text = re.sub(r'[\u200B-\u200F\u2028-\u202E]', '', text)
            mime_data.setText(text)
        return mime_data

    def recalculateLineHeights(self):
        """
        重新计算所有行的高度信息
        返回每个文档行的实际行高(含折行)
        """
        doc = self.document()
        self.line_heights = {}
        
        for i in range(doc.blockCount()):
            block = doc.findBlockByNumber(i)
            layout = block.layout()
            
            # 获取这个文本块的行数（单行或折行后的多行）
            line_count = layout.lineCount()
            
            # 计算这个块的总高度
            total_height = 0
            for j in range(line_count):
                line = layout.lineAt(j)
                total_height += line.height()
            
            self.line_heights[i] = {
                'line_count': line_count,
                'total_height': total_height
            }
            
        return self.line_heights
    
    def insertEmptyLines(self, block_number, count):
        """在指定块后插入空行"""
        if count <= 0:
            return
        
        cursor = QTextCursor(self.document().findBlockByNumber(block_number))
        cursor.movePosition(QTextCursor.EndOfBlock)
        
        for _ in range(count):
            cursor.insertText("\n")
    
    def ensurePartnerLineAlignment(self):
        """确保与伙伴编辑器的行对齐"""
        if not self.partner:
            return
            
        my_heights = self.recalculateLineHeights()
        partner_heights = self.partner.recalculateLineHeights()
        
        # 暂时断开内容变化信号连接，避免递归调用
        self.document().contentsChanged.disconnect(self.contentChanged)
        self.partner.document().contentsChanged.disconnect(self.partner.contentChanged)
        
        # 对每个块进行比较和调整
        common_blocks = min(len(my_heights), len(partner_heights))
        
        for i in range(common_blocks):
            my_lines = my_heights.get(i, {}).get('line_count', 1)
            partner_lines = partner_heights.get(i, {}).get('line_count', 1)
            
            # 确定哪一边需要添加空行
            diff = abs(my_lines - partner_lines)
            if diff > 0:
                if my_lines < partner_lines:
                    # 我需要添加空行
                    self.insertEmptyLines(i, diff)
                else:
                    # 伙伴需要添加空行
                    self.partner.insertEmptyLines(i, diff)
        
        # 重新连接信号
        self.document().contentsChanged.connect(self.contentChanged)
        self.partner.document().contentsChanged.connect(self.partner.contentChanged)


class EditorPanel(QWidget):
    """
    编辑器面板基类，包含标题和文本编辑器
    """
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 标题
        title_layout = QHBoxLayout()
        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        
        # 添加标题布局
        layout.addLayout(title_layout)
        
        # 文本编辑器实例将由子类创建
        self.editor = None


class OriginalPanel(EditorPanel):
    """原文编辑面板"""
    
    translateRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Original Text", parent)
    
    def init_ui(self):
        super().init_ui()
        
        layout = self.layout()
        
        # 添加翻译按钮到标题栏
        translate_button = QPushButton("Translate")
        translate_button.setFixedWidth(100)
        translate_button.clicked.connect(self.translateRequested)
        title_layout = layout.itemAt(0).layout()
        title_layout.insertWidget(1, translate_button)
        
        # 创建原文编辑器
        self.editor = SyncedTextEdit(parent=self)
        layout.addWidget(self.editor)
        
        # 添加系统提示区域
        layout.addWidget(QLabel("System Prompt:"))
        self.system_prompt = QTextEdit()
        self.system_prompt.setMaximumHeight(80)
        layout.addWidget(self.system_prompt)
        
        # 添加范围说明区域
        layout.addWidget(QLabel("Range Summary:"))
        self.range_summary = QTextEdit()
        self.range_summary.setMaximumHeight(60)
        layout.addWidget(self.range_summary)
        
        # 添加历史结果区域
        layout.addWidget(QLabel("History Results:"))
        self.history_results = QTextEdit()
        self.history_results.setMaximumHeight(120)
        layout.addWidget(self.history_results)
        
        # 添加术语表区域
        layout.addWidget(QLabel("Terminology:"))
        self.terminology = QTextEdit()
        self.terminology.setMaximumHeight(100)
        layout.addWidget(self.terminology)
        
        # 底部翻译按钮
        bottom_translate = QPushButton("Translate")
        bottom_translate.clicked.connect(self.translateRequested)
        layout.addWidget(bottom_translate)


class TranslationPanel(EditorPanel):
    """译文编辑面板"""
    
    continueRequested = pyqtSignal()
    loadNextRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Translation", parent)
    
    def init_ui(self):
        super().init_ui()
        
        layout = self.layout()
        
        # 创建占位区域匹配原文面板高度
        spacer = QWidget()
        layout.addWidget(spacer)
        
        # 创建译文编辑器
        self.editor = SyncedTextEdit(parent=self)
        layout.addWidget(self.editor)
        
        # 添加按钮区域
        button_layout = QHBoxLayout()
        continue_button = QPushButton("Continue")
        continue_button.clicked.connect(self.continueRequested)
        
        load_next_button = QPushButton("→")
        load_next_button.setToolTip("Load to next unit")
        load_next_button.clicked.connect(self.loadNextRequested)
        
        button_layout.addWidget(continue_button)
        button_layout.addWidget(load_next_button)
        layout.addLayout(button_layout)


class TranslationUnit(QWidget):
    """
    翻译单元组件，包含原文和译文两个面板
    """
    def __init__(self, unit_id=None, parent=None):
        super().__init__(parent)
        self.unit_id = unit_id or "L1-L100"
        self.init_ui()
        self.setup_line_sync()
    
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
    
    def setup_line_sync(self):
        """设置行同步机制"""
        # 设置编辑器伙伴关系
        self.original_panel.editor.setPartner(self.translation_panel.editor)
        self.translation_panel.editor.setPartner(self.original_panel.editor)
        
        # 连接内容变化信号到行对齐函数
        self.original_panel.editor.contentChanged.connect(self.synchronize_lines)
        self.translation_panel.editor.contentChanged.connect(self.synchronize_lines)
    
    def synchronize_lines(self):
        """同步原文和译文的行高"""
        sender = self.sender()
        if sender == self.original_panel.editor:
            sender.ensurePartnerLineAlignment()
        elif sender == self.translation_panel.editor:
            sender.ensurePartnerLineAlignment()
    
    def set_title(self, title):
        """设置翻译单元标题"""
        self.original_panel.title_label.setText(f"{title} - Original")
        self.translation_panel.title_label.setText(f"{title} - Translation")
    
    def set_content(self, original_text, translation_text=""):
        """设置原文和译文内容"""
        # 暂时断开信号连接，避免触发不必要的同步
        self.original_panel.editor.contentChanged.disconnect(self.synchronize_lines)
        self.translation_panel.editor.contentChanged.disconnect(self.synchronize_lines)
        
        # 设置内容
        self.original_panel.editor.setPlainText(original_text)
        self.translation_panel.editor.setPlainText(translation_text)
        
        # 重新连接信号
        self.original_panel.editor.contentChanged.connect(self.synchronize_lines)
        self.translation_panel.editor.contentChanged.connect(self.synchronize_lines)
        
        # 执行一次同步
        QTimer.singleShot(100, self.synchronize_lines)


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