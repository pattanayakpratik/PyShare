# PyShare 📲

**PyShare** is a lightweight, Python-based tool to share files between your PC and mobile devices over your local WiFi network. It features a modern dark-mode compatible web interface, QR code connection, and drag-and-drop uploads.

## 🚀 Features

- **Cross-Platform:** Works on Windows, macOS, and Linux.
- **Easy Connection:** Scans a QR code to connect mobile devices instantly.
- **Two-Way Transfer:** - Upload files from Phone → PC.
  - Download files from PC → Phone.
- **Modern UI:** Responsive HTML5 interface with automatic Dark Mode.
- **File Management:** View, download, and delete files directly from the browser.
- **offline support:** it transfer the accross the LAN network, it don't need internet connection.


## 📂 Directory Structure

```text
Pyshare/
├── main.py             # Main Python script
├── index.html            # The web interface
├── requirements.txt      # Dependencies
├── qrcode.png            # (Generated automatically)
└── SharedFiles/
    ├── From_Phone/       # Files uploaded appear here
    └── From_PC/          # Put files here to share them

```

## 🛠️ Installation

1. **Install Python 3.x** if you haven't already.
2. Clone this repository or download the files.
3. Install the dependencies:

```bash
pip install -r requirements.txt

```

## 🖥️ Usage

1. **Start PyShare:**
Open your terminal/command prompt in the `PyShare` folder and run:
```bash
python main.py

```


2. **Connect via Phone:**
* The terminal will display a URL (e.g., `http://192.168.1.10:8010`).
* A `qrcode.png` file is generated in the folder. Open it and scan it with your phone's camera.


3. **Transfer Files:**
* **Phone to PC:** Drag and drop files on the phone's browser. They will appear in `SharedFiles/From_Phone`.
* **PC to Phone:** Place files in `SharedFiles/From_PC`. Refresh the browser on your phone to see and download them.


4. **Stop Server:**
* Click the "Disconnect Server" button on the web interface, or press `Ctrl+C` in the terminal.



## ⚠️ Important Notes

* **Same Network:** Your PC and Phone must be connected to the **same WiFi network**.
* **Firewall:** If you cannot connect, ensure your PC's firewall allows Python to accept incoming connections on port `8010`.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.