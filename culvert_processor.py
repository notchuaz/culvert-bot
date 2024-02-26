import cv2
import csv
import pytesseract
import re
import requests
import unicodedata
import datetime
import numpy as np
from culvert_name_matcher import class_similarity
from datetime import datetime

def get_culvert_scores(image_url):
    def remove_accents(input_str):
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    
    def check_zeros(input_str):
        elements = input_str.split()
        if not elements[-1].isdigit() and len(elements[-1]) <= 3:
            elements[-1] = '0'
        return ' '.join(elements)
    
    def get_maplestory_classes(csv_path):
        classes = [] 
        with open(csv_path, mode='r', encoding='utf-8-sig') as file:
            csv_reader = csv.reader(file)
            for row in csv_reader:
                classes.append(row)
        return classes
    
    def check_class_similarity(maple_class, classes_list):
        top_class = ''
        best_similarity = 0
        for item in classes_list:
            if class_similarity(maple_class, item) > best_similarity:
                best_similarity = class_similarity(maple_class, item)
                top_class = item
        return top_class
    
    def replace_func(match):
        char = match.group(0)
        return known_ocr_mistakes.get(char, char)
    
    known_ocr_mistakes = {
        "§": "5",
        "Q": "0",
        "O": "0"
    }

    classes = [item[0] for item in get_maplestory_classes('maplestory_classes.csv')]

    # image_path = 'pg6.png'
    # image = cv2.imread(image_path)

    response = requests.get(image_url)
    if response.status_code == 200:
        image_as_np_array = np.frombuffer(response.content, dtype=np.uint8)
        image = cv2.imdecode(image_as_np_array, cv2.IMREAD_COLOR)

    (h, w) = image.shape[:2]
    resized_image = cv2.resize(image, (1700, 1500))
    gray_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2GRAY)
    _, binary_inv_thresh = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((2,2), np.uint8)
    blurred_image = cv2.GaussianBlur(binary_inv_thresh, (9, 9), 2)
    dilated_image = cv2.dilate(blurred_image, kernel, iterations=1)
    final_image = cv2.bitwise_not(dilated_image)
    # cv2.imwrite('preprocessed.png', final_image)

    tesseract_custom_config = r'--oem 3 --psm 6'
    lines = pytesseract.image_to_string(final_image, config=tesseract_custom_config).split('\n')
    filtered_lines = [line for line in lines if line.strip()]
    names_list = [f"{remove_accents(item.split()[0])}" for item in filtered_lines if len(item) > 1]
    entry_data = [' '.join(item.split()[1:]) for item in filtered_lines if len(item) > 1]

    class_level_list= []
    score_list = []
    for item in entry_data:
        item = check_zeros(re.sub(r"[§QO]", replace_func, item))
        match = re.search(r'^(.+?)(\d{3})\s+(.*?)\s+((\d{1,3}(?:[,\s]\d{3})*)(?:\.\d+)?|([A-Za-z\d]{2}))$', item)
        if match:
            class_processed = check_class_similarity(match.group(1), classes)
            class_level_list.append([class_processed, int(match.group(2))])
            score_list.append(int(re.sub(r'[,. ]', '', match.group(4))))
    
    now_utc = datetime.utcnow()
    year = now_utc.year
    month = now_utc.month
    day = now_utc.day
    
    processed_list = [
        [name] + class_level + [score] + [f"{year:04d}-{month:02d}-{day:02d}"]
        for name, class_level, score in zip(names_list, class_level_list, score_list)
    ]

    for index, item in enumerate(filtered_lines):
        print(f"{index}: {item}")
    for index, item in enumerate(processed_list):
        print(f"{index}: {item}")

    if len(filtered_lines) != len(processed_list):
        return False

    return processed_list