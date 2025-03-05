from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRect
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication

class TranslationStatusStrip(QWidget):
    """
    翻译状态条，垂直显示每行的翻译状态
    通过颜色标识不同的翻译状态
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_statuses = []  # 每行的状态
        self.line_count = 0
        self.init_ui()
    
    def init_ui(self):
        self.setFixedWidth(20)  # 固定宽度
        self.setMinimumHeight(200)  # 最小高度
        
        # 设置样式
        self.setStyleSheet("""
            TranslationStatusStrip {
                background-color: #fafafa;
                border-left: 1px solid #ddd;
                border-right: 1px solid #ddd;
            }
        """)
    
    def update_line_statuses(self, statuses):
        """
        更新行状态列表
        
        Args:
            statuses: 包含每行状态的列表，值为以下之一:
                      'untranslated': 未翻译
                      'translated': 已翻译
                      'failed': 翻译失败
        """
        self.line_statuses = statuses
        self.line_count = len(statuses)
        self.update()
    
    def set_line_status(self, line_index, status):
        """设置指定行的状态"""
        if 0 <= line_index < len(self.line_statuses):
            self.line_statuses[line_index] = status
            self.update()
    
    def paintEvent(self, event):
        """绘制状态条"""
        if not self.line_statuses:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 计算每行高度
        line_height = max(1, self.height() / self.line_count)
        strip_width = self.width() - 2  # 减去边框宽度
        
        # 绘制每行状态
        for i, status in enumerate(self.line_statuses):
            y = int(i * line_height)  # 确保y是整数
            rect = QRect(1, y, strip_width, int(line_height))  # 确保所有参数都是整数
            
            # 根据状态选择颜色
            if status == 'translated':
                color = QColor(0, 180, 0)  # 绿色
            elif status == 'failed':
                color = QColor(220, 0, 0)  # 红色
            else:  # untranslated
                color = QColor(240, 240, 240)  # 白色/浅灰色
            
            painter.fillRect(rect, color)
            
        # 绘制边框
        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.drawRect(0, 0, self.width()-1, self.height()-1)
    
    def resizeEvent(self, event):
        """处理大小变化事件"""
        self.update()


# 测试代码
if __name__ == "__main__":
    import sys
    import random
    
    app = QApplication(sys.argv)
    
    # 模拟数据
    line_count = 300
    statuses = []
    for _ in range(line_count):
        status_choice = random.choice(['untranslated', 'translated', 'failed'])
        # 使得大部分是未翻译状态
        if random.random() < 0.6:
            status_choice = 'untranslated'
        statuses.append(status_choice)
    
    # 创建并显示状态条
    status_strip = TranslationStatusStrip()
    status_strip.update_line_statuses(statuses)
    status_strip.resize(20, 600)
    status_strip.show()
    
    sys.exit(app.exec_()) 