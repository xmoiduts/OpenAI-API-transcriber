from PyQt5.QtWidgets import QWidget, QFrame, QLabel
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QPen

class NavigationBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.min_viewport_width = 200  # 最小显示宽度
        self.unit_width = 60            # 中间层单元宽度
        self.unit_spacing = 4           # 单元间距
        self.init_ui()

    def init_ui(self):
        self.setFixedHeight(40)
        self.setStyleSheet("background: rgba(220, 230, 240, 0.9); border-bottom: 1px solid #ddd;")
        
        # 中间层容器
        self.content_layer = QFrame(self)
        self.content_layer.setAttribute(Qt.WA_TranslucentBackground)
        
        # 标记层
        self.marker = QLabel(self)
        self.marker.setStyleSheet("background: rgba(100, 100, 255, 0.3); border: 1px solid #646464;")
        self.marker.hide()

    def update_layout(self, unit_count, total_content_width, workspace_visible_width, workspace_left_offset):
        """主更新方法"""
        if workspace_visible_width < self.min_viewport_width:
            self.hide()
            print(f"nav_bar hided because workspace_visible_width {workspace_visible_width} "
                  f"< min_viewport_width {self.min_viewport_width}")
            return
            
        self.show()
        content_width = self._calculate_content_width(unit_count)
        self._update_content_layer(unit_count, content_width)
        self._update_marker(total_content_width, workspace_visible_width, workspace_left_offset, content_width)
        self._update_viewport(workspace_visible_width, content_width, workspace_left_offset, total_content_width)

    def _calculate_content_width(self, unit_count):
        # = 所有翻译单元+中缝宽度之和
        return unit_count * self.unit_width + (unit_count - 1) * self.unit_spacing

    def _update_content_layer(self, unit_count, content_width):
        # 生成中间层单元（绘制矩形来表示单元）
        self.content_layer.setFixedSize(content_width, 30)
        
        # 清除现有的单元组件（如果有）
        for child in self.content_layer.children():
            child.deleteLater()
            
        # 为每个单元创建一个矩形标签
        for i in range(unit_count):
            unit = QLabel(self.content_layer)
            unit.setStyleSheet("background: rgba(180, 180, 180, 0.5); border: 1px solid #999;")
            x_pos = i * (self.unit_width + self.unit_spacing)
            unit.setGeometry(x_pos, 0, self.unit_width, 30)
            unit.show()

    def _update_marker(self, total_content_width, workspace_visible_width, workspace_left_offset, content_width):
        marker_width = max(int(workspace_visible_width / total_content_width * content_width), 10)
        marker_x = int(workspace_left_offset / total_content_width * content_width)
        self.marker.setGeometry(marker_x, 5, marker_width, 30)
        self.marker.show()

    def _update_viewport(self, workspace_visible_width, content_width, workspace_left_offset, total_content_width):
        # 计算中间层最大可滚动距离
        max_scrollable = max(content_width - workspace_visible_width, 0)
        
        # 计算内容层应向左偏移的距离
        if total_content_width > 0 and max_scrollable > 0:
            # 计算滚动比例（考虑左侧固定面板的宽度）
            scroll_ratio = workspace_left_offset / total_content_width
            content_offset = int(scroll_ratio * max_scrollable)
        else:
            content_offset = 0
        
        # 应用停靠逻辑
        if content_offset < 0:
            content_offset = 0
        elif content_offset > max_scrollable:
            content_offset = max_scrollable
        
        # 设置中间层位置
        self.content_layer.move(-content_offset, 5)

    # def resizeEvent(self, event):
    #     super().resizeEvent(event)
    #     # 当导航条宽度变化时通知父组件
    #     if self.parent():
    #         self.parent().update_nav_layout()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(Qt.black)  # 设置线条颜色为黑色
        pen.setWidth(1)       # 设置线条宽度
        painter.setPen(pen)
        
        # 绘制从左下到右上的斜线
        painter.drawLine(0, self.height(), self.width(), 0)