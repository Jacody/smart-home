# Smart Home Monitoring System

This project monitors and visualizes gas and electricity consumption data and generates reports. And sends them by Telegram Bot API. 
![Bildschirmfoto 2025-05-21 um 07 55 24](https://github.com/user-attachments/assets/dfb38c84-b644-418a-bfb3-2bb9eda7de8f)

## How it works

1. **ESP32 camera** takes images of the gas meter and sends them with sensor data to the server
2. **Electricity meter ESP** captures electricity consumption data and sends it to the server
3. **Server** (server.py) receives and stores all data
4. **Image evaluation** (image_evaluator.py) extracts meter readings from the images
5. **Visualization tools** create graphics and reports on energy consumption

## Data Flow

### Electricity Consumption Data Flow
```
electricity_data.csv (impulse data)
    ↓
electricity_data_evaluator.py (processing)
    ↓
electricity_hourly.csv (hourly data)
    ↓
electricity_visualizer.py (visualization)
```

### Gas Meter Data Flow
```
Camera images (gas meter)
    ↓
image_evaluator.py / image_evaluation.py (OCR)
    ↓
gas_data.csv (detected meter readings)
    ↓
gas_data_evaluator.py (processing)
    ↓
gas_hourly.csv (processed data)
    ↓
gas_visualizer.py (visualization)
```

### Reporting Data Flow
```
combined_visualizer
    ↓
send_report.py (send report)
```

## Setup for public use

### 1. Configure environment variables

1. Copy the `.env.example` file and rename it to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file and add your personal configuration data:
   ```
   # Replace these values with your own data
   TELEGRAM_BOT_TOKEN="INSERT_YOUR_BOT_TOKEN_HERE"
   TELEGRAM_CHAT_ID="INSERT_YOUR_GROUP_CHAT_ID_HERE"
   ELECTRICITY_ESP_IP="192.168.178.XXX"
   ```

### 2. Set up ESP32 configuration files

#### Gas meter ESP32 (with camera)
1. Copy the example configuration file and create your own:
   ```bash
   cp gas-esp/src/environment.h.example gas-esp/src/environment.h
   ```
2. Edit `gas-esp/src/environment.h` and adjust the WiFi credentials and server URL:
   ```cpp
   #define WIFI_SSID "YOUR_WIFI_SSID"
   #define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
   #define SERVER_URL "http://YOUR_SERVER_IP:5000/api/camera"
   ```

#### Electricity meter ESP32
1. Copy the example configuration file and create your own:
   ```bash
   cp electricity-esp/src/config.h.example electricity-esp/src/config.h
   ```
2. Edit `electricity-esp/src/config.h` and adjust the WiFi credentials and server URL:
   ```cpp
   const char* ssid = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
   const char* serverUrl = "http://YOUR_SERVER_IP:5000/upload";
   ```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Tesseract OCR (for image evaluation)

#### Windows
1. Download from https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installation
3. Check the path in `image_evaluator.py`: `pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'`

#### macOS
```
brew install tesseract
```

#### Linux (Ubuntu/Debian)
```
sudo apt update
sudo apt install tesseract-ocr
```

## Important files

- `server.py`: Main server for receiving all data
- `image_evaluator.py`: Image evaluation with OCR for the gas meter
- `electricity-esp/stromzaehler_logger.py`: Logger for the electricity meter
- `combined_visualizer.py`: Combined visualization of gas and electricity consumption
- `send_report.py`: Sends reports via Telegram

## Usage

### Start the server

```bash
python server.py
```

### Start the visualization

```bash
python combined_visualizer.py
```

### Send a report

```bash
python send_report.py
```

## Environment variables

The following table shows all available configuration parameters in the `.env` file:

| Variable | Description | Default value |
|----------|--------------|--------------|
| TELEGRAM_BOT_TOKEN | Telegram bot token | - |
| TELEGRAM_CHAT_ID | Telegram chat ID for reports | - |
| TELEGRAM_DATEINAME | Filename for Telegram reports | Wochenbericht_Energie_KW_JAHR_WOCHE.png |
| ELECTRICITY_ESP_IP | IP address of the electricity ESP | 192.168.178.157 |
| ELECTRICITY_POLL_INTERVAL_SECONDS | Poll interval in seconds | 0.5 |
| ELECTRICITY_ROTATIONS_PER_KWH | Rotations per kWh | 75 |
| ELECTRICITY_COST_PER_KWH_EURO | Electricity cost per kWh in euros | 0.4017 |
| SERVER_PORT | Server port | 5000 |
| PORT_NUMBER | Port for visualizations | 5001 |
| ESP_WIFI_SSID | WiFi SSID for the ESP32 devices | - |
| ESP_WIFI_PASSWORD | WiFi password for the ESP32 devices | - |
| ESP_GAS_SERVER_URL | Server URL for the gas meter | - |
| ESP_ELECTRICITY_SERVER_URL | Server URL for the electricity meter | - |

## Security note

All sensitive data is stored in separate configuration files that are not included in the repository:

1. `.env` - Main configuration for the server and Python scripts
2. `gas-esp/src/environment.h` - Configuration for the gas meter ESP32
3. `electricity-esp/src/config.h` - Configuration for the electricity meter ESP32

These files are listed in `.gitignore` and will not be uploaded to the repository. Use the `.example` versions as templates.

## Publishing on GitHub

When publishing on GitHub, `.gitignore` ensures that no sensitive data is uploaded. The following files are ignored:

- `.env` - Contains API keys, tokens, and other sensitive information
- `gas-esp/src/environment.h` - Contains WiFi credentials and server URLs
- `electricity-esp/src/config.h` - Contains WiFi credentials and server URLs

Before your first push, make sure you have removed all sensitive data from the code and moved it to the appropriate configuration files.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request 
