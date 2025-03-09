from PyQt5.QtWidgets import (QWidget, QScrollArea, QHBoxLayout, QVBoxLayout,
                            QFrame, QLabel, QSizePolicy, QApplication,
                            QPushButton, QFileDialog)
from PyQt5.QtCore import Qt, QPoint, QSize, QTimer
import random
import re
from .tab_interface import TabInterface
from .components.nav_bar import NavigationBar
from .styles.style_manager import get_translation_button_stylesheet, get_scrollbar_stylesheet  # Import the style

# 导入翻译单元相关组件
try:
    from src.gui.components.translation_unit import TranslationUnit
    from src.gui.components.translation_units_container import TranslationWorkspacePanel
    from src.gui.components.translation_status_strip import TranslationStatusStrip
except ImportError:
    # 如果作为独立模块运行
    from .components.translation_unit import TranslationUnit
    from .components.translation_units_container import TranslationWorkspacePanel
    from .components.translation_status_strip import TranslationStatusStrip

# 添加样式导入
from src.gui.styles.style_manager import get_scrollbar_stylesheet
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
        
        # 应用美化的滚动条样式
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #f8f8f8;
                border: none;
            }
        """ + get_scrollbar_stylesheet())
        
        # 设置Tab布局
        layout = QVBoxLayout()
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 当窗口大小变化时，通知主面板更新导航条
        if hasattr(self, 'main_panel'):
            self.main_panel.workspace_panel.update_nav_layout()
            
    def update_from_other_tab(self, data):
        """从其他标签页接收数据"""
        # 这里可以处理来自其他标签页的数据，如接收transcription结果
        if 'lines' in data:
            self.main_panel.load_lines(data['lines'])

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
        self.source_panel = SourcePanel()
        self.source_panel.setFixedWidth(self.source_width)
        self.source_panel.load_to_workspace_btn.clicked.connect(self.load_dummy_data)
        self.main_layout.addWidget(self.source_panel)

        # 状态条（固定宽度）
        self.status_strip = TranslationStatusStrip()
        self.status_strip.setFixedWidth(self.status_width)
        self.main_layout.addWidget(self.status_strip)

        # 工作区面板
        self.workspace_panel = WorkspacePanel(self)
        self.main_layout.addWidget(self.workspace_panel)

        # 初始化状态条
        self.init_status_strip()

        # 设置总宽度
        total_width = self.source_width + self.status_width + self.workspace_panel.width()
        self.setFixedWidth(total_width)
        self.setLayout(self.main_layout)

    def init_status_strip(self):
        """初始化状态条"""
        # 示例数据：300行，全部未翻译
        statuses = ['untranslated'] * 300
        self.status_strip.update_line_statuses(statuses)

    def setup_scroll_behavior(self):
        # 只监听滚动事件来处理status_strip的停靠
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self.handle_scroll)
        
    def handle_scroll(self, value):
        # 计算各组件位移
        scroll_offset = value
        
        # 状态条停靠逻辑
        status_x = max(self.source_width, scroll_offset)
        self.status_strip.move(status_x, 0)
        
        # 工作区联动
        self.workspace_panel.handle_scroll(scroll_offset)

    def update_total_width(self):
        # 动态更新总宽度
        total_width = self.source_width + self.status_width + self.workspace_panel.width()
        self.setFixedWidth(total_width)
        #self.scroll_area.setMinimumWidth(self.scroll_area.viewport().width())
        
    def load_dummy_data(self):
        """加载示例数据到工作区"""
        self.create_sample_units(3)
        # 延迟1秒模拟翻译
        QTimer.singleShot(1000, self.simulate_translation)
        
    def create_sample_units(self, count=3):
        """创建示例翻译单元"""
        # 清空现有单元
        self.workspace_panel.translation_units_panel.units_container.clear()
        
        for i in range(count):
            start_line = i * 100 + 1
            end_line = start_line + 99
            unit_id = f"L{start_line}-L{end_line}"
            
            # 生成示例内容
            original_lines = []
            for j in range(start_line, end_line + 1):
                original_lines.append(f"{{L{j}}} This is line {j} of the original content.")
            
            original_text = "\n".join(original_lines)
            translation_text = ""
            
            self.workspace_panel.translation_units_panel.add_unit(unit_id, original_text, translation_text)
            
        # 更新总宽度
        self.update_total_width()
        
    def simulate_translation(self):
        """模拟翻译过程"""
        # 获取所有单元
        units = self.workspace_panel.translation_units_panel.units_container.units
        if not units:
            return
        
        # 获取当前状态条状态
        statuses = self.status_strip.line_statuses
        
        # 模拟翻译第一个单元
        unit = units[0]
        original_text = unit.original_panel.editor.toPlainText()
        lines = original_text.split('\n')
        
        # 生成翻译结果
        translation_lines = []
        for i, line in enumerate(lines):
            # 从原文中提取行号
            match = re.match(r'{L(\d+)}', line)
            if match:
                line_num = int(match.group(1))
                # 更新状态条
                if 0 <= line_num - 1 < len(statuses):
                    # 90%的概率翻译成功，10%失败
                    if random.random() < 0.9:
                        statuses[line_num - 1] = 'translated'
                        status = 'translated'
                    else:
                        statuses[line_num - 1] = 'failed'
                        status = 'failed'
                    
                    # 根据状态生成不同的翻译
                    if status == 'translated':
                        # 模拟中文翻译
                        translation = f"{{L{line_num}}} 这是原始内容的第 {line_num} 行。"
                    else:
                        # 翻译失败
                        translation = f"{{L{line_num}}} [翻译失败] 原文: {line}"
                    
                    translation_lines.append(translation)
        
        # 更新翻译结果
        translation_text = "\n".join(translation_lines)
        unit.translation_panel.editor.setPlainText(translation_text)
        
        # 更新状态条
        self.status_strip.update_line_statuses(statuses)
        
    def load_lines(self, lines):
        """从外部加载行文本"""
        if not lines:
            return
            
        # 将行文本分组为翻译单元，每100行一组
        line_groups = [lines[i:i+100] for i in range(0, len(lines), 100)]
        
        # 清空现有单元
        self.workspace_panel.translation_units_panel.units_container.clear()
        
        # 创建翻译单元
        for i, group in enumerate(line_groups):
            start_line = i * 100 + 1
            end_line = start_line + len(group) - 1
            unit_id = f"L{start_line}-L{end_line}"
            
            # 将行文本转换为带行号的格式
            original_lines = []
            for j, line in enumerate(group):
                line_num = start_line + j
                original_lines.append(f"{{L{line_num}}} {line}")
                
            original_text = "\n".join(original_lines)
            
            # 添加翻译单元
            self.workspace_panel.translation_units_panel.add_unit(unit_id, original_text)
        
        # 更新状态条
        statuses = ['untranslated'] * len(lines)
        self.status_strip.update_line_statuses(statuses)
        
        # 强制更新工作区布局
        self.workspace_panel.update_nav_layout()
        
        # 更新总宽度
        self.update_total_width()
        
        # 确保滚动到开始位置
        QTimer.singleShot(100, lambda: self.scroll_area.horizontalScrollBar().setValue(0))

class SourcePanel(QFrame):
    """左侧源文件面板"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 设置样式
        self.setStyleSheet(get_translation_button_stylesheet())  # Apply the translation button styles
        
        # 拖放区域
        self.drop_zone = QLabel("Drop files here")
        self.drop_zone.setAlignment(Qt.AlignCenter)
        self.drop_zone.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 2px dashed #ccc;
                border-radius: 5px;
                padding: 20px;
                font-size: 14px;
            }
        """)
        self.drop_zone.setMinimumHeight(100)
        layout.addWidget(self.drop_zone)
        
        # 分隔符
        layout.addWidget(QLabel("or"))
        
        # 打开文件按钮
        self.open_file_btn = QPushButton("Open from file")
        self.open_file_btn.setObjectName("open_file_btn")  # Set object name for styling
        self.open_file_btn.clicked.connect(self.open_file_dialog)
        layout.addWidget(self.open_file_btn)
        
        # 分隔符
        layout.addWidget(QLabel("or"))
        
        # 从上下文加载按钮
        self.load_context_btn = QPushButton("Load from context")
        self.load_context_btn.setObjectName("load_context_btn")  # Set object name for styling
        layout.addWidget(self.load_context_btn)
        
        # 上下文名称
        self.context_name = QLabel("<context name>")
        self.context_name.setStyleSheet("text-decoration: underline;")
        layout.addWidget(self.context_name)
        
        # 加载到工作区按钮
        self.load_to_workspace_btn = QPushButton("→")
        self.load_to_workspace_btn.setObjectName("load_to_workspace_btn")  # Set object name for styling
        self.load_to_workspace_btn.setToolTip("Load to workspace")
        layout.addWidget(self.load_to_workspace_btn)
        
        # 元信息文本框
        layout.addWidget(QLabel("Meta Information:"))
        self.meta_info = QLabel("No content loaded")
        self.meta_info.setWordWrap(True)
        self.meta_info.setStyleSheet("""
            QLabel {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                padding: 5px;
                font-family: monospace;
            }
        """)
        self.meta_info.setMinimumHeight(100)
        layout.addWidget(self.meta_info)
        
        # 添加弹性空间
        layout.addStretch()
        
    
    def open_file_dialog(self):
        """打开文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "文本文件 (*.txt);;所有文件 (*)"
        )
        
        if file_path:
            self.update_meta_info(file_path)
    
    def update_meta_info(self, file_path):
        """更新元信息显示"""
        # 这里只是示例，实际应该读取文件内容并分析
        self.meta_info.setText(f"文件名: {file_path.split('/')[-1]}\n行数: 300")


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

        # 翻译单元面板（包含翻译单元容器）
        self.translation_units_panel = TranslationWorkspacePanel(self)
        layout.addWidget(self.translation_units_panel)
        
        self.setLayout(layout)
        
        # 设置初始宽度
        self.setFixedWidth(1200)  # 初始宽度，会根据翻译单元内容动态调整

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
        #super().resizeEvent(event)
        # 更新导航条布局
        self.update_nav_layout()

    def handle_scroll(self, scroll_offset):
        # 计算导航条的基准x坐标
        nav_bar_x = max(scroll_offset - self.parent_panel.source_width, 0)
        # 导航条在状态条右侧停靠
        self.nav_bar.move(nav_bar_x, 0)
        self.update_nav_layout()

    def update_nav_layout(self):
        """更新导航条布局"""
        # 获取整个滚动区域的可视宽度
        viewport_width = self.parent_panel.scroll_area.viewport().width()
        
        # 获取scroll_offset
        scroll_offset = self.parent_panel.scroll_area.horizontalScrollBar().value()

        # 计算工作区的可视宽度
        if scroll_offset < self.parent_panel.source_width:
            workspace_visible_width = viewport_width - (self.parent_panel.source_width + self.parent_panel.status_width - scroll_offset)
        else:
            workspace_visible_width = viewport_width - self.parent_panel.status_width

        # 计算工作区左侧偏移量
        left_offset = max(0, scroll_offset - (self.parent_panel.source_width + self.parent_panel.status_width))
        
        # 确保不为负
        workspace_visible_width = max(0, workspace_visible_width)
        
        # 获取翻译单元容器的总宽度
        total_width = self.translation_units_panel.units_container.container.width()
        
        # 更新导航条布局
        self.nav_bar.update_layout(
            unit_count=len(self.translation_units_panel.units_container.units),
            external_total_width=total_width,
            external_visible_width=workspace_visible_width,
            left_offset=left_offset
        )
        
        # 更新工作区面板宽度 - 使用容器的实际宽度
        self.setFixedWidth(max(total_width, 1200))
        
        # 通知父面板更新总宽度
        self.parent_panel.update_total_width()

    def add_unit(self, unit_id=None, original_text="", translation_text=""):
        """添加翻译单元的便捷方法"""
        unit = self.translation_units_panel.add_unit(unit_id, original_text, translation_text)
        self.update_nav_layout()
        return unit

    def handle_marker_drag(self, progress_ratio):
        """处理导航条标记拖动事件"""
        # 获取滚动条
        scrollbar = self.parent_panel.scroll_area.horizontalScrollBar()
        
        # 计算工作区的总可滚动范围
        workspace_scroll_range = (self.translation_units_panel.units_container.container.width() - 
                            self.parent_panel.scroll_area.viewport().width())
        
        # 计算目标滚动位置
        target_scroll = self.parent_panel.source_width + self.parent_panel.status_width + int(progress_ratio * workspace_scroll_range)
        
        # 更新滚动条位置
        scrollbar.setValue(target_scroll)