import os
import re
from tqdm import tqdm
from langchain_community.document_loaders import TextLoader


input_path = r"C:\Users\Administrator\bs_challenge_financial_14b_dataset\pdf_txt_file"
output_path = "financial_dataset"
os.makedirs(output_path, exist_ok=True)

files = os.listdir(input_path)
pattern = "股份有限公司"

saved_files = []

for file in files:
    file_full_path = os.path.join(input_path, file)
    if not os.path.isfile(file_full_path):
        continue

    try:
        with open(file_full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"读取失败 {file}: {e}")
        continue

    company_name = None
    for line in lines[:5]:
        if pattern in line:
            name = line.strip()
            if ":" in name:
                name = name.split(":")[-1].strip()
            elif "：" in name:
                name = name.split("：")[-1].strip()
            if pattern in name and 2 <= len(name) <= 20:
                company_name = name
                break

    if not company_name:
        continue

    invalid_chars = '<>:"/\\|?*'
    clean_name = ''.join(c if c not in invalid_chars else '_' for c in company_name)
    clean_name = clean_name.strip(' .')

    output_file = os.path.join(output_path, f"{clean_name}.txt")

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.writelines(lines)
        saved_files.append(output_file)
        print(f" 保存: {clean_name}.txt")
    except Exception as e:
        print(f" 写入失败 {clean_name}: {e}")


