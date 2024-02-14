import csv

def get_names(csv_file):
    csv_reader = csv.DictReader(csv_file)
    processed_names = []
    for row in csv_reader:
        if row["IGN"] != "":
            date_score_columns = list(row.items())[4:]
            entry = {"name": row["IGN"], "score": [], "date": []}
            for date, score in date_score_columns:
                if score.replace(",", "").isdigit():
                    print(score)
                    entry["score"].append(int(score.replace(",", "")))
                    entry["date"].append(date)
            processed_names.append(entry)
    return processed_names

# def get_scores(csv_file):
#     csv_reader = csv.DictReader(csv_file)
#     processed_scores = []
#     for row in csv_reader:
#         if row

# with open('sagaculverts.csv') as csv_file:
#     csv_reader = csv.DictReader(csv_file)
#     target_date = '2023-10-16'

#     for row in csv_reader:
#         if '2023-10-16' in row and row['IGN'] is not "":
#             print(f"{row['IGN']}'s score on {target_date}: {row[target_date]}")