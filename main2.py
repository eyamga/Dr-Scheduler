import logging
import json

from datetime import date
from datetime import datetime

from models.task import TaskCategory, Task, TaskDaysParameter
from models.physician import Physician
from models.calendar import Calendar
from models.math_schedule import MathSchedule
from models.alternative_schedule import AlternativeSchedule

from config.managers import TaskManager, PhysicianManager


def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



def initialize_task_manager():
    task_manager = TaskManager()

    # Add categories
    ctu_category = TaskCategory(name="CTU", days_parameter=TaskDaysParameter.MULTI_WEEK, number_of_weeks=2,
                                weekday_revenue=2000, call_revenue=4000, restricted=False)
    er_category = TaskCategory(name="ER", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
                               weekday_revenue=2500, call_revenue=5000, restricted=True)

    consult_category = TaskCategory(name="CONSULT", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
                               weekday_revenue=2000, call_revenue=3000, restricted=True)

    preop_category = TaskCategory(name="PREOP", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
                               weekday_revenue=2000, call_revenue=0, restricted=True)

    ambu_category = TaskCategory(name="AMBU", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
                         weekday_revenue=1000, call_revenue=0, restricted=True)

    mog_category = TaskCategory(name="MOG", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
                         weekday_revenue=1500, call_revenue=0, restricted=True)

    vasc_category = TaskCategory(name="VASC", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
                         weekday_revenue=2000, call_revenue=2500, restricted=True)

    task_manager.add_category(ctu_category)
    task_manager.add_category(er_category)
    task_manager.add_category(consult_category)

    task_manager.add_category(preop_category)
    task_manager.add_category(ambu_category)

    task_manager.add_category(mog_category)
    task_manager.add_category(vasc_category)


    # Add tasks
    task_manager.add_task(Task.create(ctu_category, 'Main', 'CTU_A', heaviness=4, mandatory=True))
    task_manager.add_task(Task.create(ctu_category, 'Main', 'CTU_B', week_offset=1, heaviness=4, mandatory=True))
    task_manager.add_task(Task.create(ctu_category, 'Main', 'CTU_C', heaviness=4, mandatory=True))
    task_manager.add_task(Task.create(ctu_category, 'Main', 'CTU_D', week_offset=1, heaviness=4, mandatory=True))

    task_manager.add_task(Task.create(er_category, 'Main', 'ER_1', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(er_category, 'Main', 'ER_2', heaviness=5, mandatory=True))

    task_manager.add_task(Task.create(consult_category, 'Main', 'CONSULT_1', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(consult_category, 'Main', 'CONSULT_2', heaviness=5, mandatory=True))
    #
    task_manager.add_task(Task.create(preop_category, 'Main', 'PREOP_1', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(preop_category, 'Main', 'PREOP_2', heaviness=5, mandatory=False))
    #
    task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_1', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_2', heaviness=5, mandatory=True))

    task_manager.add_task(Task.create(mog_category, 'Main', 'MOG', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(vasc_category, 'Main', 'VASC', heaviness=5, mandatory=False)) # False

    task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_AB_CALL', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_CD_CALL', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(er_category, 'Call', 'ER_CALL', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(consult_category, 'Call', 'CONSULT_CALL', heaviness=5, mandatory=True))

    task_manager.add_task(Task.create(mog_category, 'Call', 'MOG_CALL', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(vasc_category, 'Call', 'VASC_CALL', heaviness=5, mandatory=False))

    # Link tasks
    task_manager.link_tasks('CTU_A', 'CTU_AB_CALL')
    task_manager.link_tasks('CTU_B', 'CTU_AB_CALL')
    task_manager.link_tasks('CTU_C', 'CTU_CD_CALL')
    task_manager.link_tasks('CTU_D', 'CTU_CD_CALL')

    task_manager.link_tasks('ER_1', 'ER_CALL')
    task_manager.link_tasks('ER_2', 'ER_CALL')

    task_manager.link_tasks('CONSULT_1', 'CONSULT_CALL')
    task_manager.link_tasks('CONSULT_2', 'CONSULT_CALL')

    task_manager.link_tasks('VASC', 'VASC_CALL')
    task_manager.link_tasks('MOG', 'MOG_CALL')


    return task_manager


def initialize_physician_manager(task_manager):
    physician_manager = PhysicianManager(task_manager)

    # Add physicians
    physicians = [
        Physician("Eric", "Yamga", ["CTU", "ER", "PREOP", "CONSULT"], True, 0.45, [], ["MOG", "VASC", "AMBU"]),
        Physician("Madeleine", "Durand", ["CONSULT", "CTU", "ER", "PREOP"], False, 0.3, [], ["MOG", "VASC", "AMBU"]),
        Physician("Emmanuelle", "Duceppe", ["CTU", "PREOP", "CONSULT"], False, 0.3, [], ["MOG", "VASC", "AMBU", "ER"]),
        Physician("Emmanuel", "Sirdar", ["CTU", "CONSULT", "ER", "PREOP"], False, 0.3, [], ["MOG", "VASC"]),
        Physician("Florence", "Weber", ["MOG", "ER", "CTU"],False, 0.6, ["MOG"], ["VASC"]),
        Physician("Sophie", "Granmaison", ["MOG", "CTU", "ER", "AMBU"], False, 0.75, ["MOG"], ["VASC"]),
        Physician("Michèle", "Mahone", ["MOG", "CTU", "ER", "AMBU", "PREOP"], False, 0.75, ["MOG"], ["VASC"]),
        Physician("Nazila", "Bettache", ["MOG", "ER", "CTU", "AMBU", "CONSULT", "PREOP"], False, 0.5, ["MOG"], ["VASC"]),
        Physician("Vincent", "Williams", ["MOG", "CTU", "ER", "PREOP", "CONSULT", "AMBU"], False, 0.80, [], ["VASC"]),

        Physician("Gabriel", "Dion", ["CTU", "PREOP", "CONSULT"], False, 0.70, [], ["MOG", "VASC"]),
        Physician("Justine", "Munger", ["CTU"], True, 0.75, [], ["MOG", "VASC"]),
        Physician("Mikhael", "Laskine", ["CTU", "CONSULT", "ER", "PREOP"], False, 0.8, [], ["MOG", "VASC"]),
        Physician("Maxime", "Lamarre-Cliche", ["CTU", "ER",  "CONSULT",  "PREOP", "AMBU"], False, 0.80, [], ["MOG", "VASC"]),
        Physician("Julien", "Dastous", ["CTU", "CONSULT", "PREOP", "ER", "AMBU"], False, 0.75, [], ["MOG", "VASC"]),
        Physician("Jean-Pascal", "Costa", ["CTU", "ER", "AMBU", "PREOP", "CONSULT"], False, 0.70, [], ["MOG", "VASC"]),
        Physician("Camille", "Laflamme", ["ER",  "CONSULT", "CTU", "PREOP", "AMBU"], False, 0.70, [], ["MOG", "VASC"]),

        Physician("Robert", "Wistaff", ["CTU",  "CONSULT", "PREOP", "ER", "AMBU"], False, 0.85, [], ["MOG", "VASC"]),
        Physician("Rene", "Lecours", ["AMBU", "CTU", "CONSULT", "ER"], False, 0.80, [],
                ["MOG", "VASC"]),
        Physician("Diem-Quyen", "Nguyen", ["CTU",  "CONSULT", "PREOP", "AMBU", "ER"], False, 0.70, [], ["MOG", "VASC"]),
        Physician("Michel", "Bertrand", ["CTU", "PREOP", "CONSULT"], False, 0.70, [], ["MOG", "VASC"]),

        Physician("J.Manuel", "Dominguez", ["CTU", "CONSULT", "PREOP", "ER"], False, 0.55, ["VASC"], ["MOG"]),
        Physician("Marie-Jose", "Miron", ["VASC"], False, 0.4, ["VASC"],
                ["MOG", "CTU", "ER", "PREOP", "AMBU"]),
        Physician("André", "Roussin", ["VASC"], False, 0.35, ["VASC"],
                ["MOG", "CTU", "CONSULT", "ER", "PREOP", "AMBU"]),

        Physician("Tal", "Kopel", ["MOG"], False, 0.1, [], ["VASC", "CTU", "CONSULT", "ER", "PREOP", "AMBU"]),
        Physician("Julien", "Viau", ["MOG"], False, 0.1, [], ["VASC", "CTU", "CONSULT", "ER", "PREOP", "AMBU"]),

        Physician("Vasc", "Vasc", [], False, 1.0, [], ["MOG", "CTU", "CONSULT", "ER", "PREOP", "AMBU"]),
        Physician("Benoit", "Deligne", ["CTU", "CONSULT", "ER", "PREOP", "AMBU"], False, 0.5, [], ["MOG", "VASC"]),
        Physician("Martial", "Koenig", ["CTU", "CONSULT", "PREOP", "AMBU", "ER"], False, 0.8, [], ["MOG", "VASC"]),

        Physician("Brigitte", "Benard", ["PREOP", "CONSULT", "CTU", "AMBU"], False, 0.2, [], ["MOG", "VASC"]),

        #Physician("Christopher Oliver", "Clapperton", ["CTU", "ER", "PREOP", "AMBU", "CONSULT"], False, 0, [], ["MOG", "VASC"]),
        #Physician("Audrey", "Lacasse", ["CTU", "ER"], False, 0.6, [], ["MOG", "VASC"]),
        ]



    for physician in physicians:
        physician_manager.add_physician(physician)

    # Set unavailability periods
    unavailability_periods = {
        "Michel Bertrand": [
        (date(2024, 12, 9), date(2024, 12, 13)),
        (date(2024, 12, 14), date(2024, 12, 15)),
        (date(2024, 12, 28), date(2024, 12, 30)),
        (date(2024, 12, 31)),
        (date(2025, 1, 1), date(2025, 1, 5)),
        (date(2025, 1, 6), date(2025, 1, 12)),
        (date(2025, 2, 3), date(2025, 2, 9)),
        (date(2025, 2, 24), date(2025, 3, 2)),
        (date(2025, 3, 24), date(2025, 3, 28)),
        (date(2025, 3, 29), date(2025, 4, 6)),
        (date(2025, 4, 28), date(2025, 5, 11)),
        (date(2025, 5, 12), date(2025, 5, 16)),
        (date(2025, 5, 26), date(2025, 5, 31)),
        (date(2025, 6, 23), date(2025, 7, 6)),
        date(2025, 6, 1),
    ],
    "Nazila Bettache": [
        (date(2024, 12, 9), date(2024, 12, 15)),
        (date(2024, 12, 16), date(2025, 1, 12)),
        (date(2025, 1, 20), date(2025, 1, 26)),
        (date(2025, 2, 1), date(2025, 2, 9)),
        (date(2025, 2, 24), date(2025, 2, 28)),
        (date(2025, 3, 1), date(2025, 3, 3)),
        (date(2025, 3, 15), date(2025, 4, 13)),
        (date(2025, 4, 15), date(2025, 4, 21)),
        (date(2025, 4, 14)),
        (date(2025, 5, 12), date(2025, 5, 16)),
        (date(2025, 5, 17), date(2025, 5, 19)),
        (date(2025, 6, 2), date(2025, 6, 8)),
        (date(2025, 6, 21), date(2025, 6, 24)),
        (date(2025, 6, 25), date(2025, 6, 29)),
    ],
    "Brigitte Benard": [
        (date(2024, 12, 23), date(2025, 2, 9)),
        (date(2025, 2, 18), date(2025, 3, 30)),
        (date(2025, 4, 5), date(2025, 5, 18)),
        (date(2025, 5, 24), date(2025, 5, 25)),
        (date(2025, 7, 5), date(2025, 7, 6)),
    ],
    "Jean-Pascal Costa": [
        (date(2025, 1, 25), date(2025, 1, 26)),
        (date(2025, 2, 8), date(2025, 2, 16)),
        (date(2025, 3, 15), date(2025, 3, 23)),
        (date(2025, 4, 18), date(2025, 4, 21)),
        (date(2025, 5, 9), date(2025, 5, 25)),
        (date(2025, 6, 14), date(2025, 6, 22)),
    ],
    "Julien Dastous": [
        (date(2025, 1, 30)),
        (date(2025, 2, 13)),
        (date(2025, 2, 27)),
        (date(2025, 3, 13)),
        (date(2025, 4, 12), date(2025, 4, 27)),
        (date(2025, 4, 3)),
        (date(2025, 5, 24), date(2025, 6, 1)),
        (date(2025, 5, 8)),
        (date(2025, 6, 19)),
    ],
    "Benoit Deligne": [
        (date(2024, 12, 25), date(2025, 1, 7)),
        (date(2024, 12, 12)),
        (date(2025, 1, 11), date(2025, 1, 12)),
        (date(2025, 1, 30)),
        (date(2025, 2, 27)),
        (date(2025, 3, 15), date(2025, 3, 16)),
        (date(2025, 3, 17), date(2025, 3, 23)),
        (date(2025, 4, 2), date(2025, 4, 6)),
        (date(2025, 4, 24)),
        (date(2025, 5, 29)),
        (date(2025, 6, 25), date(2025, 6, 27)),
    ],
    "Gabriel Dion": [
        (date(2024, 12, 23), date(2024, 12, 27)),
        (date(2025, 1, 29)),
        (date(2025, 2, 1), date(2025, 2, 23)),
        (date(2025, 5, 31), date(2025, 6, 8)),
    ],
    "J.Manuel Dominguez": [
        (date(2024, 12, 16), date(2024, 12, 20)),
        (date(2024, 12, 30), date(2025, 1, 5)),
        (date(2025, 1, 20), date(2025, 1, 24)),
        (date(2025, 2, 17), date(2025, 2, 21)),
        (date(2025, 3, 3), date(2025, 3, 16)),
        (date(2025, 4, 14), date(2025, 4, 20)),
        (date(2025, 5, 19), date(2025, 5, 23)),
        (date(2025, 6, 16), date(2025, 6, 20)),
    ],
    "Emmanuelle Duceppe": [
        (date(2024, 12, 23), date(2024, 12, 27)),
        (date(2024, 12, 28), date(2025, 1, 5)),
        (date(2025, 1, 20), date(2025, 1, 31)),
        (date(2025, 2, 1), date(2025, 2, 2)),
        (date(2025, 2, 3), date(2025, 2, 28)),
        (date(2025, 3, 1), date(2025, 3, 4)),
        (date(2025, 3, 5), date(2025, 3, 9)),
        (date(2025, 3, 24), date(2025, 4, 11)),
        (date(2025, 4, 12), date(2025, 4, 13)),
        (date(2025, 4, 22), date(2025, 5, 4)),
        (date(2025, 5, 12), date(2025, 5, 16)),
        (date(2025, 5, 17), date(2025, 5, 25)),
        (date(2025, 5, 26), date(2025, 5, 30)),
        (date(2025, 5, 31), date(2025, 6, 1)),
        (date(2025, 6, 2), date(2025, 6, 8)),
        (date(2025, 6, 16), date(2025, 6, 29)),
        (date(2025, 7, 7), date(2025, 7, 11)),
        (date(2025, 7, 12), date(2025, 7, 13)),
        (date(2025, 7, 14), date(2025, 7, 20)),
    ],
    "Madeleine Durand": [
        (date(2024, 12, 2), date(2024, 12, 8)),
        (date(2024, 12, 16), date(2024, 12, 20)),
        (date(2025, 1, 6), date(2025, 1, 10)),
        (date(2025, 1, 20), date(2025, 1, 24)),
        (date(2025, 1, 27), date(2025, 1, 31)),
        (date(2025, 2, 3), date(2025, 2, 7)),
        (date(2025, 2, 24), date(2025, 2, 28)),
        (date(2025, 2, 12)),
        (date(2025, 3, 1), date(2025, 3, 9)),
        (date(2025, 3, 10), date(2025, 3, 16)),
        (date(2025, 3, 24), date(2025, 3, 28)),
        (date(2025, 4, 7), date(2025, 4, 11)),
        (date(2025, 4, 14), date(2025, 4, 17)),
        (date(2025, 4, 22), date(2025, 4, 25)),
        (date(2025, 4, 28), date(2025, 4, 29)),
        (date(2025, 4, 30)),
        (date(2025, 5, 1), date(2025, 5, 4)),
        (date(2025, 5, 5), date(2025, 5, 11)),
        (date(2025, 5, 26), date(2025, 5, 30)),
        (date(2025, 5, 14)),
        (date(2025, 6, 9), date(2025, 6, 13)),
        (date(2025, 6, 16), date(2025, 6, 20)),
        (date(2025, 7, 5), date(2025, 7, 13)),
    ],
    "Martial Koenig": [
        (date(2025, 3, 15), date(2025, 3, 23)),
        (date(2025, 4, 21), date(2025, 4, 27)),
        (date(2025, 5, 19), date(2025, 6, 15)),
        (date(2025, 7, 21), date(2025, 7, 27)),
    ],
    "Camille Laflamme": [
        (date(2024, 12, 21), date(2024, 12, 27)),
        (date(2025, 1, 29)),
        (date(2025, 5, 2), date(2025, 7, 6)),
    ],
    "Maxime Lamarre-Cliche": [
        (date(2025, 1, 16), date(2025, 1, 17)),
        (date(2025, 3, 1), date(2025, 3, 9)),
        (date(2025, 4, 12), date(2025, 4, 21)),
        (date(2025, 5, 22), date(2025, 5, 23)),
        (date(2025, 6, 21), date(2025, 6, 30)),
        (date(2025, 7, 1), date(2025, 7, 13)),
    ],
    "Mikhael Laskine": [
        (date(2024, 12, 30), date(2025, 1, 5)),
        (date(2025, 1, 29)),
        (date(2025, 4, 12), date(2025, 4, 13)),
        (date(2025, 4, 2)),
        (date(2025, 5, 3), date(2025, 5, 4)),
    ],
    "Michèle Mahone": [
        (date(2024, 12, 28), date(2025, 1, 5)),
        (date(2025, 1, 18), date(2025, 1, 19)),
        (date(2025, 2, 6)),
        (date(2025, 3, 1), date(2025, 3, 9)),
        (date(2025, 3, 23), date(2025, 3, 28)),
        (date(2025, 3, 22)),
        (date(2025, 4, 13), date(2025, 4, 23)),
        (date(2025, 4, 24), date(2025, 4, 27)),
        (date(2025, 4, 28), date(2025, 5, 4)),
        (date(2025, 4, 12)),
        (date(2025, 5, 17), date(2025, 5, 19)),
        (date(2025, 6, 9), date(2025, 6, 11)),
        (date(2025, 7, 4), date(2025, 7, 6)),
    ],
    "Marie-Jose Miron": [
        (date(2024, 12, 9), date(2024, 12, 15)),
        (date(2024, 12, 23), date(2025, 1, 12)),
        (date(2025, 1, 13), date(2025, 1, 19)),
        (date(2025, 3, 1), date(2025, 3, 9)),
    ],
    "Justine Munger": [
        (date(2025, 1, 18), date(2025, 1, 19)),
        (date(2025, 1, 29)),
        (date(2025, 2, 15), date(2025, 2, 23)),
        (date(2025, 4, 18), date(2025, 5, 4)),
    ],
    "Diem-Quyen Nguyen": [
        (date(2024, 12, 21), date(2024, 12, 29)),
        (date(2025, 1, 28), date(2025, 1, 29)),
        (date(2025, 1, 25)),
        (date(2025, 1, 26)),
        (date(2025, 2, 1), date(2025, 2, 2)),
        (date(2025, 2, 7), date(2025, 3, 2)),
        (date(2025, 3, 16), date(2025, 3, 22)),
        (date(2025, 3, 31), date(2025, 4, 6)),
        (date(2025, 5, 2), date(2025, 5, 18)),
        (date(2025, 6, 7), date(2025, 6, 15)),
        (date(2025, 6, 28), date(2025, 7, 6)),
        (date(2025, 6, 21)),
        (date(2025, 6, 22)),
    ],
    "André Roussin": [
        (date(2024, 12, 7), date(2024, 12, 15)),
        (date(2024, 12, 23), date(2025, 1, 5)),
        (date(2025, 1, 6), date(2025, 1, 12)),
        (date(2025, 2, 1), date(2025, 2, 9)),
        (date(2025, 2, 24), date(2025, 3, 9)),
        #(date(2025, 4, 5), date(2025, 4, 13)),
        (date(2025, 5, 3), date(2025, 6, 1)),
        (date(2025, 6, 28), date(2025, 7, 6)),
    ],
    "Florence Weber": [
        (date(2025, 1, 18), date(2025, 1, 19)),
        (date(2025, 3, 1), date(2025, 3, 9)),
        (date(2025, 4, 12), date(2025, 5, 4)),
        (date(2025, 5, 30), date(2025, 6, 1)),
        (date(2025, 6, 24)),
        (date(2025, 7, 4), date(2025, 7, 6)),
    ],
    "Vincent Williams": [
        (date(2025, 1, 29)),
        (date(2025, 2, 1), date(2025, 2, 21)),
        (date(2025, 4, 18), date(2025, 4, 21)),
        (date(2025, 5, 17), date(2025, 5, 19)),
        (date(2025, 5, 31), date(2025, 6, 1)),
        (date(2025, 6, 24)),
        (date(2025, 7, 4), date(2025, 7, 6)),
    ],
    "Robert Wistaff": [
        (date(2025, 2, 8)),
        (date(2025, 2, 9)),
    ],
    "Eric Yamga": [
        (date(2025, 1, 25), date(2025, 2, 5)),
        (date(2025, 2, 8), date(2025, 2, 24)),
        (date(2025, 3, 24), date(2025, 3, 31)),
        (date(2025, 6, 16), date(2025, 6, 29)),
    ],
    "Sophie Granmaison":[
		    (date(2025, 2, 22), date(2025, 2, 23)),
		    (date(2025, 3, 22), date(2025, 3, 23)),
		    (date(2025, 4, 5), date(2025, 4, 13)),
		    (date(2025, 4, 25), date(2025, 4, 26)),
		    (date(2025, 4, 30), date(2025, 5, 4)),
		    (date(2025, 5, 10), date(2025, 5, 11)),
		    (date(2025, 5, 24), date(2025, 5, 25)),
		],
        "Julien Viau": [
            (date(2025, 1, 6), date(2025, 1, 19)),
            (date(2025, 1, 25), date(2025, 3, 16)),
            (date(2025, 3, 22), date(2025, 6, 15)),
            (date(2025, 6, 21), date(2025, 7, 6))
        ],
        "Tal Kopel": [
            (date(2025, 1, 6), date(2025, 1, 26)),
            (date(2025, 2, 1), date(2025, 4, 21)),
            (date(2025, 4, 26), date(2025, 6, 1)),
            (date(2025, 6, 7), date(2025, 7, 6))
        ]
    }
        
    physician_manager.set_unavailability_periods(unavailability_periods)

    return physician_manager


def initialize_calendar():
    start_date = date(2025, 1, 13)
    end_date = date(2025, 7, 6)
    region = 'Canada/QC'
    calendar = Calendar.create_calendar(start_date, end_date, region)
    #calendar.add_holiday(date(2025, 1, 1))
    #calendar.add_holiday(date(2025, 1, 2))
    calendar.add_holiday(date(2025, 3, 3))
    calendar.add_holiday(date(2025, 4, 18))
    calendar.add_holiday(date(2025, 4, 21))
    calendar.add_holiday(date(2025, 6, 24))
    calendar.add_holiday(date(2025, 7, 4))
    calendar.remove_holiday(date(2025, 7, 1))

    return calendar


def generate_schedules(physician_manager, task_manager, calendar):
    start_date = date(2025, 1, 13)
    end_date = date(2025, 7, 6)
    task_splits = {
        "CTU": {"linked": "5:2", "unlinked": "5:2"},
        "ER": {"linked": "5:2", "unlinked": "5:2"},
        "CONSULT": {"linked": "4:3", "unlinked": None},
        "PREOP": {"linked": None, "unlinked": "3:2"},
        "AMBU": {"linked": None, "unlinked": "3:2"},
        "MOG": {"linked": "4:3", "unlinked": None},
        "VASC": {"linked": "5:2", "unlinked": "5:2"}
    }

    off_days = {
        "CTU": [date(2023, 1, 3), date(2023, 12, 25)],
        "ER": [date(2023, 7, 4)]
    }

    scheduler = AlternativeSchedule(physician_manager, task_manager, calendar)

    scheduler.set_scheduling_period(start_date, end_date)
    #scheduler.set_task_splits(task_splits)
    #scheduler.set_off_days(off_days)

    scheduler.load_initial_schedule("output/config/initial_schedule.json")

    scheduler.generate_schedule(use_initial_schedule=True)


    scheduler.print_schedule()
    scheduler.generate_ics_calendar(f"output/schedule/optimized_generated_calendar.ics")
    scheduler.save_schedule(f"output/schedule/optimized_generated_schedule.json")


def export_periods():
    calendar = initialize_calendar()

    def convert_to_iso(item):
        if isinstance(item, datetime):
            return item.isoformat()
        elif isinstance(item, dict) and 'date' in item:
            # Assuming dictionaries contain date information as 'date' key
            return item['date']
        else:
            # Log the item that couldn't be converted
            print(f"Couldn't convert {item} to ISO format")
            return str(item)

    def flatten_nested_structure(data):
        flattened = {}
        for key, value in data.items():
            if isinstance(value, dict):
                # Handle nested dictionaries
                for subkey, subvalue in value.items():
                    if isinstance(subvalue, list):
                        flattened[f"{key}_{subkey}"] = [item for sublist in subvalue for item in
                                                        (isinstance(item, dict) and item.values()) or [item]]
                    else:
                        flattened[f"{key}_{subkey}"] = convert_to_iso(subvalue)
            elif isinstance(value, list):
                # Handle lists directly
                flattened[key] = [convert_to_iso(item) for item in value]
        return flattened

    # Assuming calendar.determine_periods() returns the data structure you provided
    data = calendar.determine_periods()

    # Flatten the nested structure
    flattened_data = flatten_nested_structure(data)

    # Convert the flattened dictionary to JSON string
    json_string = json.dumps(flattened_data, indent=2)

    print(json_string)

def main():
    setup_logging()

    task_manager = initialize_task_manager()
    physician_manager = initialize_physician_manager(task_manager)
    calendar = initialize_calendar()

    generate_schedules(physician_manager, task_manager, calendar)

if __name__ == "__main__":
    main()



