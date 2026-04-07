# Sleep Sense Dashboard - PyQt5 Medical Application

A professional medical-grade sleep monitoring dashboard built with PyQt5.

## 🏥 Features

- **Patient Information Panel**
  - Patient demographics and details
  - Weekly sleep statistics
  - Medical info cards with color-coded categories
  - Tab interface for Info and Raw Data

- **Sleep Monitoring Charts**
  - Real-time signal traces (Abdominal Move, Body Move, Snoring, Apnea, SpO2, Pulse Wave, Body Position, CPAP Pressure)
  - Playback controls
  - Time tracking
  - Export functionality

- **File Management**
  - Upload CSV, EDF, TXT files
  - Download individual files
  - Batch download as ZIP

- **Medical White Theme**
  - Clean, professional medical-grade UI
  - High contrast for readability
  - Color-coded information hierarchy

## 📋 Requirements

- Python 3.8 or higher
- PyQt5 5.15.x
- pyqtgraph 0.13.x
- NumPy 1.24.x

## 🚀 Installation

1. **Install Python dependencies:**

```bash
pip install -r requirements.txt
```

2. **Verify files are present:**
   - `sleep_sense_dashboard.py` - Main application file
   - `sleep_sense_medical_white.qss` - Stylesheet file
   - `requirements.txt` - Python dependencies

## ▶️ Running the Application

```bash
python sleep_sense_dashboard.py
```

## 📁 File Structure

```
sleep-sense-dashboard/
├── sleep_sense_dashboard.py          # Main application
├── sleep_sense_medical_white.qss     # Medical white theme stylesheet
├── requirements.txt                   # Python dependencies
└── README_PYQT5.md                   # This file
```

## 🎨 Customization

### Modifying the Stylesheet

Edit `sleep_sense_medical_white.qss` to customize colors, fonts, and styling:

```css
/* Example: Change primary blue color */
QPushButton {
    background-color: #2563eb;  /* Change this hex color */
}
```

### Adding New Signal Traces

In `sleep_sense_dashboard.py`, modify the `signals` list in `init_charts()`:

```python
signals = [
    ("Signal Name", "color_hex", frequency, amplitude, offset),
    # Add your signals here
]
```

### Customizing Patient Data

Modify the data in `PatientInfoWidget` class:

```python
def create_info_card(self, icon, label_text, value_text, object_name):
    # Customize icons, labels, and values
```

## 🔧 Key Components

### 1. SleepSenseDashboard (Main Window)
- Application header with logo and status badges
- Layout management
- Stylesheet loading

### 2. PatientInfoWidget
- Patient information display
- Tab widget for Info/Data tabs
- File upload/download functionality
- Statistics cards

### 3. SleepMonitorChart
- Real-time signal visualization using PyQtGraph
- Playback controls
- Time tracking
- Status bar

## 🎯 Usage Tips

1. **File Upload:**
   - Click "Choose Files" in the Raw Data tab
   - Select CSV, EDF, or TXT files
   - Files appear in the list below

2. **Chart Interaction:**
   - Scroll horizontally on charts to view history
   - Use playback controls to navigate
   - Export data using the Export button

3. **Resizable Panels:**
   - Drag the separator between patient info and charts
   - Adjust to your preferred layout

## 🐛 Troubleshooting

### Stylesheet not loading
- Ensure `sleep_sense_medical_white.qss` is in the same directory as the Python file
- Check console for "Stylesheet file not found" warning

### Charts not displaying
- Verify pyqtgraph is installed: `pip install pyqtgraph`
- Check NumPy version compatibility

### Import errors
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
- Ensure Python version is 3.8+

## 🔐 Medical Data Considerations

**IMPORTANT:** This is a demonstration application. For production use:

- Implement proper authentication
- Use encrypted data storage
- Follow HIPAA/medical data regulations
- Implement audit logging
- Add data validation
- Use secure file handling

## 📊 Performance

- Optimized for 1600x900+ resolution
- Real-time signal updates at 1 Hz
- Handles 8 concurrent signal traces
- Efficient memory usage with NumPy

## 🎨 Color Scheme

Medical white theme colors:

- Background: `#ffffff` (White)
- Primary: `#2563eb` (Medical Blue)
- Success: `#10b981` (Emerald Green)
- Warning: `#f59e0b` (Amber)
- Danger: `#ef4444` (Red)
- Text: `#111827` (Dark Gray)
- Borders: `#e5e7eb` (Light Gray)

## 📝 License

This is a demonstration application for educational purposes.

## 🤝 Contributing

To modify or extend:

1. Follow PyQt5 best practices
2. Maintain medical-grade UI standards
3. Keep accessibility in mind
4. Document all changes
5. Test thoroughly

## 📧 Support

For issues or questions:
- Check PyQt5 documentation: https://doc.qt.io/qtforpython/
- PyQtGraph docs: https://pyqtgraph.readthedocs.io/

## 🚀 Future Enhancements

Potential additions:
- [ ] Database integration
- [ ] PDF report generation
- [ ] Email notifications
- [ ] Multi-patient management
- [ ] Advanced analytics
- [ ] Real device integration
- [ ] Cloud sync
- [ ] Mobile companion app

---

**Built with PyQt5 for medical professionals** 🏥
