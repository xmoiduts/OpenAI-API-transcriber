# Translation Unit Panel

这是一个用PyQt5实现的翻译面板组件，专为按行对齐的原文-译文翻译工作设计。

## 主要功能

- **行对齐翻译**：原文和译文文本编辑器保持行对齐，即使在文本折行的情况下
- **多单元水平排列**：支持将长文本分割为多个翻译单元，水平排列浏览
- **状态可视化**：通过颜色条显示每行的翻译状态（已翻译、未翻译、翻译失败）
- **导航栏**：提供单元缩略视图，支持快速导航
- **加载与保存**：支持从文件加载原文并保存译文

## 组件结构

- `TranslationUnit`：翻译单元，包含原文和译文编辑面板
- `SyncedTextEdit`：同步的文本编辑器，处理行对齐和滚动同步
- `TranslationUnitsContainer`：翻译单元容器，水平排列多个翻译单元
- `TranslationStatusStrip`：翻译状态条，显示每行的翻译状态
- `NavigationBar`：导航条，显示翻译单元的缩略图

## 对中文（CJK字符）的特殊处理

- 使用`QTextOption.WrapAnywhere`实现按字符而非按单词换行
- 通过自定义的`SyncedTextEdit`处理东亚文字的折行问题
- 复制时自动过滤零宽控制字符，确保文本干净

## 运行演示

```bash
# 安装依赖
pip install PyQt5

# 运行演示程序
# cd 项目根目录
python run_translation_demo.py
```

## 开发环境

- Python 3.6+
- PyQt5 5.15+
- 操作系统：Windows/macOS/Linux

## 使用方法

1. 点击左侧面板中的"Open from file"加载原文文件
2. 点击"→"按钮将内容加载到工作区
3. 在原文面板中编辑或查看原文
4. 点击"Translate"按钮开始翻译（演示模式下会自动生成翻译）
5. 在译文面板中编辑或查看译文
6. 使用顶部导航条在不同翻译单元间导航