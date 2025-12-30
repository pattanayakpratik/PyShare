<div align="center">
<img src="Screenshots/banner.png" alt="PyShare Banner" width="100%">
  <h1 align="center">
  
  <img src="Screenshots\app_icon.png" alt="PyShare Logo" width="32">
  PyShare
</h1>
  <strong>A lightweight, high-speed Python tool to share files between PC and Mobile over Wi-Fi.</strong>

  <p>
    <a href="#-download-recommended">Download</a> •
    <a href="#-features">Features</a> •
    <a href="#%EF%B8%8F-usage">Usage</a> •
    <a href="#%EF%B8%8F-installation-for-developers">Installation</a>
  </p>

</div>

<br>

**PyShare** is a modern, ultra-fast local file sharing tool. The latest version features a stunning **Glassmorphism UI**, real-time file searching, drag-and-drop uploads, and automatic Dark/Light mode switching.


## 📥 Download (Recommended)

**Windows Users:** For the best experience, download the standalone **PyShare.exe** from the [Latest Releases](https://github.com/pattanayakpratik/pyshare/releases) page.

* **No Setup Required:** Run the app directly without installing Python.
* **Professional Branding:** Includes a custom application icon.
* **Self-Contained:** All assets (HTML/CSS/JS) and dependencies (pyqrcode, pypng) are bundled inside.

### 🚀 Standalone Executable

* **PyShare (Windows EXE)** 👉 **[Download PyShare.exe](https://github.com/pattanayakpratik/PyShare/releases/download/v2.2.0/PyShare.exe)**

### 📦 Compressed Archives (Recommended if EXE is blocked)

* **PyShare (Windows ZIP)** 👉 **[Download PyShare.zip](https://github.com/pattanayakpratik/PyShare/releases/download/v2.2.0/PyShare.zip)**
* **PyShare (Linux/macOS TAR)** 👉 **[Download PyShare.tar.gz](https://github.com/pattanayakpratik/PyShare/releases/download/v2.2.0/PyShare.tar.gz)**

### 💻 Source Code (For Developers)

* **Source (ZIP)** 👉 **[v2.2.0.zip](https://github.com/pattanayakpratik/PyShare/archive/refs/tags/v2.2.0.zip)**
* **Source (TAR)** 👉 **[v2.2.0.tar.gz](https://github.com/pattanayakpratik/PyShare/archive/refs/tags/v2.2.0.tar.gz)**

---

*⚠️ **Note:** If Windows SmartScreen shows a warning, click **More info → Run anyway**. The app is entirely local and safe to use.*

---

## 🆕 What's New (v2.2.0)
- **Fixed Execution Error:** Resolved the `ModuleNotFoundError: No module named 'pyqrcode'` that affected previous standalone versions.
- **Improved Portability:** Now providing `.zip` and `.tar.gz` archives to ensure compatibility across Windows and Linux.
- **Self-Contained:** All assets (HTML/CSS/JS) and Python dependencies are now correctly bundled within the executable.

## 🚀 Features

- **🎨 Modern Glassmorphism UI:** A beautiful interface with frosted glass effects and smooth animations.
- **📂 Desktop Integration:** Automatically creates a `PyShare_Files` folder on your **Desktop** and opens it for you.
- **🚀 Smart Launch:** Automatically opens your web browser to the correct URL when started.
- **🔌 Port Protection:** Automatically finds an open port (8010-8020) if the default is busy.
- **🌗 Dark & Light Themes:** Automatically detects system preference or toggle manually.
- **📂 Smart File Management:**
  - **Dual Lists:** Clearly separates "Files on PC" from "Received from Phone".
  - **Real-Time Search:** Filter through hundreds of files instantly as you type.
- **☁️ Drag & Drop Uploads:** Simply drag files into the box to upload from phone or PC.
- **📊 Visual Progress Bar:** See upload percentages in real-time.
- **📱 Easy Connection:** Scan the generated QR code to connect instantly.
- **🔐 Offline Privacy:** Works entirely over LAN (Local Area Network)—no internet required.

## 📸 Screenshots

### 🖥️ Desktop View
<img src="Screenshots/desktop.png" width="80%" alt="Desktop Dashboard">

### 📱 Mobile View
<img src="Screenshots/mobile.jpg" width="200" alt="Mobile Home"> <img src="Screenshots/mobile2.jpg" width="200" alt="Mobile Files"> <img src="Screenshots/mobile3.jpg" width="200" alt="Mobile Dark Mode"> <img src="Screenshots/mobile4.jpg" width="200" alt="Mobile Uploads">

## 🖥️ Usage

### 1. Start PyShare
* **App:** Double-click `PyShare.exe`.
* **Source:** Open your terminal in the `PyShare` folder and run `python main.py`.

### 2. Connect via Phone
* **QR Code:** The app displays a QR code automatically. Scan it with your phone to open the interface.
* **Manual URL:** You can also enter the URL shown in the terminal (e.g., `http://192.168.1.10:8010`) into your mobile browser.
* *Tip: You can also click the 📱 button in the web app to see the QR code.*

### 3. Transfer Files
* **To PC:** Drag and drop files into the **"Send to PC"** box on your phone. They will appear in `Desktop/PyShare_Files/From_Phone`.
* **To Phone:** Place files in `Desktop/PyShare_Files/From_PC`. They will appear in the **"Files on PC"** list on your phone instantly.

### 4. Stop Server
* **Web UI:** Click the **🛑 Disconnect Server** button on the web interface.
* **Terminal:** Press `Ctrl+C` in your terminal window.

## 🛠️ Installation (For Developers)

1. **Install Python 3.x** if you haven't already.
2. Clone this repository and navigate to the folder.
3. Install the dependencies:
```bash
pip install -r requirements.txt

```

*(Note: Requires `pyqrcode` and `pypng`.)*

## ⚠️ Important Notes

* **Same Network:** Your PC and Phone must be connected to the **same Wi-Fi network**.
* **Firewall:** If you cannot connect, ensure your PC's firewall allows Python/PyShare to accept incoming connections on port `8010`.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

