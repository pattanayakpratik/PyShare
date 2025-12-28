<div align="center">

  <h1>⚡ PyShare 📲</h1>

  <img src="Screenshots/banner.svg" alt="PyShare Banner" width="100%">

  <br><br>

  <strong>A lightweight, high-speed Python tool to share files between PC and Mobile over Wi-Fi.</strong>

  <p>
    <a href="#-features">Features</a> •
    <a href="#%EF%B8%8F-installation">Installation</a> •
    <a href="#%EF%B8%8F-usage">Usage</a>
  </p>

</div>

<br>

**PyShare** is a modern, ultra-fast local file sharing tool. The latest version (**v2.1**) features a stunning **Glassmorphism UI**, real-time file searching, drag-and-drop uploads, and automatic Dark/Light mode switching.

## 🚀 Features

- **🎨 Modern Glassmorphism UI:** A beautiful interface with frosted glass effects, gradients, and smooth animations.
- **📂 Desktop Integration:** Automatically creates a `PyShare_Files` folder on your **Desktop** and opens it for you.
- **🚀 Smart Launch:** Automatically opens your web browser to the correct URL when started.
- **🔌 Port Conflict Protection:** Automatically finds an open port (8010-8020) if the default is busy.
- **🌗 Dark & Light Themes:** Automatically detects your system preference, or toggle manually.
- **⚡ Single Page Application (SPA):** Instant interactions without page reloads.
- **📂 Smart File Management:**
  - **Dual Lists:** Clearly separates "Files on PC" from "Received from Phone".
  - **Real-Time Search:** Filter through hundreds of files instantly as you type.
- **☁️ Drag & Drop Uploads:** Simply drag files into the box to upload from phone or PC.
- **📊 Visual Progress Bar:** See upload percentages in real-time.
- **📱 Easy Connection:** Scan the generated QR code to connect instantly.
- **🔐 Offline Privacy:** Works entirely over LAN (Local Area Network) – no internet required.
- **🔇 Silent Mode:** Keeps your terminal clean by only showing active transfers (no spammy logs).

## 📸 Screenshots

### 🖥️ Desktop View
*Clean 3-column dashboard*

<img src="Screenshots/desktop.png" width="80%" alt="Desktop Dashboard">
<br><br>
<img src="Screenshots/desktop2.png" width="80%" alt="Desktop File List">

### 📱 Mobile View
*Responsive single-column layout*

<img src="Screenshots/mobile.jpg" width="200" alt="Mobile Home"> <img src="Screenshots/mobile2.jpg" width="200" alt="Mobile Files"> <img src="Screenshots/mobile3.jpg" width="200" alt="Mobile Dark Mode"> <img src="Screenshots/mobile4.jpg" width="200" alt="Mobile Uploads">

## 📂 Directory Structure

```text
PyShare/
├── main.py             # Main Server Script (Backend)
├── index.html          # Frontend Interface (HTML5)
├── styles.css          # Glassmorphism Styling (CSS3)
├── scripts.js          # App Logic (Search, Uploads, API)
├── requirements.txt    # Dependencies
└── ...

```
*(Note: All shared files are now stored in Desktop/PyShare_Files automatically.)*

## 🛠️ Installation

1. **Install Python 3.x** if you haven't already.
2. Clone this repository or download the files.
3. Install the dependencies (mainly for QR code generation):

```bash
pip install -r requirements.txt

```

*(Note: If you don't have a `requirements.txt`, simply run: `pip install pyqrcode pypng`)*

## 🖥️ Usage

1. **Start PyShare:**
Open your terminal/command prompt in the `PyShare` folder and run:
```bash
python main.py

```


2. **Connect via Phone:**
* The terminal will display a URL (e.g., `http://192.168.1.10:8010`).
* A `qrcode.png` file is generated. **Scan it** with your phone to open the app.
* *Tip: You can also click the 📱 button in the web app to see the QR code.*


3. **Transfer Files:**
* **Phone → PC:** Drag and drop files into the **"Send to PC"** box. They will appear in `SharedFiles/From_Phone`.
* **PC → Phone:** Place files in `SharedFiles/From_PC`. They will appear in the "Files on PC" list instantly.


4. **Stop Server:**
* Click the **🛑 Disconnect Server** button on the web interface, or press `Ctrl+C` in the terminal.



## ⚠️ Important Notes

* **Same Network:** Your PC and Phone must be connected to the **same WiFi network**.
* **Firewall:** If you cannot connect, ensure your PC's firewall allows Python to accept incoming connections on port `8010`.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
