from PyQt5.QtWidgets import QWidget, QFrame, QLabel
from PyQt5.QtCore import Qt, QRect, QPoint, QEvent
from PyQt5.QtGui import QPainter, QPen

class NavigationBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.min_viewable_width = 200  # 最小显示宽度
        self.unit_width = 160           # 中间层单元宽度（固定）
        self.unit_spacing = 12          # 单元间距（固定）
        self.half_unit_spacing = self.unit_spacing // 2
        self.content_offset = 0        # 缩略图层向左偏移的距离
        self.min_marker_width = 40     # 最小marker宽度
        self.dragging = False          # 标记是否正在拖动marker
        self.last_mouse_pos = None     # 用于拖动计算
        self.drag_start_pos = None  # 拖动起始位置（内容层坐标系）
        self.initial_marker_x = 0  # 拖动开始时marker的位置（内容层坐标系）
        self.init_ui()
        

    def init_ui(self):
        self.setFixedHeight(40)
        self.setStyleSheet("background: rgba(220, 230, 240, 0.9); border-bottom: 1px solid #ddd;")
        
        # 中间层容器
        self.content_layer = QFrame(self)
        self.content_layer.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.content_layer.setAttribute(Qt.WA_TranslucentBackground)
        
        # 标记层
        self.marker = QLabel(self)
        self.marker.setStyleSheet("background: rgba(100, 100, 255, 0.3); border: 1px solid #646464;")
        self.marker.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.marker.hide()

    def _calculate_layout_params(self, external_total_width, thumbnail_total_width, external_visible_width):
        """计算关键布局参数"""
        # 假设nav_bar与workspace的可见区域等宽

        # 计算marker宽度
        marker_width = int(external_visible_width * thumbnail_total_width / external_total_width)
        marker_width = max(marker_width, self.min_marker_width)
        # 计算最大marker移动距离
        max_marker_travel = min(external_visible_width, thumbnail_total_width) - marker_width # may BUG: max marker travel 是相对于thumbnails 最左端还是navbar visible area 最左端 的偏移像素数? 他俩的区别是, thumbnails层可能随浏览进度的增长而向左滑动.具体实现要看图层合并的方法
        
        return marker_width, max_marker_travel

    def _calculate_progress_ratio(self, external_left_offset, external_total_width, external_visible_width):
        """计算进度比例"""
        if external_total_width <= 0:
            return 0

        try:
            progress_ratio = external_left_offset / (external_total_width - external_visible_width) # 假定marker的移动范围是相对于external_visible_width的
        except ZeroDivisionError:
            progress_ratio = 0
        return max(0, min(1, progress_ratio))

    def _calculate_content_offset(self, progress_ratio, thumbnail_total_width, external_visible_width):
        """根据marker位置计算内容层偏移量"""
        # 计算最大可滚动距离
        max_content_offset = max(thumbnail_total_width - external_visible_width, 0)
        
        # 计算内容层偏移量
        return int(progress_ratio * max_content_offset)

    def update_layout(self, unit_count, external_total_width, external_visible_width, left_offset):
        """主更新方法"""
        # unit_count is a temporary variable to mock translation_units count
        # external_total_width is the total content width of the scrollable
        #   component where the nav bar is located
        # external_visible_width is the visible width of the scrollable
        #   component where the nav bar is located
        # left_offset is the offset of the left edge of the visible area
        #   from the left edge of the scrollable component
        if external_visible_width < self.min_viewable_width:
            self.hide()
            return
            
        self.show()
            
        # 计算内容层总宽度（固定缩放）
        self.thumbnail_total_width = self._calculate_thumbnail_total_width(unit_count)

        # 计算布局参数
        marker_width, max_marker_travel = self._calculate_layout_params(
            external_total_width, self.thumbnail_total_width, external_visible_width)
        
        # 更新内容层
        self._update_content_layer(unit_count, self.thumbnail_total_width)

        # 计算进度比例
        progress_ratio = self._calculate_progress_ratio(
            left_offset, external_total_width, external_visible_width)
        
        # 计算并更新marker位置
        marker_x = int(progress_ratio * max_marker_travel)
        self.marker.setGeometry(marker_x + self.half_unit_spacing, 5, marker_width, 30)
        self.marker.show()
        
        # 计算并更新内容层位置
        self.content_offset = self._calculate_content_offset(
            progress_ratio, self.thumbnail_total_width, external_visible_width)
        self.content_layer.move(-self.content_offset, 5)

    def _calculate_thumbnail_total_width(self, unit_count):
        # = 所有翻译单元+中缝宽度之和
        return unit_count * (self.unit_width + self.unit_spacing)

    def _update_content_layer(self, unit_count, thumbnail_total_width):
        # 生成中间层单元（绘制矩形来表示单元）
        self.content_layer.setFixedSize(thumbnail_total_width, 30)
        
        # 清除现有的单元组件（如果有）
        for child in self.content_layer.children():
            child.deleteLater()
            
        # 为每个单元创建一个矩形标签
        for i in range(unit_count):
            unit = QLabel(self.content_layer)
            unit.setAttribute(Qt.WA_TransparentForMouseEvents)
            unit.setStyleSheet("background: rgba(180, 180, 180, 0.5); border: 1px solid #999;")
            x_pos = i * (self.unit_width + self.unit_spacing) + self.half_unit_spacing
            unit.setGeometry(x_pos, 0, self.unit_width, 30)
            unit.show()

    def mousePressEvent(self, event):
        """处理整个导航条的鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 将点击位置转换到内容层坐标系
            click_content_x = event.x() + self.content_offset
            
            # 计算marker在内容层的绝对位置
            marker_content_left = self.marker.x() + self.content_offset
            marker_content_right = marker_content_left + self.marker.width()
            
            self.dragging = True
            #self.update()
            if not (marker_content_left <= click_content_x <= marker_content_right):
                # 点击在marker外部：立即跳转
                self._handle_drag_start(click_content_x, is_quick_jump=True)
            else:
                # 点击在marker内部：记录初始位置
                self._handle_drag_start(click_content_x)
                

    def _handle_drag_start(self, content_x, is_quick_jump=False):
        """处理拖动开始逻辑"""
        marker_width = self.marker.width()
        
        if is_quick_jump:
            # 快速跳转：将marker中心对准点击位置
            new_content_x = content_x - marker_width / 2
            # 记录拖动起始参数
            self.drag_start_pos = content_x
            self.initial_marker_x = new_content_x
        else:
            # 正常拖动：记录初始偏移
            self.drag_start_pos = content_x
            self.initial_marker_x = self.marker.x() + self.content_offset
            new_content_x = self.initial_marker_x
            
        # 计算有效范围
        max_travel = self.thumbnail_total_width - marker_width
        new_content_x = max(0, min(new_content_x, max_travel))
        
        # 更新界面位置
        #self.marker.move(new_content_x - self.content_offset, self.marker.y())
        
        # 立即通知父组件
        print("drag")
        if self.parent() and hasattr(self.parent(), 'handle_marker_drag'):
            try:
                progress = new_content_x / max_travel
            except ZeroDivisionError:
                progress = 0
            self.parent().handle_marker_drag(progress)
    def mouseMoveEvent(self, event):
        """处理导航条的鼠标移动事件"""
        if self.dragging:
            # 转换到内容层坐标系
            current_content_x = event.x() + self.content_offset
            delta = current_content_x - self.drag_start_pos
            
            # 计算新位置
            new_content_x = self.initial_marker_x + delta
            marker_width = self.marker.width()
            max_travel = self.thumbnail_total_width - marker_width
            new_content_x = max(0, min(new_content_x, max_travel))
            
            # 更新界面位置
            #self.marker.move(new_content_x - self.content_offset, self.marker.y())
            
            # 通知父组件
            if self.parent() and hasattr(self.parent(), 'handle_marker_drag'):
                try:
                    progress = new_content_x / max_travel
                except ZeroDivisionError:
                    progress = 0
                self.parent().handle_marker_drag(progress)

    def mouseReleaseEvent(self, event):
        """结束拖动状态"""
        print("release")
        self.dragging = False
        self.drag_start_pos = None
        self.initial_marker_x = 0

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(Qt.black)  # 设置线条颜色为黑色
        pen.setWidth(1)       # 设置线条宽度
        painter.setPen(pen)
        
        # 绘制从左下到右上的斜线
        painter.drawLine(0, self.height(), self.width(), 0)