from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QScrollArea, QApplication,
    QVBoxLayout, QPushButton, QLabel, QFrame
)

from src.gui.styles.style_manager import get_scrollbar_stylesheet
from src.gui.components.translation_unit import TranslationUnit

class TranslationUnitsContainer(QScrollArea):
    """
    翻译单元容器，水平排列多个翻译单元
    提供添加、移除翻译单元的功能
    """
    unitAdded = pyqtSignal(TranslationUnit)
    unitRemoved = pyqtSignal(str)  # 发送被移除的单元ID
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.units = []  # 存储所有翻译单元
        self.init_ui()
    
    def init_ui(self):
        # 设置滚动区域属性
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建容器widget
        self.container = QWidget()
        self.container_layout = QHBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(1)  # 单元之间的间距
        self.container_layout.addStretch(1)  # 右侧弹性空间，确保单元靠左对齐
        
        # 设置容器为滚动区域的内容
        self.setWidget(self.container)
        
        # 应用样式
        self.setStyleSheet("""
            QScrollArea {
                background-color: #f0f0f0;
                border: none;
            }
        """ + get_scrollbar_stylesheet())
        
        # 禁用水平滚动条但保持垂直滚动
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    
    def add_unit(self, unit_id=None, original_text="", translation_text=""):
        """添加新的翻译单元"""
        # 创建新的翻译单元
        unit = TranslationUnit(unit_id)
        
        # 设置内容
        if original_text or translation_text:
            unit.set_content(original_text, translation_text)
        
        # 添加到布局中，确保添加在stretch之前
        self.container_layout.insertWidget(len(self.units), unit)
        self.units.append(unit)
        
        # 更新容器宽度以适应新增的单元
        QTimer.singleShot(10, self._update_container_width)
        
        # 发送信号
        self.unitAdded.emit(unit)
        
        return unit
    
    def remove_unit(self, index):
        """移除指定索引的翻译单元"""
        if 0 <= index < len(self.units):
            unit = self.units.pop(index)
            unit_id = unit.unit_id
            
            # 从布局中移除
            self.container_layout.removeWidget(unit)
            unit.deleteLater()
            
            # 更新容器宽度
            self._update_container_width()
            
            # 发送信号
            self.unitRemoved.emit(unit_id)
    
    def _update_container_width(self):
        """更新容器宽度以适应所有翻译单元"""
        if not self.units:
            # 如果没有单元，设置一个默认宽度
            min_width = 1200
        else:
            # 计算所有单元的总宽度
            total_width = sum(unit.width() for unit in self.units)
            
            # 添加额外空间以确保所有单元都可见
            padding = 20 * len(self.units)
            
            # 计算最小宽度
            min_width = total_width + padding
        
        # 设置容器最小宽度
        self.container.setMinimumWidth(min_width)
        
        # 设置滚动区域的宽度与容器相同
        self.setMinimumWidth(min_width)
        
        # 通知父级容器更新宽度
        if self.parent() and hasattr(self.parent(), 'update_container_width'):
            self.parent().update_container_width(min_width)
    
    def get_unit_by_id(self, unit_id):
        """根据ID获取翻译单元"""
        for unit in self.units:
            if unit.unit_id == unit_id:
                return unit
        return None
    
    def clear(self):
        """清除所有翻译单元"""
        for unit in self.units[:]:
            self.remove_unit(0)  # 始终移除第一个，因为索引会自动更新


class TranslationWorkspacePanel(QWidget):
    """
    翻译工作区面板，包含导航条和翻译单元容器
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建导航条
        self.navigation_bar = NavigationBar()
        layout.addWidget(self.navigation_bar)
        
        # 创建翻译单元容器
        self.units_container = TranslationUnitsContainer()
        layout.addWidget(self.units_container)
        
        # 连接单元添加/移除信号
        self.units_container.unitAdded.connect(self.handle_unit_added)
        self.units_container.unitRemoved.connect(self.handle_unit_removed)
    
    def handle_unit_added(self, unit):
        """处理单元添加事件"""
        self.navigation_bar.update_unit_count(len(self.units_container.units))
    
    def handle_unit_removed(self, unit_id):
        """处理单元移除事件"""
        self.navigation_bar.update_unit_count(len(self.units_container.units))
    
    def add_unit(self, unit_id=None, original_text="", translation_text=""):
        """添加新的翻译单元"""
        return self.units_container.add_unit(unit_id, original_text, translation_text)
        
    def update_container_width(self, width):
        """处理容器宽度变化"""
        # 设置面板宽度与容器相同
        self.setMinimumWidth(width)
        
        # 通知父级更新布局（如果存在）
        if self.parent() and hasattr(self.parent(), 'update_nav_layout'):
            self.parent().update_nav_layout()


class NavigationBar(QFrame):
    """
    简化版导航条，显示翻译单元的缩略图
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.unit_count = 0
        self.init_ui()
    
    def init_ui(self):
        self.setMinimumHeight(30)
        self.setMaximumHeight(30)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        
        self.add_unit_button = QPushButton("+")
        self.add_unit_button.setToolTip("Add new translation unit")
        self.add_unit_button.setFixedSize(25, 25)
        
        self.unit_label = QLabel("Units: 0")
        
        layout.addWidget(self.unit_label)
        layout.addStretch(1)
        layout.addWidget(self.add_unit_button)
        
        # 设置样式
        self.setStyleSheet("""
            NavigationBar {
                background-color: #e0e0e0;
                border-bottom: 1px solid #ccc;
            }
            QPushButton {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #eaeaea;
            }
        """)
    
    def update_unit_count(self, count):
        """更新单元数量显示"""
        self.unit_count = count
        self.unit_label.setText(f"Units: {count}")


# 测试代码
if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    # 创建测试文本
    sample_texts = [
        # 单元1
        {
            "original": """{L1} This is the first translation unit.
{L2} It contains some sample text for testing.
{L3} The line alignment should work properly.""",
            "translation": """{L1} 这是第一个翻译单元。
{L2} 它包含一些用于测试的示例文本。
{L3} 行对齐应该正常工作。"""
        },
        # 单元2
        {
            "original": """{L4} This is the second translation unit.
{L5} It demonstrates how multiple units are arranged horizontally.
{L6} Users can scroll horizontally to view all units.""",
            "translation": """{L4} 这是第二个翻译单元。
{L5} 它演示了多个单元如何水平排列。
{L6} 用户可以水平滚动查看所有单元。"""
        },
        # 单元3
        {
            "original": """{L7} This is the third translation unit.
{L8} The navigation bar above shows an overview of all units.
{L9} Each unit can be translated independently.""",
            "translation": """{L7} 这是第三个翻译单元。
{L8} 上方的导航条显示所有单元的概览。
{L9} 每个单元可以独立翻译。"""
        }
    ]
    
    # 创建工作区面板
    workspace = TranslationWorkspacePanel()
    
    # 添加测试单元
    for i, text in enumerate(sample_texts):
        unit_id = f"L{i*3+1}-L{i*3+3}"
        workspace.add_unit(unit_id, text["original"], text["translation"])
    
    # 连接添加按钮信号
    workspace.navigation_bar.add_unit_button.clicked.connect(
        lambda: workspace.add_unit(f"L{len(workspace.units_container.units)*3+1}-L{len(workspace.units_container.units)*3+3}")
    )
    
    # 显示工作区
    workspace.resize(1200, 800)
    workspace.show()
    
    sys.exit(app.exec_()) 