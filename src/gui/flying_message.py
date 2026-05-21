from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt, QTimer
from PyQt5 import sip

class FlyingLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0);
            color: rgba(255, 255, 255, 0);
            border-radius: 10px;
            padding: 5px;
        """)
        self.setWordWrap(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.opacity = 0.0
        self.y_position = 0
        self.animation_state = "fly_in"

    def animate(self):
        if self.animation_state == "fly_in":
            self.opacity = min(1.0, self.opacity + 0.1)
            self.y_position = max(self.target_y, self.y_position - 2)
            self.move(self.x(), int(self.y_position))
            self.update_style()
            
            if self.opacity >= 1.0 and self.y_position <= self.target_y:
                self.animation_state = "stay"
                self.timer.stop()
                if hasattr(self, "stay_timer"):
                    self.stay_timer.start()
        
        elif self.animation_state == "fade_out":
            self.opacity = max(0.0, self.opacity - 0.1)
            self.update_style()
            
            if self.opacity <= 0:
                self.hide()
                self.timer.stop()

    def update_style(self):
        self.setStyleSheet(f"""
            background-color: rgba(0, 0, 0, {int(180 * self.opacity)});
            color: rgba(255, 255, 255, {int(255 * self.opacity)});
            border-radius: 10px;
            padding: 5px;
        """)

    def start_fade_out(self):
        self.animation_state = "fade_out"
        self.timer.start(16)

def show_flying_message(parent, message, duration=4000):
    if hasattr(parent, 'current_flying_label') and parent.current_flying_label and not sip.isdeleted(parent.current_flying_label):
        parent.current_flying_label.deleteLater()
    
    parent.current_flying_label = FlyingLabel(parent)
    parent.current_flying_label.setText(message)
    parent.current_flying_label.adjustSize()
    
    width = parent.current_flying_label.width()
    height = parent.current_flying_label.height()
    
    start_y = int(parent.height() * 0.53)
    parent.current_flying_label.move(parent.width() // 2 - width // 2, start_y)
    parent.current_flying_label.y_position = start_y

    parent.current_flying_label.target_y = int(parent.height() * 0.5 - height // 2)
    parent.current_flying_label.raise_()

    parent.current_flying_label.show()
    parent.current_flying_label.timer.start(16)

    parent.current_flying_label.stay_timer = QTimer(parent.current_flying_label)
    parent.current_flying_label.stay_timer.setSingleShot(True)
    parent.current_flying_label.stay_timer.timeout.connect(parent.current_flying_label.start_fade_out)
    parent.current_flying_label.stay_timer.start(duration)


def show_countdown_message(parent, seconds, on_finished=None, anchor="upper-middle"):
    if hasattr(parent, 'current_flying_label') and parent.current_flying_label and not sip.isdeleted(parent.current_flying_label):
        parent.current_flying_label.deleteLater()

    label = FlyingLabel(parent)
    label.countdown_remaining = max(int(seconds), 0)
    parent.current_flying_label = label

    def update_text():
        if sip.isdeleted(label):
            return
        label.setText(f"Waiting for {label.countdown_remaining} seconds")
        label.adjustSize()
        _position_label(parent, label, anchor)

    def tick():
        if sip.isdeleted(label):
            timer.stop()
            return
        label.countdown_remaining -= 1
        if label.countdown_remaining <= 0:
            timer.stop()
            label.start_fade_out()
            if on_finished is not None:
                on_finished()
            return
        update_text()

    update_text()
    label.raise_()
    label.show()
    label.timer.start(16)

    timer = QTimer(label)
    timer.timeout.connect(tick)
    timer.start(1000)
    label.countdown_timer = timer
    return label


def _position_label(parent, label, anchor):
    width = label.width()
    height = label.height()
    x = parent.width() // 2 - width // 2
    if anchor == "upper-middle":
        target_y = max(8, int(parent.height() * 0.16 - height // 2))
        start_y = target_y + 12
    else:
        start_y = int(parent.height() * 0.53)
        target_y = int(parent.height() * 0.5 - height // 2)

    label.move(x, start_y)
    label.y_position = start_y
    label.target_y = target_y