import re
from datetime import date
from collections import defaultdict

def parse_unavailabilities(input_text):
    import re
    from datetime import date
    from collections import defaultdict

    data_lines = input_text.strip().split('\n')
    idx = 0
    unavailabilities = defaultdict(list)

    # Mapping French month abbreviations and full names to month numbers
    months_fr = {
        'janv': 1, 'févr': 2, 'mars': 3, 'avr': 4, 'mai': 5, 'juin': 6,
        'juil': 7, 'août': 8, 'sept': 9, 'oct':10, 'nov':11, 'déc':12,
        'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5,
        'juin': 6, 'juillet': 7, 'août': 8, 'septembre': 9, 'octobre':10,
        'novembre':11, 'décembre':12
    }

    while idx < len(data_lines):
        line = data_lines[idx].strip()
        if not line:
            idx += 1
            continue

        name = line
        idx += 1

        # Skip if not followed by 'Historique'
        if idx >= len(data_lines) or data_lines[idx].strip() != 'Historique':
            continue
        idx += 1

        # Check for 'Ajout' or 'Retrait'
        if idx >= len(data_lines):
            break
        action = data_lines[idx].strip()
        idx += 1

        # Skip 'Retrait' entries
        if action == 'Retrait':
            while idx < len(data_lines) and data_lines[idx].strip() != 'Complétée':
                idx += 1
            idx +=1  # Skip 'Complétée'
            continue

        if idx >= len(data_lines):
            break
        date_line = data_lines[idx].strip()
        idx += 1

        # Skip to 'Complétée'
        while idx < len(data_lines) and data_lines[idx].strip() != 'Complétée':
            idx += 1
        idx += 1  # Skip 'Complétée'

        # Regular expressions to match date formats
        patterns = [
            r"du (\d{1,2}) - (\d{1,2}) (\w+)\.? (\d{4})",                   # du 2 - 8 déc. 2024
            r"du (\d{1,2}) (\w+)\.? - (\d{1,2}) (\w+)\.? (\d{4})",          # du 25 janv. - 5 févr. 2025
            r"du (\d{1,2}) (\w+)\.? (\d{4}) - (\d{1,2}) (\w+)\.? (\d{4})",  # du 9 déc. 2024 - 11 janv. 2025
            r"(\d{1,2}) (\w+)\.? (\d{4})",                                  # 19 décembre 2024
            r"du (\d{1,2}) (\w+)\.? - (\d{1,2}) (\w+)\.? (\d{4})",          # du 7 févr. - 2 mars 2025
        ]

        parsed = False
        for pattern in patterns:
            match = re.match(pattern, date_line)
            if match:
                groups = match.groups()
                if pattern == patterns[0]:
                    day_start, day_end, month_str, year = groups
                    month = months_fr.get(month_str.strip('.'), 0)
                    start_date = date(int(year), month, int(day_start))
                    end_date = date(int(year), month, int(day_end))
                elif pattern == patterns[1]:
                    day_start, month_start_str, day_end, month_end_str, year = groups
                    month_start = months_fr.get(month_start_str.strip('.'), 0)
                    month_end = months_fr.get(month_end_str.strip('.'), 0)
                    year = int(year)
                    start_date = date(year, month_start, int(day_start))
                    end_date = date(year, month_end, int(day_end))
                elif pattern == patterns[2]:
                    day_start, month_start_str, year_start, day_end, month_end_str, year_end = groups
                    month_start = months_fr.get(month_start_str.strip('.'), 0)
                    month_end = months_fr.get(month_end_str.strip('.'), 0)
                    start_date = date(int(year_start), month_start, int(day_start))
                    end_date = date(int(year_end), month_end, int(day_end))
                elif pattern == patterns[3]:
                    day, month_str, year = groups
                    month = months_fr.get(month_str.strip('.'), 0)
                    start_date = end_date = date(int(year), month, int(day))
                elif pattern == patterns[4]:
                    day_start, month_start_str, day_end, month_end_str, year = groups
                    month_start = months_fr.get(month_start_str.strip('.'), 0)
                    month_end = months_fr.get(month_end_str.strip('.'), 0)
                    start_date = date(int(year), month_start, int(day_start))
                    end_date = date(int(year), month_end, int(day_end))
                else:
                    continue
                unavailabilities[name].append((start_date, end_date))
                parsed = True
                break

        if not parsed:
            print(f"Could not parse date line: {date_line}")

    return unavailabilities

if __name__ == "__main__":
    input_text = """
    décembre 2024
Madeleine Durand
Historique
Ajout
du 2 - 8 déc. 2024
Recherche
Toute la journée
Complétée
Éric Yamga
Historique
Ajout
du 3 - 14 déc. 2024
Recherche
Toute la journée
Complétée
André Roussin
Historique
Ajout
du 7 - 15 déc. 2024
Congrès
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 9 - 13 déc. 2024
Personnel
Toute la journée
Complétée
Nazila Bettache
Historique
Ajout
du 9 - 15 déc. 2024
Personnel
Toute la journée
Complétée
Marie-José Miron
Historique
Ajout
du 9 - 15 déc. 2024
Personnel
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 14 - 15 déc. 2024
Personnel
Toute la journée
Complétée
Nazila Bettache
Historique
Ajout
du 16 déc. 2024 - 12 janv. 2025
Personnel
Toute la journée
Complétée
J. Manuel Dominguez
Historique
Ajout
du 16 - 20 déc. 2024
Personnel
AM - PM
Complétée
Madeleine Durand
Historique
Ajout
du 16 - 20 déc. 2024
Recherche
Toute la journée
Complétée
Camille Laflamme
Historique
Ajout
du 21 - 27 déc. 2024
Vacances
Toute la journée
Complétée
Diem-Quyen Nguyen
Historique
Ajout
du 21 - 29 déc. 2024
Vacances
Toute la journée
Complétée
Vincent Williams
Historique
Ajout
du 21 - 27 déc. 2024
Vacances
Toute la journée
Complétée
Brigitte BÉNARD
Historique
Ajout
du 23 - 29 déc. 2024
Personnel
Toute la journée
Complétée
Gabriel Dion
Historique
Ajout
du 23 - 27 déc. 2024
Vacances
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 23 - 27 déc. 2024
Vacances
Toute la journée
Complétée
Marie-José Miron
Historique
Ajout
du 23 déc. 2024 - 11 janv. 2025
Vacances
Toute la journée
Complétée
André Roussin
Historique
Ajout
du 23 déc. 2024 - 5 janv. 2025
Vacances
Toute la journée
Complétée
Benoit Deligne
Historique
Ajout
du 25 déc. 2024 - 7 janv. 2025
Vacances
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 28 - 30 déc. 2024
Vacances
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 28 déc. 2024 - 5 janv. 2025
Vacances
Toute la journée
Complétée
Michèle Mahone
Historique
Ajout
du 28 déc. 2024 - 5 janv. 2025
Vacances
Toute la journée
Complétée
J. Manuel Dominguez
Historique
Ajout
du 30 déc. 2024 - 5 janv. 2025
Vacances
Toute la journée
Complétée
Mikhael Laskine
Historique
Ajout
du 30 déc. 2024 - 5 janv. 2025
Vacances
Toute la journée
Complétée
lundi 9 décembre 2024
Marie-José Miron
Historique
Retrait
9 décembre 2024
Personnel
Toute la journée
Complétée
Vincent Williams
Historique
Ajout
9 décembre 2024
Enseignement
AM
Complétée
jeudi 12 décembre 2024
Benoit Deligne
Historique
Ajout
12 décembre 2024
Administration
PM
Complétée
Vincent Williams
Historique
Ajout
12 décembre 2024
Enseignement
AM
Complétée
lundi 16 décembre 2024
Vincent Williams
Historique
Ajout
16 décembre 2024
Enseignement
AM
Complétée
jeudi 19 décembre 2024
Julien Dastous
Historique
Ajout
19 décembre 2024
Personnel
PM
Complétée
Vincent Williams
Historique
Ajout
19 décembre 2024
Enseignement
AM
Complétée
lundi 23 décembre 2024
Emmanuelle Duceppe
Historique
Retrait
23 décembre 2024
Vacances
Toute la journée
Complétée
Marie-José Miron
Historique
Retrait
23 décembre 2024
Vacances
Toute la journée
Complétée
mardi 24 décembre 2024
Emmanuelle Duceppe
Historique
Retrait
24 décembre 2024
Vacances
Toute la journée
Complétée
Marie-José Miron
Historique
Retrait
24 décembre 2024
Vacances
Toute la journée
Complétée
vendredi 27 décembre 2024
Emmanuelle Duceppe
Historique
Retrait
27 décembre 2024
Vacances
Toute la journée
Complétée
lundi 30 décembre 2024
Marie-José Miron
Historique
Retrait
30 décembre 2024
Vacances
Toute la journée
Complétée
mardi 31 décembre 2024
Michel Bertrand
Historique
Ajout
31 décembre 2024
Vacances
Toute la journée
Complétée
Marie-José Miron
Historique
Retrait
31 décembre 2024
Vacances
Toute la journée
Complétée
janvier 2025
Michel Bertrand
Historique
Ajout
du 1 - 5 janv. 2025
Vacances
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 6 - 12 janv. 2025
Vacances
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 6 - 10 janv. 2025
Recherche
Toute la journée
Complétée
André Roussin
Historique
Ajout
du 6 - 12 janv. 2025
Vacances
Toute la journée
Complétée
Benoit Deligne
Historique
Ajout
du 11 - 12 janv. 2025
Personnel
Toute la journée
Complétée
Marie-José Miron
Historique
Ajout
du 13 - 19 janv. 2025
Vacances
Toute la journée
Complétée
Maxime Lamarre-Cliche
Historique
Ajout
du 16 - 17 janv. 2025
Vacances
Toute la journée
Complétée
Nazila Bettache
Historique
Ajout
du 20 - 26 janv. 2025
Personnel
Toute la journée
Complétée
J. Manuel Dominguez
Historique
Ajout
du 20 - 24 janv. 2025
Personnel
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 20 - 31 janv. 2025
Recherche
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 20 - 24 janv. 2025
Recherche
Toute la journée
Complétée
Jean-Pascal Costa
Historique
Ajout
du 25 - 26 janv. 2025
Personnel
Toute la journée
Complétée
Éric Yamga
Historique
Ajout
du 25 janv. - 5 févr. 2025
Autre Garde
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 27 - 31 janv. 2025
Recherche
Toute la journée
Complétée
Diem-Quyen Nguyen
Historique
Ajout
du 28 - 29 janv. 2025
Vacances
Soir
Complétée
mercredi 1 janvier 2025
Benoit Deligne
Historique
Retrait
1 janvier 2025
Vacances
Toute la journée
Complétée
Marie-José Miron
Historique
Retrait
1 janvier 2025
Vacances
Toute la journée
Complétée
jeudi 2 janvier 2025
Benoit Deligne
Historique
Retrait
2 janvier 2025
Vacances
Toute la journée
Complétée
Marie-José Miron
Historique
Retrait
2 janvier 2025
Vacances
Toute la journée
Complétée
vendredi 3 janvier 2025
Marie-José Miron
Historique
Retrait
3 janvier 2025
Vacances
Toute la journée
Complétée
samedi 4 janvier 2025
Marie-José Miron
Historique
Retrait
4 janvier 2025
Vacances
Toute la journée
Complétée
dimanche 5 janvier 2025
Marie-José Miron
Historique
Retrait
5 janvier 2025
Vacances
Toute la journée
Complétée
lundi 6 janvier 2025
Marie-José Miron
Historique
Retrait
6 janvier 2025
Vacances
Toute la journée
Complétée
mardi 7 janvier 2025
Marie-José Miron
Historique
Retrait
7 janvier 2025
Vacances
Toute la journée
Complétée
mercredi 8 janvier 2025
Marie-José Miron
Historique
Retrait
8 janvier 2025
Vacances
Toute la journée
Complétée
jeudi 9 janvier 2025
Marie-José Miron
Historique
Retrait
9 janvier 2025
Vacances
Toute la journée
Complétée
vendredi 10 janvier 2025
Marie-José Miron
Historique
Retrait
10 janvier 2025
Vacances
Toute la journée
Complétée
dimanche 12 janvier 2025
Marie-José Miron
Historique
Ajout
12 janvier 2025
Vacances
Toute la journée
Complétée
samedi 25 janvier 2025
Diem-Quyen Nguyen
Historique
Ajout
25 janvier 2025
Personnel
Toute la journée
Complétée
dimanche 26 janvier 2025
Diem-Quyen Nguyen
Historique
Ajout
26 janvier 2025
Personnel
Toute la journée
Complétée
mardi 28 janvier 2025
Diem-Quyen Nguyen
Historique
Retrait
28 janvier 2025
Vacances
Soir
Complétée
mercredi 29 janvier 2025
Gabriel Dion
Historique
Ajout
29 janvier 2025
Personnel
AM
Complétée
Camille Laflamme
Historique
Ajout
29 janvier 2025
Enseignement
Toute la journée
Complétée
Mikhael Laskine
Historique
Ajout
29 janvier 2025
Enseignement
AM - Soir
Complétée
Justine Munger
Historique
Ajout
29 janvier 2025
Vacances
PM
Complétée
Vincent Williams
Historique
Ajout
29 janvier 2025
Enseignement
PM
Complétée
jeudi 30 janvier 2025
Julien Dastous
Historique
Ajout
30 janvier 2025
Autre Garde
PM
Complétée
Benoit Deligne
Historique
Ajout
30 janvier 2025
Administration
PM
Complétée
février 2025
Nazila Bettache
Historique
Ajout
du 1 - 9 févr. 2025
Personnel
Toute la journée
Complétée
Gabriel Dion
Historique
Ajout
du 1 - 23 févr. 2025
Vacances
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 1 - 2 févr. 2025
Personnel
Toute la journée
Complétée
Diem-Quyen Nguyen
Historique
Ajout
du 1 - 2 févr. 2025
Personnel
Toute la journée
Complétée
André Roussin
Historique
Ajout
du 1 - 9 févr. 2025
Vacances
Toute la journée
Complétée
Vincent Williams
Historique
Ajout
du 1 - 28 févr. 2025
Vacances
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 3 - 9 févr. 2025
Vacances
Toute la journée
Complétée
Marianne Dion
Historique
Ajout
du 3 - 7 févr. 2025
Vacances
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 3 - 28 févr. 2025
Recherche
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 3 - 7 févr. 2025
Recherche
Toute la journée
Complétée
Diem-Quyen Nguyen
Historique
Ajout
du 7 févr. - 2 mars 2025
Vacances
Toute la journée
Complétée
Jean-Pascal Costa
Historique
Ajout
du 8 - 16 févr. 2025
Vacances
Toute la journée
Complétée
Éric Yamga
Historique
Ajout
du 8 - 24 févr. 2025
Vacances
Toute la journée
Complétée
Justine Munger
Historique
Ajout
du 15 - 23 févr. 2025
Vacances
Toute la journée
Complétée
J. Manuel Dominguez
Historique
Ajout
du 17 - 21 févr. 2025
Personnel
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 24 févr. - 2 mars 2025
Vacances
Toute la journée
Complétée
Nazila Bettache
Historique
Ajout
du 24 - 28 févr. 2025
Personnel
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 24 - 28 févr. 2025
Recherche
Toute la journée
Complétée
André Roussin
Historique
Ajout
du 24 févr. - 9 mars 2025
Vacances
Toute la journée
Complétée
jeudi 6 février 2025
Michèle Mahone
Historique
Ajout
6 février 2025
Personnel
Toute la journée
Complétée
samedi 8 février 2025
Robert Wistaff
Historique
Ajout
8 février 2025
Vacances
Toute la journée
Complétée
dimanche 9 février 2025
Robert Wistaff
Historique
Ajout
9 février 2025
Vacances
Toute la journée
Complétée
lundi 10 février 2025
Marianne Dion
Historique
Ajout
10 février 2025
Vacances
Toute la journée
Complétée
mercredi 12 février 2025
Madeleine Durand
Historique
Ajout
12 février 2025
Congrès
Toute la journée
Complétée
jeudi 13 février 2025
Julien Dastous
Historique
Ajout
13 février 2025
Autre Garde
PM
Complétée
jeudi 27 février 2025
Julien Dastous
Historique
Ajout
27 février 2025
Autre Garde
PM
Complétée
Benoit Deligne
Historique
Ajout
27 février 2025
Administration
PM
Complétée
mars 2025
Nazila Bettache
Historique
Ajout
du 1 - 3 mars 2025
Personnel
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 1 - 4 mars 2025
Vacances
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 1 - 9 mars 2025
Vacances
Toute la journée
Complétée
Maxime Lamarre-Cliche
Historique
Ajout
du 1 - 9 mars 2025
Vacances
Toute la journée
Complétée
Michèle Mahone
Historique
Ajout
du 1 - 9 mars 2025
Vacances
Toute la journée
Complétée
Marie-José Miron
Historique
Ajout
du 1 - 9 mars 2025
Vacances
Toute la journée
Complétée
Florence Weber
Historique
Ajout
du 1 - 9 mars 2025
Vacances
Toute la journée
Complétée
J. Manuel Dominguez
Historique
Ajout
du 3 - 16 mars 2025
Vacances
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 5 - 9 mars 2025
Vacances
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 10 - 16 mars 2025
Recherche
Toute la journée
Complétée
Nazila Bettache
Historique
Ajout
du 15 mars - 13 avr. 2025
Vacances
Toute la journée
Complétée
Jean-Pascal Costa
Historique
Ajout
du 15 - 23 mars 2025
Autre Garde
Toute la journée
Complétée
Benoit Deligne
Historique
Ajout
du 15 - 16 mars 2025
Vacances
Toute la journée
Complétée
Martial Koenig
Historique
Ajout
du 15 - 23 mars 2025
Vacances
Toute la journée
Complétée
Diem-Quyen Nguyen
Historique
Ajout
du 16 - 22 mars 2025
Congrès
Toute la journée
Complétée
Benoit Deligne
Historique
Ajout
du 17 - 23 mars 2025
Vacances
Toute la journée
Complétée
Michèle Mahone
Historique
Ajout
du 23 - 28 mars 2025
Vacances
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 24 - 28 mars 2025
Vacances
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 24 mars - 11 avr. 2025
Recherche
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 24 - 28 mars 2025
Recherche
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 29 mars - 6 avr. 2025
Vacances
Toute la journée
Complétée
Diem-Quyen Nguyen
Historique
Ajout
du 31 mars - 6 avr. 2025
Congrès
Toute la journée
Complétée
jeudi 13 mars 2025
Julien Dastous
Historique
Ajout
13 mars 2025
Autre Garde
PM
Complétée
samedi 22 mars 2025
Michèle Mahone
Historique
Ajout
22 mars 2025
Vacances
Toute la journée
Complétée
lundi 31 mars 2025
Diem-Quyen Nguyen
Historique
Retrait
31 mars 2025
Congrès
Toute la journée
Complétée
avril 2025
Benoit Deligne
Historique
Ajout
du 2 - 6 avr. 2025
Congrès
Toute la journée
Complétée
André Roussin
Historique
Ajout
du 5 - 13 avr. 2025
Vacances
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 7 - 11 avr. 2025
Recherche
Toute la journée
Complétée
Julien Dastous
Historique
Ajout
du 12 - 27 avr. 2025
Vacances
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 12 - 13 avr. 2025
Personnel
Toute la journée
Complétée
Maxime Lamarre-Cliche
Historique
Ajout
du 12 - 21 avr. 2025
Vacances
Toute la journée
Complétée
Mikhael Laskine
Historique
Ajout
du 12 - 13 avr. 2025
Vacances
Toute la journée
Complétée
Florence Weber
Historique
Ajout
du 12 avr. - 4 mai 2025
Vacances
Toute la journée
Complétée
Michèle Mahone
Historique
Ajout
du 13 - 23 avr. 2025
Vacances
Toute la journée
Complétée
J. Manuel Dominguez
Historique
Ajout
du 14 - 20 avr. 2025
Personnel
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 14 - 17 avr. 2025
Recherche
Toute la journée
Complétée
Éric Yamga
Historique
Ajout
du 14 - 21 avr. 2025
Vacances
Toute la journée
Complétée
Nazila Bettache
Historique
Ajout
du 15 - 21 avr. 2025
Vacances
Toute la journée
Complétée
Jean-Pascal Costa
Historique
Ajout
du 18 - 21 avr. 2025
Personnel
Toute la journée
Complétée
Justine Munger
Historique
Ajout
du 18 avr. - 4 mai 2025
Vacances
Toute la journée
Complétée
Vincent Williams
Historique
Ajout
du 18 - 21 avr. 2025
Personnel
Toute la journée
Complétée
Martial Koenig
Historique
Ajout
du 21 - 27 avr. 2025
Congrès
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 22 avr. - 4 mai 2025
Recherche
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 22 - 25 avr. 2025
Recherche
Toute la journée
Complétée
Michèle Mahone
Historique
Ajout
du 24 - 27 avr. 2025
Congrès
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 28 avr. - 11 mai 2025
Vacances
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 28 - 29 avr. 2025
Congrès
Toute la journée
Complétée
Michèle Mahone
Historique
Ajout
du 28 avr. - 4 mai 2025
Vacances
Toute la journée
Complétée
mardi 1 avril 2025
Diem-Quyen Nguyen
Historique
Retrait
1 avril 2025
Congrès
Toute la journée
Complétée
mercredi 2 avril 2025
Mikhael Laskine
Historique
Ajout
2 avril 2025
Enseignement
AM - Soir
Complétée
Diem-Quyen Nguyen
Historique
Retrait
2 avril 2025
Congrès
Toute la journée
Complétée
jeudi 3 avril 2025
Julien Dastous
Historique
Ajout
3 avril 2025
Autre Garde
PM
Complétée
Diem-Quyen Nguyen
Historique
Retrait
3 avril 2025
Congrès
Toute la journée
Complétée
vendredi 4 avril 2025
Diem-Quyen Nguyen
Historique
Retrait
4 avril 2025
Congrès
Toute la journée
Complétée
samedi 5 avril 2025
Diem-Quyen Nguyen
Historique
Retrait
5 avril 2025
Congrès
Toute la journée
Complétée
dimanche 6 avril 2025
Diem-Quyen Nguyen
Historique
Retrait
6 avril 2025
Congrès
Toute la journée
Complétée
samedi 12 avril 2025
Michèle Mahone
Historique
Ajout
12 avril 2025
Vacances
Toute la journée
Complétée
lundi 14 avril 2025
Nazila Bettache
Historique
Ajout
14 avril 2025
Vacances
Toute la journée
Complétée
jeudi 24 avril 2025
Benoit Deligne
Historique
Ajout
24 avril 2025
Administration
PM
Complétée
mercredi 30 avril 2025
Madeleine Durand
Historique
Ajout
30 avril 2025
Congrès
Toute la journée
Complétée
mai 2025
Madeleine Durand
Historique
Ajout
du 1 - 4 mai 2025
Congrès
Toute la journée
Complétée
Diem-Quyen Nguyen
Historique
Ajout
du 2 - 18 mai 2025
Vacances
Toute la journée
Complétée
Mikhael Laskine
Historique
Ajout
du 3 - 4 mai 2025
Vacances
Toute la journée
Complétée
André Roussin
Historique
Ajout
du 3 mai - 1 juin 2025
Vacances
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 5 - 11 mai 2025
Recherche
Toute la journée
Complétée
Jean-Pascal Costa
Historique
Ajout
du 9 - 25 mai 2025
Vacances
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 12 - 16 mai 2025
Vacances
Toute la journée
Complétée
Nazila Bettache
Historique
Ajout
du 12 - 16 mai 2025
Personnel
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 12 - 16 mai 2025
Recherche
Toute la journée
Complétée
Nazila Bettache
Historique
Ajout
du 17 - 19 mai 2025
Personnel
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 17 - 25 mai 2025
Vacances
Toute la journée
Complétée
Michèle Mahone
Historique
Ajout
du 17 - 19 mai 2025
Personnel
Toute la journée
Complétée
Vincent Williams
Historique
Ajout
du 17 - 19 mai 2025
Personnel
Toute la journée
Complétée
J. Manuel Dominguez
Historique
Ajout
du 19 - 23 mai 2025
Personnel
Toute la journée
Complétée
Martial Koenig
Historique
Ajout
du 19 mai - 15 juin 2025
Vacances
Toute la journée
Complétée
Marianne Dion
Historique
Ajout
du 20 - 23 mai 2025
Vacances
Toute la journée
Complétée
Maxime Lamarre-Cliche
Historique
Ajout
du 22 - 23 mai 2025
Vacances
Toute la journée
Complétée
Brigitte BÉNARD
Historique
Ajout
du 24 - 25 mai 2025
Personnel
Toute la journée
Complétée
Julien Dastous
Historique
Ajout
du 24 mai - 1 juin 2025
Vacances
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 26 - 31 mai 2025
Vacances
Toute la journée
Complétée
Marianne Dion
Historique
Ajout
du 26 - 30 mai 2025
Vacances
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 26 - 30 mai 2025
Recherche
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 26 - 30 mai 2025
Recherche
Toute la journée
Complétée
Florence Weber
Historique
Ajout
du 30 mai - 1 juin 2025
Congrès
Toute la journée
Complétée
Gabriel Dion
Historique
Ajout
du 31 mai - 8 juin 2025
Vacances
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 31 mai - 1 juin 2025
Personnel
Toute la journée
Complétée
Vincent Williams
Historique
Ajout
du 31 mai - 1 juin 2025
Congrès
Toute la journée
Complétée
jeudi 8 mai 2025
Julien Dastous
Historique
Ajout
8 mai 2025
Autre Garde
PM
Complétée
mercredi 14 mai 2025
Madeleine Durand
Historique
Ajout
14 mai 2025
Congrès
PM - Soir
Complétée
vendredi 16 mai 2025
Marianne Dion
Historique
Ajout
16 mai 2025
Vacances
Toute la journée
Complétée
jeudi 29 mai 2025
Benoit Deligne
Historique
Ajout
29 mai 2025
Administration
PM
Complétée
juin 2025
Nazila Bettache
Historique
Ajout
du 2 - 8 juin 2025
Personnel
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 2 - 8 juin 2025
Recherche
Toute la journée
Complétée
Diem-Quyen Nguyen
Historique
Ajout
du 7 - 15 juin 2025
Vacances
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 9 - 13 juin 2025
Recherche
Toute la journée
Complétée
Michèle Mahone
Historique
Ajout
du 9 - 11 juin 2025
Congrès
Toute la journée
Complétée
Jean-Pascal Costa
Historique
Ajout
du 14 - 22 juin 2025
Autre Garde
Toute la journée
Complétée
J. Manuel Dominguez
Historique
Ajout
du 16 - 20 juin 2025
Personnel
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 16 - 29 juin 2025
Recherche
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 16 - 20 juin 2025
Recherche
Toute la journée
Complétée
Éric Yamga
Historique
Ajout
du 16 - 29 juin 2025
Recherche
Toute la journée
Complétée
Nazila Bettache
Historique
Ajout
du 21 - 24 juin 2025
Personnel
Toute la journée
Complétée
Maxime Lamarre-Cliche
Historique
Ajout
du 21 - 30 juin 2025
Vacances
Toute la journée
Complétée
Michel Bertrand
Historique
Ajout
du 23 juin - 6 juil. 2025
Vacances
Toute la journée
Complétée
Nazila Bettache
Historique
Ajout
du 25 - 29 juin 2025
Personnel
Toute la journée
Complétée
Benoit Deligne
Historique
Ajout
du 25 - 27 juin 2025
Congrès
Toute la journée
Complétée
Diem-Quyen Nguyen
Historique
Ajout
du 28 juin - 6 juil. 2025
Vacances
Toute la journée
Complétée
André Roussin
Historique
Ajout
du 28 juin - 6 juil. 2025
Vacances
Toute la journée
Complétée
dimanche 1 juin 2025
Michel Bertrand
Historique
Ajout
1 juin 2025
Vacances
Toute la journée
Complétée
lundi 2 juin 2025
Marianne Dion
Historique
Ajout
2 juin 2025
Vacances
Toute la journée
Complétée
jeudi 19 juin 2025
Julien Dastous
Historique
Ajout
19 juin 2025
Autre Garde
PM
Complétée
samedi 21 juin 2025
Diem-Quyen Nguyen
Historique
Ajout
21 juin 2025
Personnel
Toute la journée
Complétée
dimanche 22 juin 2025
Diem-Quyen Nguyen
Historique
Ajout
22 juin 2025
Personnel
Toute la journée
Complétée
mardi 24 juin 2025
Florence Weber
Historique
Ajout
24 juin 2025
Vacances
Toute la journée
Complétée
Vincent Williams
Historique
Ajout
24 juin 2025
Personnel
Toute la journée
Complétée
juillet 2025

Afficher à partir de novembre 2023
Calendrier
Liste
Maxime Lamarre-Cliche
Historique
Ajout
du 1 - 13 juil. 2025
Vacances
Toute la journée
Complétée
Michèle Mahone
Historique
Ajout
du 4 - 6 juil. 2025
Vacances
Toute la journée
Complétée
Florence Weber
Historique
Ajout
du 4 - 6 juil. 2025
Vacances
Toute la journée
Complétée
Vincent Williams
Historique
Ajout
du 4 - 6 juil. 2025
Personnel
Toute la journée
Complétée
Brigitte BÉNARD
Historique
Ajout
du 5 - 6 juil. 2025
Personnel
Toute la journée
Complétée
Madeleine Durand
Historique
Ajout
du 5 - 13 juil. 2025
Vacances
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 7 - 11 juil. 2025
Recherche
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 12 - 13 juil. 2025
Personnel
Toute la journée
Complétée
Emmanuelle Duceppe
Historique
Ajout
du 14 - 20 juil. 2025
Recherche
Toute la journée
Complétée
Martial Koenig
Historique
Ajout
du 21 - 27 juil. 2025
Congrès
Toute la journée

    """
    unavailabilities = parse_unavailabilities(input_text)

    # Function to extract last name for sorting
    def get_last_name(name):
        return name.split()[-1].lower()

    sorted_unavailabilities = dict(sorted(unavailabilities.items(), key=lambda x: get_last_name(x[0])))

    # Output the unavailabilities in the desired B format
    print("{")
    for name, periods in sorted_unavailabilities.items():
        print(f'    "{name}": [')
        for start_date, end_date in periods:
            if start_date == end_date:
                print(f'        date({start_date.year}, {start_date.month}, {start_date.day}),')
            else:
                print(f'        (date({start_date.year}, {start_date.month}, {start_date.day}), date({end_date.year}, {end_date.month}, {end_date.day})),')
        print("    ],")
    print("}")