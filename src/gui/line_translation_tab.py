from PyQt5.QtWidgets import (QWidget, QScrollArea, QHBoxLayout, QVBoxLayout,
                            QFrame, QLabel, QSizePolicy, QApplication)
from PyQt5.QtCore import Qt, QPoint, QSize
from .tab_interface import TabInterface
from .components.nav_bar import NavigationBar

class LineTranslationTab(TabInterface):
    def __init__(self):
        super().__init__("Line Translation")
        self.init_ui()
        
    def init_ui(self):
        # 主滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # 主内容面板
        self.main_panel = LineTranslationPanel(self.scroll_area)
        self.scroll_area.setWidget(self.main_panel)
        
        # 设置Tab布局
        layout = QVBoxLayout()
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 当窗口大小变化时，通知主面板更新导航条
        if hasattr(self, 'main_panel'):
            self.main_panel.workspace_panel.update_nav_layout()

class LineTranslationPanel(QWidget):
    def __init__(self, scroll_area):
        super().__init__()
        self.scroll_area = scroll_area
        self.source_width = 300
        self.status_width = 40
        self.init_ui()
        self.setup_scroll_behavior()

    def init_ui(self):
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 源面板（固定宽度）
        self.source_panel = QFrame()
        self.source_panel.setFixedWidth(self.source_width)
        self.source_panel.setStyleSheet("background: #f8f8f8; border-right: 1px solid #ddd;")
        self.main_layout.addWidget(self.source_panel)

        # 状态条（固定宽度）
        self.status_strip = QFrame()
        self.status_strip.setFixedWidth(self.status_width)
        self.status_strip.setStyleSheet("background: #e0d0c0; border-right: 1px solid #ddd;")
        self.main_layout.addWidget(self.status_strip)

        # 工作区面板（固定总宽度）
        self.workspace_panel = WorkspacePanel(self)
        self.main_layout.addWidget(self.workspace_panel)

        # 设置总宽度
        total_width = self.source_width + self.status_width + self.workspace_panel.width()
        self.setFixedWidth(total_width)
        self.setLayout(self.main_layout)

    def setup_scroll_behavior(self):
        # 只监听滚动事件来处理status_strip的停靠
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self.handle_scroll)
        
    def handle_scroll(self, value):
        # 计算各组件位移
        scroll_offset = value
        
        # 状态条停靠逻辑
        status_x = max(self.source_width, scroll_offset)
        self.status_strip.move(status_x, 0)
        
        # 工作区（navigation_strip）联动,导航条标记
        self.workspace_panel.handle_scroll(scroll_offset)

        # # 更新导航条标记
        # self.workspace_panel.update_nav_layout(value)

    def update_total_width(self):
        # 动态更新总宽度
        total_width = self.source_width + self.status_width + self.workspace_panel.width()
        self.setFixedWidth(total_width)
        self.scroll_area.setMinimumWidth(self.scroll_area.viewport().width())


class WorkspacePanel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 导航条
        self.nav_bar = NavigationBar()
        layout.addWidget(self.nav_bar)

        # 翻译单元容器
        self.trans_units_container = QWidget()
        self.trans_units_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        
        # 计算总宽度
        unit_count = 6
        unit_width = 400
        self.total_width = unit_count * unit_width
        self.trans_units_container.setFixedWidth(self.total_width)

        # 水平布局配置
        self.units_layout = QHBoxLayout()
        self.units_layout.setContentsMargins(0, 0, 0, 0)
        self.units_layout.setSpacing(0)

        for i in range(unit_count):
            # 创建滚动区域（处理垂直滚动但不显示滚动条）
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 隐藏滚动条
            scroll.setStyleSheet("QScrollArea { border: none; }")  # 移除边框
            scroll.setFixedWidth(unit_width)
            
            # 内容部件（仅保留灰色虚线边框）
            content = QWidget()
            content.setStyleSheet("""
                border: 2px dashed #ccc;
                margin: 10px;
                background: white;
            """)
            content.setFixedWidth(unit_width - 20)  # 考虑滚动条空间
            if i == 2:
                content.setMinimumHeight(2000) # 测试用超大高度
            else:
                content.setMinimumHeight(500)
            
            scroll.setWidget(content)
            self.units_layout.addWidget(scroll)

        self.trans_units_container.setLayout(self.units_layout)
        layout.addWidget(self.trans_units_container)
        self.setLayout(layout)

        # 设置固定宽度
        self.setFixedWidth(self.total_width)

    def wheelEvent(self, event):
        # 垂直滚动处理（即使没有可见滚动条）
        if event.angleDelta().y() != 0:
            scroll = self.focusWidget()
            if isinstance(scroll, QScrollArea):
                v_scroll = scroll.verticalScrollBar()
                v_scroll.setValue(v_scroll.value() - event.angleDelta().y())
        else:
            super().wheelEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 更新导航条布局
        self.update_nav_layout()
        
    # def update_nav_layout(self):
    #     """当窗口大小变化时调用"""
    #     # 获取实际可视宽度（排除左侧固定面板）
    #     viewport_width = self.parent_panel.scroll_area.viewport().width() 
    #     viewport_width -= (self.parent_panel.source_width + self.parent_panel.status_width)
    #     viewport_width = max(viewport_width, 0)
        
    #     total_content_width = self.trans_units_container.width()
    #     scroll_offset = self.parent_panel.scroll_area.horizontalScrollBar().value()
        
    #     # 确保导航条可见时才更新布局
    #     if self.nav_bar.isVisible():
    #         self.nav_bar.update_layout(
    #             unit_count=6,  # 实际应从数据获取
    #             total_content_width=total_content_width,
    #             viewport_width=viewport_width,
    #             scroll_offset=scroll_offset
    #         )

    def handle_scroll(self, scroll_offset):
        # 计算工作区容器的基准x坐标（source_width + status_width）
        base_x = self.parent_panel.source_width + self.parent_panel.status_width
        # 调整翻译单元容器的位置，使其从基准位置开始移动
        #self.trans_units_container.move(0, 40)
        nav_bar_x = max(scroll_offset - self.parent_panel.source_width, 0)
        # nav bar floats inside the workspace panel, but seems like parked at the left edge of the window after status strip.
        self.nav_bar.move(nav_bar_x,0)
        self.update_nav_layout()

    def update_nav_layout(self):
        """更新可视区域标记位置"""
        # 获取整个滚动区域的可视宽度
        viewport_width = self.parent_panel.scroll_area.viewport().width()
        
        # 获取scroll_offset
        scroll_offset = self.parent_panel.scroll_area.horizontalScrollBar().value()

        if scroll_offset < self.parent_panel.source_width:
            workspace_visible_width = viewport_width - (self.parent_panel.source_width + self.parent_panel.status_width - scroll_offset)
        else:
            workspace_visible_width = viewport_width - self.parent_panel.status_width

        # left_offset: offset of the leftmost visible position
        # of the workspace panel from the left edge of the window
        left_offset = scroll_offset - (self.parent_panel.source_width + self.parent_panel.status_width)
        left_offset = max(0, left_offset)

        # status strip is always visible in its full width
        
        workspace_visible_width = max(0, workspace_visible_width)  # 确保不为负
        
        total_width = self.trans_units_container.width()
        
        # 更新导航条布局
        self.nav_bar.update_layout(
            unit_count=6,  # 实际应从数据获取
            external_total_width=total_width,
            external_visible_width=workspace_visible_width,  # 使用workspace的实际可视宽度
            left_offset=left_offset
        )

    def handle_marker_drag(self, progress_ratio):
        """处理导航条标记拖动事件
        
        Args:
            progress_ratio: 拖动进度比例 (0-1)
        """
        # 获取滚动条
        scrollbar = self.parent_panel.scroll_area.horizontalScrollBar()
        #print(f"Progress ratio: {progress_ratio}")
        # 计算工作区的总可滚动范围
        workspace_scroll_range = (self.trans_units_container.width() - 
                            self.parent_panel.scroll_area.viewport().width())
        
        # 计算目标滚动位置
        target_scroll = self.parent_panel.source_width + self.parent_panel.status_width + int(progress_ratio * workspace_scroll_range)
        
        # 更新滚动条位置
        scrollbar.setValue(target_scroll)