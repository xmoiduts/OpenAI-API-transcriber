from PyQt5.QtWidgets import QWidget

class TabInterface(QWidget):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def update_from_other_tab(self, data):
        # Implement in subclasses if needed
        pass
