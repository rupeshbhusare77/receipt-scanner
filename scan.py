# --- Imports ---
import os
import json
import argparse
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

# --- Configuration & Constants ---
# Load credentials from environment variables for security.
AZURE_ENDPOINT = os.environ.get("AZURE_ENDPOINT")
AZURE_KEY = os.environ.get("AZURE_KEY")
MAX_RETRIES = 3 # Max number of retries for a failed API call.

def analyze_document(image_path: str) -> tuple:
    """
    Analyzes a single document image using the Azure 'prebuilt-receipt' model.
    Implements a retry mechanism with exponential backoff for resilience.

    Args:
        image_path: The local path to the image file.

    Returns:
        A tuple containing the Azure result object and the original filename.
    """
    model_id = "prebuilt-receipt"
    if not os.path.exists(image_path):
        print(f"SKIPPING: Image not found at path: {image_path}")
        return None, os.path.basename(image_path)
    
    print(f"\n- Submitting '{os.path.basename(image_path)}' for analysis...")
    
    # Retry loop to handle transient network errors.
    for attempt in range(MAX_RETRIES):
        try:
            document_analysis_client = DocumentAnalysisClient(
                endpoint=AZURE_ENDPOINT, credential=AzureKeyCredential(AZURE_KEY)
            )
            with open(image_path, "rb") as f:
                poller = document_analysis_client.begin_analyze_document(model_id, document=f)
            result = poller.result()
            return result, os.path.basename(image_path)
        except Exception as e:
            print(f"  - Attempt {attempt + 1} failed for '{os.path.basename(image_path)}': {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt) # Exponential backoff: 1s, 2s
            else:
                print(f"  - All retries failed for '{os.path.basename(image_path)}'.")
                return None, os.path.basename(image_path)

def extract_and_validate_receipt(result) -> dict:
    """
    Parses the raw Azure result object into a clean, validated dictionary.
    Includes logic for item extraction, discount hunting, and total validation.

    Args:
        result: The result object from the Azure `analyze_document` call.

    Returns:
        A dictionary containing the structured and validated receipt data.
    """
    if not result or not result.documents:
        return {}

    doc = result.documents[0]
    final_result = {"items": []}
    
    def get_field(field_name):
        """Helper to safely get a field's value and confidence."""
        field = doc.fields.get(field_name)
        return (field.value, field.confidence) if field else (None, 0.0)

    # --- Field Extraction ---
    vendor_name, vendor_conf = get_field("VendorName")
    
    # Heuristic: If AI fails, guess the vendor name from the top lines of text.
    if not vendor_name and result.content:
        print("  -> AI did not find VendorName. Applying fallback heuristic...")
        JUNK_WORDS = ["RECEIPT", "INVOICE", "BILL", "TAX INVOICE", "CASH MEMO", "THANK YOU"]
        possible_lines = [line.strip() for line in result.content.split('\n') if line.strip()][:5]
        for line in possible_lines:
            if line.upper() not in JUNK_WORDS and len(line) > 2:
                vendor_name, vendor_conf = line, "Heuristic-Guess"
                break
    
    date_val, date_conf = get_field("TransactionDate")
    time_val, time_conf = get_field("TransactionTime")
    subtotal, subtotal_conf = get_field("Subtotal")
    tax, tax_conf = get_field("TotalTax")
    tip, tip_conf = get_field("Tip")
    total, total_conf = get_field("Total")
    
    # --- Item & Discount Extraction ---
    discount = 0.0
    items_field = doc.fields.get("Items")
    if items_field and items_field.value:
        for item in items_field.value:
            desc_f = item.value.get("Description")
            price_f = item.value.get("TotalPrice")
            qty_f = item.value.get("Quantity")
            
            desc = desc_f.value if desc_f else None
            price = price_f.value if price_f else 0.0
            qty = qty_f.value if qty_f else 1.0
            
            final_result["items"].append({"description": desc, "quantity": qty, "price": price})
            
            # Heuristic for finding discounts within the line items.
            if desc and any(k in desc.lower() for k in ["discount", "coupon", "saving"]) or price < 0:
                discount += abs(price)

    # --- Mathematical Validation ---
    subtotal_val = subtotal or 0.0
    tax_val = tax or 0.0
    tip_val = tip or 0.0
    total_val = total or 0.0
    
    calculated_total = subtotal_val - discount + tax_val + tip_val
    validation_passed = abs(calculated_total - total_val) < 0.01 # Tolerance for float comparison

    # --- Assemble Final Output ---
    final_result.update({
        "vendor_name": vendor_name,
        "date": str(date_val) if date_val else None,
        "time": str(time_val) if time_val else None,
        "subtotal": subtotal,
        "tax": tax,
        "tip": tip,
        "discount": discount,
        "total": total,
        "validation_info": {
            "calculated_total": round(calculated_total, 2),
            "validation_passed": validation_passed
        }
    })
    return final_result

def process_receipt_path_concurrently(path: str) -> list:
    """
    Manages the processing of a single file or a directory of files concurrently.

    Args:
        path: A path to an image file or a directory.

    Returns:
        A list of dictionaries, where each dictionary is the extracted data from one receipt.
    """
    all_results = []
    
    if os.path.isdir(path):
        image_paths = [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    elif os.path.isfile(path):
        image_paths = [path]
    else:
        print(f"ERROR: Path does not exist or is not a file/directory: {path}")
        return []
    
    if not image_paths:
        print(f"No images found in path: {path}")
        return []

    print(f"Found {len(image_paths)} image(s). Processing concurrently...")
    
    # Use a ThreadPoolExecutor to send multiple requests to Azure at the same time.
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_file = {executor.submit(analyze_document, img_path): img_path for img_path in image_paths}
        
        for future in as_completed(future_to_file):
            result, filename = future.result()
            if result:
                details = extract_and_validate_receipt(result)
                details['source_file'] = os.path.basename(filename)
                all_results.append(details)
    return all_results

def save_results(results_list: list, base_filename="extraction_log"):
    """
    Saves the extracted data to both a detailed JSON file and a summary CSV file.
    """
    if not results_list: return

    # Save detailed JSON output
    json_filename = f"{base_filename}.json"
    print(f"Saving detailed results to {json_filename}...")
    with open(json_filename, 'w') as f:
        json.dump(results_list, f, indent=2, default=str)
    
    # Save flattened summary to CSV
    csv_filename = f"{base_filename}.csv"
    print(f"Saving summary to {csv_filename}...")
    flat_results = []
    for res in results_list:
        flat_res = res.copy()
        flat_res.pop('items', None) # Remove nested items list for CSV
        validation_info = flat_res.pop('validation_info', {})
        flat_res.update(validation_info)
        flat_results.append(flat_res)
        
    df = pd.DataFrame(flat_results)
    df.to_csv(csv_filename, mode='a', header=not os.path.exists(csv_filename), index=False)
    print(f"\nAll files saved successfully.")


if __name__ == "__main__":
    # --- Command-Line Interface Setup ---
    cli_parser = argparse.ArgumentParser(
        description="An advanced, industrial-grade receipt scanner using Azure AI.",
        epilog="Example usage: python scan.py -i ./receipts/"
    )
    cli_parser.add_argument("-i", "--input", required=True, help="Path to a receipt image file or a directory.")
    args = cli_parser.parse_args()

    # --- Main Pipeline Execution ---
    if not AZURE_ENDPOINT or not AZURE_KEY:
        print("ERROR: Please set the AZURE_ENDPOINT and AZURE_KEY environment variables first.")
    else:
        results = process_receipt_path_concurrently(args.input)
        if results:
            print("\n--- EXTRACTION COMPLETE ---")
            save_results(results)