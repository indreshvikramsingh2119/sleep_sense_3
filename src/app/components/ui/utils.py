"""
CSS Utility Functions - Python equivalent of utils.ts
For PyQt5 styling and class management
"""

def cn(*class_names):
    """
    Python equivalent of cn() function from utils.ts
    Combines and merges CSS class names for PyQt5 widgets
    
    Args:
        *class_names: Variable number of class name arguments
        
    Returns:
        str: Combined class name string
    """
    # Flatten and filter out None/empty values
    classes = []
    for class_name in class_names:
        if class_name:
            if isinstance(class_name, (list, tuple)):
                classes.extend([str(c) for c in class_name if c])
            else:
                classes.append(str(class_name))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_classes = []
    for class_name in classes:
        if class_name not in seen:
            unique_classes.append(class_name)
            seen.add(class_name)
    
    return " ".join(unique_classes)

def apply_widget_style(widget, class_names):
    """
    Apply CSS classes to PyQt5 widget
    
    Args:
        widget: PyQt5 widget instance
        class_names: String or list of CSS class names
    """
    if widget:
        combined_classes = cn(class_names)
        if combined_classes:
            widget.setProperty("class", combined_classes)

def get_widget_class(widget):
    """
    Get CSS classes from PyQt5 widget
    
    Args:
        widget: PyQt5 widget instance
        
    Returns:
        str: CSS class names
    """
    if widget:
        return widget.property("class") or ""
    return ""
