from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt

class DraggableLabel(QLabel):
    def __init__(self, text, input_box):
        super().__init__(text)
        self.input_box = input_box
        self.dragging = False
        self.last_pos = None
        self.setCursor(Qt.SizeHorCursor)  # 设置左右箭头光标
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_pos = event.globalPos()
            
    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.last_pos = None
        
    def mouseMoveEvent(self, event):
        if self.dragging and self.last_pos:
            delta = event.globalPos().x() - self.last_pos.x()
            value_change = (abs(delta) // 10) * (1 if delta > 0 else -1)

            if value_change != 0:
                # 获取当前值
                try:
                    current_value = int(self.input_box.text() or '0')
                except ValueError:
                    current_value = 0
                    
                # 根据拖动距离调整值（每10像素改变1个单位）
                new_value = max(0, current_value + value_change)
                
                # 根据HMS类型设置上限         
                new_value = min(new_value, 59)
                    
                self.input_box.setText(str(new_value))
                self.last_pos = event.globalPos()