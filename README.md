# 🧾 Azure-Powered Receipt Scanner

This is my AI-powered receipt built with **Azure AI Document Intelligence** (the service formerly known as Form Recognizer).

It’s not 100% perfect , but it does its best to give you clean, structured data from messy bills so you can skip the manual typing and focus on what matters.

---
### ✨ Why It’s Cool

* 🧠 **Smart Extraction** — Finds vendor, date, totals, tax, tip, discounts, and items.
* ⚡ **Bulk Processing** — Handles whole folders in parallel.
* ✅ **Checks the Math** — Verifies if totals, tax, and discounts actually add up.
* 🛡️ **Secure** — API keys stay safe via environment variables.
* 💾 **JSON + CSV Output** — Detailed + clean data in one go.
* 🤖 **Vendor Backup** — Heuristic guess if AI can’t find the name.

---
### 🚀 Quick Start

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/rupeshbhusare77/receipt-scanner.git
    cd receipt-scanner
    ```
2.  **Set Up the Environment**
    ```bash
    python -m venv venv
    venv\Scripts\activate   # Mac/Linux: source venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Set Up Your Azure Credentials**

    The script reads your Azure keys from environment variables so they never appear in your code.

    * **Get your keys:**
        1.  Log in to the **Azure Portal**.
        2.  Create a new resource by searching for and selecting **"Document Intelligence"** (the service formerly known as Form Recognizer). Choose the free tier when prompted.
        3.  Once your resource is created, navigate to it.
        4.  Find the **"Keys and Endpoint"** tab on the left menu.
        5.  Copy your **Key** and **Endpoint**.

    * **Set them in your terminal (Windows PowerShell):**
        ```powershell
        $env:AZURE_ENDPOINT = "Your_Endpoint_URL"
        $env:AZURE_KEY = "Your_Key"
        ```
    💡 These variables only last for your current terminal session. For a permanent setup, add them to your system environment variables.

    >**Student tip:** If you’re a student, you can get Azure for free with limited monthly usage through **Azure for Students** — no credit card required.

---
### 🖥 Usage
```bash
python scan.py --input path/to/receipt.jpg         # Single file
python scan.py --input path/to/folder/             # Whole folder
```
**Output files:**
* `extraction_log.json` — Full details
* `extraction_log.csv` — Clean summary

---
### 🛠 Stack
* Python 3
* Azure AI Document Intelligence
* Pandas

---
### 🤝 Contribute
Built with 💻 by Rupesh Bhusare, IIT Goa.

If you spot a bug, have a better idea, or want to make it faster — fork the repo and submit a PR.

Let’s make receipt scanning smarter together! 🚀

*Not perfect, but always trying its best.*

For Output and sample images refer *Output* folder.
