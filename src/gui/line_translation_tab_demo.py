import sys
import random
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QScrollArea, QFrame, QLabel, QPushButton, QFileDialog
)

# 修正导入路径
try:
    from src.gui.components.translation_unit import TranslationUnit
    from src.gui.components.translation_units_container import TranslationWorkspacePanel
    from src.gui.components.translation_status_strip import TranslationStatusStrip
except ImportError:
    # 如果作为独立模块运行
    from components.translation_unit import TranslationUnit
    from components.translation_units_container import TranslationWorkspacePanel
    from components.translation_status_strip import TranslationStatusStrip

class SourcePanel(QFrame):
    """左侧源文件面板"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        self.setMinimumWidth(200)
        self.setMaximumWidth(300)
        
        layout = QVBoxLayout(self)
        
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
        self.open_file_btn.clicked.connect(self.open_file_dialog)
        layout.addWidget(self.open_file_btn)
        
        # 分隔符
        layout.addWidget(QLabel("or"))
        
        # 从上下文加载按钮
        self.load_context_btn = QPushButton("Load from context")
        layout.addWidget(self.load_context_btn)
        
        # 上下文名称
        self.context_name = QLabel("<context name>")
        self.context_name.setStyleSheet("text-decoration: underline;")
        layout.addWidget(self.context_name)
        
        # 加载到工作区按钮
        self.load_to_workspace_btn = QPushButton("→")
        self.load_to_workspace_btn.setToolTip("Load to workspace")
        self.load_to_workspace_btn.clicked.connect(self.load_dummy_data)
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
        
        # 设置样式
        self.setStyleSheet("""
            SourcePanel {
                background-color: white;
                border-right: 1px solid #ddd;
            }
        """)
    
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
    
    def load_dummy_data(self):
        """加载示例数据到主窗口"""
        # 获取主窗口引用
        main_window = self.window()
        if hasattr(main_window, 'load_sample_data'):
            main_window.load_sample_data()


class LineTranslationTab(QWidget):
    """行翻译Tab页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建源面板
        self.source_panel = SourcePanel()
        main_layout.addWidget(self.source_panel)
        
        # 创建状态条
        self.status_strip = TranslationStatusStrip()
        main_layout.addWidget(self.status_strip)
        
        # 创建工作区面板
        self.workspace_panel = TranslationWorkspacePanel()
        main_layout.addWidget(self.workspace_panel)
        
        # 设置初始状态
        self.init_status_strip()
    
    def init_status_strip(self):
        """初始化状态条"""
        # 示例数据：300行，全部未翻译
        statuses = ['untranslated'] * 300
        self.status_strip.update_line_statuses(statuses)
    
    def create_sample_units(self, count=3):
        """创建示例翻译单元"""
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
            
            self.workspace_panel.add_unit(unit_id, original_text, translation_text)
    
    def simulate_translation(self):
        """模拟翻译过程"""
        # 获取所有单元
        units = self.workspace_panel.units_container.units
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
            import re
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


class LineTranslationDemo(QMainWindow):
    """行翻译演示程序"""
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Line Translation Demo")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中央组件
        self.tab = LineTranslationTab()
        self.setCentralWidget(self.tab)
        
        # 添加状态栏
        self.statusBar().showMessage("Ready")
    
    def load_sample_data(self):
        """加载示例数据"""
        self.tab.create_sample_units(3)
        self.statusBar().showMessage("Sample data loaded")
        
        # 延迟1秒模拟翻译
        QTimer.singleShot(1000, self.tab.simulate_translation)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = LineTranslationDemo()
    demo.show()
    sys.exit(app.exec_()) 