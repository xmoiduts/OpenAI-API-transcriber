from enum import Enum
from typing import List, Tuple, Dict, Optional
from PyQt5.QtCore import QObject, pyqtSignal


class SliceStatus(Enum):
    IDLE = "idle"
    SELECTED = "selected"
    TRANSCRIBING = "transcribing"
    DONE = "done"
    FAILURE = "failure"


class SliceInfo:
    """单个slice的信息"""
    def __init__(self, start_time: float, duration: float, actual_start: float = None):
        self.start_time = start_time  # 显示的开始时间
        self.duration = duration      # 持续时间
        self.actual_start = actual_start if actual_start is not None else start_time  # 实际开始时间
        self.status = SliceStatus.IDLE
        
    def __repr__(self):
        return f"SliceInfo(start={self.start_time}, duration={self.duration}, actual={self.actual_start}, status={self.status.value})"


class SliceManager(QObject):
    """管理所有slice的状态和信息"""
    
    # 信号：slice状态改变时发出
    slice_status_changed = pyqtSignal(int, str)  # (slice_index, new_status)
    slices_updated = pyqtSignal()  # 当slice列表被更新时发出
    
    def __init__(self):
        super().__init__()
        self.slices: List[SliceInfo] = []
    
    def set_slices(self, time_slices: List[Tuple[float, float]], actual_starts: List[float] = None):
        """设置slice列表
        
        Args:
            time_slices: [(start_time, duration), ...] 的列表
            actual_starts: 实际开始时间列表，如果不提供则使用start_time
        """
        self.slices.clear()
        
        if actual_starts is None:
            actual_starts = [start for start, _ in time_slices]
        
        for i, (start, duration) in enumerate(time_slices):
            actual_start = actual_starts[i] if i < len(actual_starts) else start
            slice_info = SliceInfo(start, duration, actual_start)
            self.slices.append(slice_info)
        
        self.slices_updated.emit()
    
    def get_slice_count(self) -> int:
        """获取slice数量"""
        return len(self.slices)
    
    def get_slice(self, index: int) -> Optional[SliceInfo]:
        """获取指定索引的slice"""
        if 0 <= index < len(self.slices):
            return self.slices[index]
        return None
    
    def set_slice_status(self, index: int, status: SliceStatus):
        """设置slice状态"""
        if 0 <= index < len(self.slices):
            old_status = self.slices[index].status
            self.slices[index].status = status
            if old_status != status:
                self.slice_status_changed.emit(index, status.value)
    
    def get_slice_status(self, index: int) -> Optional[SliceStatus]:
        """获取slice状态"""
        if 0 <= index < len(self.slices):
            return self.slices[index].status
        return None
    
    def get_all_statuses(self) -> Dict[int, SliceStatus]:
        """获取所有slice的状态"""
        return {i: slice_info.status for i, slice_info in enumerate(self.slices)}
    
    def get_slices_by_status(self, status: SliceStatus) -> List[int]:
        """获取指定状态的slice索引列表"""
        return [i for i, slice_info in enumerate(self.slices) if slice_info.status == status]
    
    def reset_slice_to_idle(self, index: int):
        """重置slice为idle状态"""
        self.set_slice_status(index, SliceStatus.IDLE)
    
    def toggle_slice_selection(self, index: int):
        """切换slice的选择状态（idle <-> selected）"""
        if 0 <= index < len(self.slices):
            current_status = self.slices[index].status
            if current_status == SliceStatus.IDLE:
                self.set_slice_status(index, SliceStatus.SELECTED)
            elif current_status == SliceStatus.SELECTED:
                self.set_slice_status(index, SliceStatus.IDLE)
    
    def get_selected_slices(self) -> List[int]:
        """获取所有被选中的slice索引"""
        return self.get_slices_by_status(SliceStatus.SELECTED)
    
    def get_transcribable_slices(self) -> List[int]:
        """获取所有可以转录的slice（非transcribing和done状态）"""
        transcribable = []
        for i, slice_info in enumerate(self.slices):
            if slice_info.status not in [SliceStatus.TRANSCRIBING, SliceStatus.DONE]:
                transcribable.append(i)
        return transcribable
    
    def get_legacy_format(self) -> Tuple[List[Tuple[float, float]], List[float]]:
        """获取兼容旧格式的数据，用于与现有代码兼容"""
        time_slices = [(slice_info.start_time, slice_info.duration) for slice_info in self.slices]
        actual_starts = [slice_info.actual_start for slice_info in self.slices]
        return time_slices, actual_starts
    
    def clear(self):
        """清空所有slice"""
        self.slices.clear()
        self.slices_updated.emit() 