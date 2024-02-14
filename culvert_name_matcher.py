import Levenshtein
import re
import numpy as np
from Levenshtein import ratio

def class_similarity(str1, str2):
    distance = Levenshtein.distance(str1.lower(), str2.lower())
    longest_length = max(len(str1), len(str2))
    return round(1-distance/longest_length, 5)

def find_max_sim(sim_list, index_ignore):
    sim = -1
    sim_index = -1
    for index, value in enumerate(sim_list):
        if index in index_ignore:
            continue
        if value > sim:
            sim = value
            sim_index = index
    return sim, sim_index

def link_names(ocr_names, defined_names):
    similarity_matrix = [[0 for _ in range(len(ocr_names))] for _ in range(len(defined_names))]
    for row, defined in enumerate(defined_names):
        for column, ocr in enumerate(ocr_names):
            defined_class_normalized = defined["class"].lower()
            ocr_class_normalized = ocr[1].lower()
            similarity = 0
            if ocr_class_normalized == defined_class_normalized:
                defined_normalized = re.sub(r"\s", "", defined["name"]).lower()
                ocr_normalized = re.sub(r"\s+", "", ocr[0]).lower()
                similarity = ratio(ocr_normalized, defined_normalized)
            similarity_matrix[row][column] = similarity
    linked_columns = []
    linked_names = []
    for defined_index, row in enumerate(similarity_matrix):
        similarity_score, highest_similarity_index = find_max_sim(row, linked_columns)
        linked_columns.append(highest_similarity_index)
        linked_names.append([similarity_score, defined_names[defined_index]["name"], ocr_names[highest_similarity_index]])
    return linked_names