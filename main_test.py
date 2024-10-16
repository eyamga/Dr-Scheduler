import argparse
import logging
from datetime import date
from models.task import TaskCategory, Task, TaskDaysParameter
from models.physician import Physician
from models.calendar import Calendar
from models.schedule import Schedule
from models.math_schedule import MathSchedule
from config.managers import TaskManager, PhysicianManager
from typing import Optional, Dict
import itertools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define scenario labels as constants or use enums (optional)
TASK_SCENARIOS = {
    'default': 'All tasks, except restricted tasks',
    'restricted_tasks': 'All tasks, including restricted tasks',
    'mini_tasks': 'Small number of tasks, for faster debugging'
}

PHYSICIAN_SCENARIOS = {
    'default': 'Default physician configuration, all physicians, availability jan-june 2025',
    'all_modified_availability': 'Default configuration (reduced availability restricted jan-feb 2025',
    'reduced_staff': 'Reduced number of physicians for fast debugging : unvaialability jan-feb 2025'
}

CALENDAR_SCENARIOS = {
    'default': 'Default calendar configuration',
    'short_period': 'Short scheduling period - jan 1-feb2025'
}

SCHEDULE_SCENARIOS = {
    'default': 'Default schedule generation',
    #'unavailability_test': 'Testing off days for task',
    #'task_splitting_test': 'Testing task splitting',
}

def initialize_task_manager(scenario_label='default'):
    logger.info(f"Initializing Task Manager with scenario: {scenario_label}")
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

    if scenario_label == 'default':
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
        task_manager.add_task(Task.create(preop_category, 'Main', 'PREOP_2', heaviness=5, mandatory=True))
        #
        task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_1', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_2', heaviness=5, mandatory=True))

        ## task_manager.add_task(Task.create(mog_category, 'Main', 'MOG', heaviness=5, mandatory=False))
        ## task_manager.add_task(Task.create(vasc_category, 'Main', 'VASC', heaviness=5, mandatory=False))

        task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_AB_CALL', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_CD_CALL', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(er_category, 'Call', 'ER_CALL', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(consult_category, 'Call', 'CONSULT_CALL', heaviness=5, mandatory=True))

        ## task_manager.add_task(Task.create(mog_category, 'Call', 'MOG_CALL', heaviness=5, mandatory=False))
        ## task_manager.add_task(Task.create(vasc_category, 'Call', 'VASC_CALL', heaviness=5, mandatory=False))

        # Link tasks
        task_manager.link_tasks('CTU_A', 'CTU_AB_CALL')
        task_manager.link_tasks('CTU_B', 'CTU_AB_CALL')
        task_manager.link_tasks('CTU_C', 'CTU_CD_CALL')
        task_manager.link_tasks('CTU_D', 'CTU_CD_CALL')

        task_manager.link_tasks('ER_1', 'ER_CALL')
        task_manager.link_tasks('ER_2', 'ER_CALL')

        task_manager.link_tasks('CONSULT_1', 'CONSULT_CALL')
        task_manager.link_tasks('CONSULT_2', 'CONSULT_CALL')

        ## task_manager.link_tasks('VASC', 'VASC_CALL')
        ## task_manager.link_tasks('MOG', 'MOG_CALL')
    elif scenario_label == 'restricted_tasks':
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
        task_manager.add_task(Task.create(preop_category, 'Main', 'PREOP_2', heaviness=5, mandatory=True))
        #
        task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_1', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_2', heaviness=5, mandatory=True))

        task_manager.add_task(Task.create(mog_category, 'Main', 'MOG', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(vasc_category, 'Main', 'VASC', heaviness=5, mandatory=True))

        task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_AB_CALL', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_CD_CALL', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(er_category, 'Call', 'ER_CALL', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(consult_category, 'Call', 'CONSULT_CALL', heaviness=5, mandatory=True))

        task_manager.add_task(Task.create(mog_category, 'Call', 'MOG_CALL', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(vasc_category, 'Call', 'VASC_CALL', heaviness=5, mandatory=True))

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
    elif scenario_label == 'mini_tasks':
        # Add tasks
        task_manager.add_task(Task.create(ctu_category, 'Main', 'CTU_A', heaviness=4, mandatory=True))
        task_manager.add_task(Task.create(ctu_category, 'Main', 'CTU_B', week_offset=1, heaviness=4, mandatory=True))
        task_manager.add_task(Task.create(er_category, 'Main', 'ER_1', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_1', heaviness=5, mandatory=True))

        task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_AB_CALL', heaviness=5, mandatory=True))
        task_manager.add_task(Task.create(er_category, 'Call', 'ER_CALL', heaviness=5, mandatory=True))


        # Link tasks
        task_manager.link_tasks('CTU_A', 'CTU_AB_CALL')
        task_manager.link_tasks('CTU_B', 'CTU_AB_CALL')
        task_manager.link_tasks('ER_1', 'ER_CALL')

    else:
        raise ValueError(f"Unknown task scenario label: {scenario_label}")


    return task_manager


def initialize_physician_manager(task_manager, scenario_label='default'):
    logger.info(f"Initializing Physician Manager with scenario: {scenario_label}")
    physician_manager = PhysicianManager(task_manager)

    if scenario_label == 'default':
        # Add physicians
        physicians = [
            Physician("Eric", "Yamga", ["CTU", "ER", "PREOP", "CONSULT"], True, 0.45, [], ["MOG", "VASC", "AMBU"]),
            Physician("Madeleine", "Durand", ["CONSULT", "CTU", "ER", "PREOP"], False, 0.3, [], ["MOG", "VASC", "AMBU"]),
            Physician("Emmanuelle", "Duceppe", ["CTU", "PREOP", "CONSULT"], False, 0.3, [], ["MOG", "VASC", "AMBU", "ER"]),
            Physician("Emmanuel", "Sirdar", ["CTU", "CONSULT", "ER", "PREOP"], False, 0.3, [], ["MOG", "VASC"]),


            Physician("Florence", "Weber", ["MOG", "ER", "CTU"],False, 0.6, ["MOG"], ["VASC"]),
            Physician("Sophie", "Grandmaison", ["MOG", "CTU", "ER", "AMBU"], False, 0.75, ["MOG"], ["VASC"]),
            Physician("Michèle", "Mahone", ["MOG", "CTU", "ER", "AMBU", "PREOP"], False, 0.75, ["MOG"], ["VASC"]),
            Physician("Nazila", "Bettache", ["MOG", "ER", "CTU", "AMBU", "CONSULT", "PREOP"], False, 0.5, ["MOG"], ["VASC"]),
            Physician("Vincent", "Williams", ["MOG", "CTU", "ER", "PREOP", "CONSULT", "AMBU"], False, 0.80, [], ["VASC"]),

            Physician("Gabriel", "Dion", ["CTU", "PREOP", "CONSULT"], False, 0.70, [], ["MOG", "VASC"]),
            Physician("Justine", "Munger", ["CTU"], True, 0.75, [], []),
            Physician("Mikhael", "Laskine", ["CTU", "CONSULT", "ER", "PREOP"], False, 0.8, [], ["AMBU"]),
            Physician("Benoit", "Deligne", ["ER", "CTU"], False, 0.25, [], ["MOG", "VASC"]),
            Physician("Maxime", "Lamarre-Cliche", ["CTU", "ER",  "CONSULT",  "PREOP", "AMBU"], False, 0.80, [], ["MOG", "VASC"]),
            Physician("Julien", "D'Astous", ["CTU", "CONSULT", "PREOP", "ER", "AMBU"], False, 0.75, [], ["MOG", "VASC"]),
            Physician("Jean-Pascal", "Costa", ["CTU", "ER", "AMBU", "PREOP", "CONSULT"], False, 0.70, [], ["MOG", "VASC"]),
            Physician("Camille", "Laflamme", ["ER",  "CONSULT", "CTU", "PREOP", "AMBU"], False, 0.70, [], ["MOG", "VASC"]),

            Physician("Robert", "Wistaff", ["CTU",  "CONSULT", "PREOP", "ER", "AMBU"], False, 0.85, [], ["MOG", "VASC"]),
            Physician("Rene", "Lecours", ["AMBU", "CTU", "CONSULT", "ER"], False, 0.80, [],
                      ["MOG", "VASC"]),
            Physician("Diem-Quyen", "Nguyen", ["CTU",  "CONSULT", "PREOP", "AMBU", "ER"], False, 0.70, [], ["MOG", "VASC"]),
            Physician("Michel", "Bertrand", ["CTU", "PREOP", "CONSULT"], False, 0.70, [], ["MOG", "VASC", "AMBU"]),

            Physician("J.Manuel", "Dominguez", ["CTU", "CONSULT", "PREOP", "ER"], False, 0.55, ["VASC"], ["MOG"]),
            Physician("Marie-Jose", "Miron", ["VASC"], False, 0.4, ["VASC"],
                      ["MOG", "CTU", "ER", "PREOP", "AMBU"]),
            Physician("André", "Roussin", ["VASC"], False, 0.35, ["VASC"],
                      ["MOG", "CTU", "CONSULT", "ER", "PREOP", "AMBU"]),
            Physician("Benoit", "Deligne", ["CTU", "CONSULT", "ER", "PREOP", "AMBU"], False, 0.5, [], ["MOG", "VASC"]),
            Physician("Martial", "Koenig", ["CTU", "CONSULT", "PREOP", "AMBU", "ER"], False, 0.8, [], ["MOG", "VASC"]),


            #Physician("Christopher Oliver", "Clapperton", ["CTU", "ER", "PREOP", "AMBU", "CONSULT"], False, 0, [], ["MOG", "VASC"]),
            #Physician("Brigitte", "Benard", ["PREOP", "CONSULT", "CTU", "AMBU"], False, 0, [], ["MOG", "VASC"]),
            #Physician("Audrey", "Lacasse", ["CTU", "ER"], False, 0.6, [], ["MOG", "VASC"]),

        ]
        for physician in physicians:
            physician_manager.add_physician(physician)

        unavailability_periods = {
            "Eric Yamga": [
                (date(2025, 2, 10), date(2025, 2, 23)),
                (date(2025, 5, 5), date(2025, 5, 11)),
            ],
            "Madeleine Durand": [
                (date(2025, 1, 13), date(2025, 1, 13)),
                (date(2025, 3, 17), date(2025, 3, 23)),
                (date(2025, 6, 9), date(2025, 6, 15)),
            ],
            "Emmanuelle Duceppe": [
                (date(2025, 2, 3), date(2025, 2, 9)),
                (date(2025, 4, 21), date(2025, 4, 21)),
                (date(2025, 6, 2), date(2025, 6, 15)),
            ],
            "Emmanuel Sirdar": [
                (date(2025, 1, 6), date(2025, 1, 12)),
                (date(2025, 3, 10), date(2025, 3, 16)),
                (date(2025, 5, 19), date(2025, 5, 25)),
            ],
            "Florence Weber": [
                (date(2025, 2, 17), date(2025, 2, 23)),
                (date(2025, 4, 14), date(2025, 4, 20)),
                (date(2025, 6, 23), date(2025, 6, 29)),
            ],
            "Sophie Grandmaison": [
                (date(2025, 1, 20), date(2025, 1, 26)),
                (date(2025, 3, 31), date(2025, 4, 6)),
            ],
            "Michèle Mahone": [
                (date(2025, 2, 24), date(2025, 3, 2)),
                (date(2025, 5, 12), date(2025, 5, 18)),
            ],
            "Nazila Bettache": [
                (date(2025, 1, 27), date(2025, 2, 2)),
                (date(2025, 4, 7), date(2025, 4, 13)),
                (date(2025, 6, 16), date(2025, 6, 22)),
            ],
            "Vincent Williams": [
                (date(2025, 3, 3), date(2025, 3, 9)),
                (date(2025, 5, 26), date(2025, 6, 1)),
            ],
            "Gabriel Dion": [
                (date(2025, 1, 30), date(2025, 1, 31)),
                (date(2025, 4, 28), date(2025, 5, 4)),
            ],
            "Justine Munger": [
                (date(2025, 1, 1), date(2025, 1, 5)),
                (date(2025, 3, 24), date(2025, 3, 30)),
                (date(2025, 6, 9), date(2025, 6, 15)),
            ],
            "Mikhael Laskine": [
                (date(2025, 2, 3), date(2025, 2, 9)),
                (date(2025, 5, 5), date(2025, 5, 11)),
            ],
            "Benoit Deligne": [
                (date(2025, 1, 13), date(2025, 1, 26)),
                (date(2025, 3, 31), date(2025, 4, 6)),
                (date(2025, 6, 2), date(2025, 6, 8)),
            ],
            "Maxime Lamarre-Cliche": [
                (date(2025, 3, 10), date(2025, 3, 16)),
                (date(2025, 5, 19), date(2025, 5, 25)),
            ],
            "Julien D'Astous": [
                (date(2025, 2, 10), date(2025, 2, 16)),
                (date(2025, 4, 21), date(2025, 4, 27)),
            ],
            "Jean-Pascal Costa": [
                (date(2025, 1, 27), date(2025, 2, 2)),
                (date(2025, 4, 7), date(2025, 4, 13)),
                (date(2025, 6, 16), date(2025, 6, 22)),
            ],
            "Camille Laflamme": [
                (date(2025, 3, 17), date(2025, 3, 23)),
                (date(2025, 5, 26), date(2025, 6, 1)),
            ],
            "Robert Wistaff": [
                (date(2025, 2, 17), date(2025, 2, 23)),
                (date(2025, 4, 28), date(2025, 5, 4)),
            ],
            "Rene Lecours": [
                (date(2025, 1, 6), date(2025, 1, 12)),
                (date(2025, 3, 24), date(2025, 3, 30)),
                (date(2025, 6, 9), date(2025, 6, 15)),
            ],
            "Diem-Quyen Nguyen": [
                (date(2025, 2, 24), date(2025, 3, 2)),
                (date(2025, 5, 12), date(2025, 5, 18)),
            ],
            "Michel Bertrand": [
                (date(2025, 1, 20), date(2025, 1, 26)),
                (date(2025, 4, 14), date(2025, 4, 20)),
            ],
            "J.Manuel Dominguez": [
                (date(2025, 3, 3), date(2025, 3, 9)),
                (date(2025, 5, 19), date(2025, 5, 25)),
            ],
            "Marie-Jose Miron": [
                (date(2025, 2, 3), date(2025, 2, 9)),
                (date(2025, 4, 21), date(2025, 4, 27)),
                (date(2025, 6, 23), date(2025, 6, 29)),
            ],
            "André Roussin": [
                (date(2025, 1, 13), date(2025, 1, 19)),
                (date(2025, 3, 31), date(2025, 4, 6)),
                (date(2025, 6, 2), date(2025, 6, 8)),
            ],
            "Martial Koenig": [
                (date(2025, 2, 10), date(2025, 2, 16)),
                (date(2025, 5, 5), date(2025, 5, 11)),
            ],
        }
        physician_manager.set_unavailability_periods(unavailability_periods)

    elif scenario_label == 'reduced_staff':
        physicians = [
            Physician("Eric", "Yamga", ["CTU", "ER", "PREOP", "CONSULT"], True, 0.45, [], ["MOG", "VASC", "AMBU"]),
            Physician("Madeleine", "Durand", ["CONSULT", "CTU", "ER", "PREOP"], False, 0.3, [], ["MOG", "VASC", "AMBU"]),
            Physician("Emmanuelle", "Duceppe", ["CTU", "PREOP", "CONSULT"], False, 0.3, [], ["MOG", "VASC", "AMBU", "ER"]),
            Physician("Emmanuel", "Sirdar", ["CTU", "CONSULT", "ER", "PREOP"], False, 0.3, [], ["MOG", "VASC"]),
            Physician("Florence", "Weber", ["MOG", "ER", "CTU"], False, 0.6, ["MOG"], ["VASC"]),
            Physician("André", "Roussin", ["VASC"], False, 0.35, ["VASC"],
                      ["MOG", "CTU", "CONSULT", "ER", "PREOP", "AMBU"]),
        ]

        for physician in physicians:
            physician_manager.add_physician(physician)

        # Set unavailability periods
        unavailability_periods = {
            "Eric Yamga": [
                (date(2025, 1, 6), date(2025, 1, 12)),
                date(2025, 2, 9),
            ],
            "Madeleine Durand": [
                (date(2025, 1, 6), date(2025, 1, 19)),
                date(2025, 2, 3),
            ],
            "Emmanuelle Duceppe": [
                (date(2025, 1, 20), date(2025, 1, 26)),
                date(2025, 2, 10),
            ]
        }
        physician_manager.set_unavailability_periods(unavailability_periods)

    elif scenario_label == 'all_modified_availability':
        physicians = [
            Physician("Eric", "Yamga", ["CTU", "ER", "PREOP", "CONSULT"], True, 0.45, [], ["MOG", "VASC", "AMBU"]),
            Physician("Madeleine", "Durand", ["CONSULT", "CTU", "ER", "PREOP"], False, 0.3, [], ["MOG", "VASC", "AMBU"]),
            Physician("Emmanuelle", "Duceppe", ["CTU", "PREOP", "CONSULT"], False, 0.3, [], ["MOG", "VASC", "AMBU", "ER"]),
            Physician("Emmanuel", "Sirdar", ["CTU", "CONSULT", "ER", "PREOP"], False, 0.3, [], ["MOG", "VASC"]),


            Physician("Florence", "Weber", ["MOG", "ER", "CTU"],False, 0.6, ["MOG"], ["VASC"]),
            Physician("Sophie", "Grandmaison", ["MOG", "CTU", "ER", "AMBU"], False, 0.75, ["MOG"], ["VASC"]),
            Physician("Michèle", "Mahone", ["MOG", "CTU", "ER", "AMBU", "PREOP"], False, 0.75, ["MOG"], ["VASC"]),
            Physician("Nazila", "Bettache", ["MOG", "ER", "CTU", "AMBU", "CONSULT", "PREOP"], False, 0.5, ["MOG"], ["VASC"]),
            Physician("Vincent", "Williams", ["MOG", "CTU", "ER", "PREOP", "CONSULT", "AMBU"], False, 0.80, [], ["VASC"]),

            Physician("Gabriel", "Dion", ["CTU", "PREOP", "CONSULT"], False, 0.70, [], ["MOG", "VASC"]),
            Physician("Justine", "Munger", ["CTU"], True, 0.75, [], []),
            Physician("Mikhael", "Laskine", ["CTU", "CONSULT", "ER", "PREOP"], False, 0.8, [], ["AMBU"]),
            Physician("Benoit", "Deligne", ["ER", "CTU"], False, 0.25, [], ["MOG", "VASC"]),
            Physician("Maxime", "Lamarre-Cliche", ["CTU", "ER",  "CONSULT",  "PREOP", "AMBU"], False, 0.80, [], ["MOG", "VASC"]),
            Physician("Julien", "D'Astous", ["CTU", "CONSULT", "PREOP", "ER", "AMBU"], False, 0.75, [], ["MOG", "VASC"]),
            Physician("Jean-Pascal", "Costa", ["CTU", "ER", "AMBU", "PREOP", "CONSULT"], False, 0.70, [], ["MOG", "VASC"]),
            Physician("Camille", "Laflamme", ["ER",  "CONSULT", "CTU", "PREOP", "AMBU"], False, 0.70, [], ["MOG", "VASC"]),

            Physician("Robert", "Wistaff", ["CTU",  "CONSULT", "PREOP", "ER", "AMBU"], False, 0.85, [], ["MOG", "VASC"]),
            Physician("Rene", "Lecours", ["AMBU", "CTU", "CONSULT", "ER"], False, 0.80, [],
                      ["MOG", "VASC"]),
            Physician("Diem-Quyen", "Nguyen", ["CTU",  "CONSULT", "PREOP", "AMBU", "ER"], False, 0.70, [], ["MOG", "VASC"]),
            Physician("Michel", "Bertrand", ["CTU", "PREOP", "CONSULT"], False, 0.70, [], ["MOG", "VASC", "AMBU"]),

            Physician("J.Manuel", "Dominguez", ["CTU", "CONSULT", "PREOP", "ER"], False, 0.55, ["VASC"], ["MOG"]),
            Physician("Marie-Jose", "Miron", ["VASC"], False, 0.4, ["VASC"],
                      ["MOG", "CTU", "ER", "PREOP", "AMBU"]),
            Physician("André", "Roussin", ["VASC"], False, 0.35, ["VASC"],
                      ["MOG", "CTU", "CONSULT", "ER", "PREOP", "AMBU"]),
            Physician("Benoit", "Deligne", ["CTU", "CONSULT", "ER", "PREOP", "AMBU"], False, 0.5, [], ["MOG", "VASC"]),
            Physician("Martial", "Koenig", ["CTU", "CONSULT", "PREOP", "AMBU", "ER"], False, 0.8, [], ["MOG", "VASC"]),


            #Physician("Christopher Oliver", "Clapperton", ["CTU", "ER", "PREOP", "AMBU", "CONSULT"], False, 0, [], ["MOG", "VASC"]),
            #Physician("Brigitte", "Benard", ["PREOP", "CONSULT", "CTU", "AMBU"], False, 0, [], ["MOG", "VASC"]),
            #Physician("Audrey", "Lacasse", ["CTU", "ER"], False, 0.6, [], ["MOG", "VASC"]),

        ]

        for physician in physicians:
            physician_manager.add_physician(physician)

        unavailability_periods = {
            "Eric Yamga": [
                (date(2025, 1, 6), date(2025, 1, 12)),
                (date(2025, 2, 10), date(2025, 2, 16)),
            ],
            "Madeleine Durand": [
                (date(2025, 1, 13), date(2025, 1, 19)),
                (date(2025, 2, 17), date(2025, 2, 23)),
            ],
            "Emmanuelle Duceppe": [
                (date(2025, 1, 20), date(2025, 1, 26)),
                (date(2025, 2, 24), date(2025, 2, 28)),
            ],
            "Emmanuel Sirdar": [
                (date(2025, 1, 27), date(2025, 2, 2)),
            ],
            "Florence Weber": [
                (date(2025, 2, 3), date(2025, 2, 9)),
            ],
            "Sophie Grandmaison": [
                (date(2025, 1, 1), date(2025, 1, 5)),
                (date(2025, 2, 10), date(2025, 2, 16)),
            ],
            "Michèle Mahone": [
                (date(2025, 1, 13), date(2025, 1, 26)),
            ],
            "Nazila Bettache": [
                (date(2025, 2, 3), date(2025, 2, 16)),
            ],
            "Vincent Williams": [
                (date(2025, 1, 6), date(2025, 1, 7)),
                (date(2025, 2, 17), date(2025, 2, 23)),
            ],
            "Gabriel Dion": [
                (date(2025, 1, 20), date(2025, 1, 26)),
                (date(2025, 2, 24), date(2025, 2, 25)),
            ],
            "Justine Munger": [
                (date(2025, 1, 27), date(2025, 2, 9)),
            ],
            "Mikhael Laskine": [
                (date(2025, 1, 1), date(2025, 1, 12)),
                (date(2025, 2, 17), date(2025, 2, 28)),
            ],
            "Benoit Deligne": [
                (date(2025, 1, 13), date(2025, 1, 19)),
                (date(2025, 2, 10), date(2025, 2, 16)),
            ],
            "Maxime Lamarre-Cliche": [
                (date(2025, 1, 20), date(2025, 1, 21)),
                (date(2025, 2, 24), date(2025, 2, 28)),
            ],
            "Julien D'Astous": [
                (date(2025, 1, 27), date(2025, 2, 2)),
                (date(2025, 2, 17), date(2025, 2, 23)),
            ],
            "Jean-Pascal Costa": [
                (date(2025, 1, 6), date(2025, 1, 19)),
            ],
            "Camille Laflamme": [
                (date(2025, 2, 3), date(2025, 2, 16)),
            ],
            "Robert Wistaff": [
                (date(2025, 1, 13), date(2025, 1, 26)),
                (date(2025, 2, 24), date(2025, 2, 28)),
            ],
            "Rene Lecours": [
                (date(2025, 1, 1), date(2025, 1, 5)),
                (date(2025, 2, 10), date(2025, 2, 23)),
            ],
            "Diem-Quyen Nguyen": [
                (date(2025, 1, 20), date(2025, 2, 2)),
            ],
            "Michel Bertrand": [
                (date(2025, 1, 6), date(2025, 1, 12)),
                (date(2025, 2, 17), date(2025, 2, 28)),
            ],
            "J.Manuel Dominguez": [
                (date(2025, 1, 27), date(2025, 2, 9)),
            ],
            "Marie-Jose Miron": [
                (date(2025, 1, 13), date(2025, 1, 19)),
                (date(2025, 2, 24), date(2025, 2, 25)),
            ],
            "André Roussin": [
                (date(2025, 1, 1), date(2025, 1, 14)),
                (date(2025, 2, 10), date(2025, 2, 16)),
            ],
            "Martial Koenig": [
                (date(2025, 1, 20), date(2025, 1, 26)),
                (date(2025, 2, 17), date(2025, 2, 23)),
            ],
        }

        physician_manager.set_unavailability_periods(unavailability_periods)

    else:
        raise ValueError(f"Unknown physician scenario label: {scenario_label}")


    return physician_manager


def initialize_calendar(scenario_label='default'):
    logger.info(f"Initializing Calendar with scenario: {scenario_label}")
    if scenario_label == 'default':
        start_date = date(2025, 1, 1)
        end_date = date(2025, 6, 30)
        region = 'Canada/QC'
    elif scenario_label == 'short_period':
        # Different dates for a short scheduling period
        start_date = date(2025, 1, 1)
        end_date = date(2025, 2, 28)
        region = 'Canada/QC'

    else:
        raise ValueError(f"Unknown calendar scenario label: {scenario_label}")

    calendar = Calendar.create_calendar(start_date, end_date, region)
    calendar.add_holiday(date(2024, 12, 25))
    calendar.add_holiday(date(2024, 12, 24))
    calendar.add_holiday(date(2025, 1, 1))
    calendar.add_holiday(date(2025, 1, 2))

    return calendar


def generate_schedule(
    physician_manager,
    task_manager,
    calendar,
    task_scenario_label='default',
    physician_scenario_label='default',
    calendar_scenario_label='default',
    schedule_scenario_label='default'
):

    config_name = f"{task_scenario_label}_{physician_scenario_label}_{calendar_scenario_label}_{schedule_scenario_label}"
    logger.info(f"Generating schedules with scenario: {config_name}")

    start_date = calendar.start_date
    end_date = calendar.end_date



    if schedule_scenario_label == 'default':
        task_splits = {
            # Default task splits
            "CTU": {"linked": "5:2", "unlinked": "5:2"},
            "ER": {"linked": "5:2", "unlinked": "5:2"},
            # Add other tasks as needed
        }

        off_days = {
            # Default off days
            "CTU": [],
            "ER": []
        }

    elif schedule_scenario_label == 'unavailability_test':
        off_days = {
            "AMBU": [date(2025, 1, 6), date(2025, 1, 10)],
        }

    elif schedule_scenario_label == 'task_splitting_test':
        task_splits = {
            "CTU": {"linked": "5:2", "unlinked": "5:2"},
            "ER": {"linked": "5:2", "unlinked": "5:2"},
            "CONSULT": {"linked": "5:2", "unlinked": "5:2"},
            "PREOP": {"linked": "5:2", "unlinked": "5:2"},
            "AMBU": {"linked": "5:2", "unlinked": "5:2"},
            "MOG": {"linked": "5:2", "unlinked": "5:2"},
            "VASC": {"linked": "5:2", "unlinked": "5:2"}

        }
    else:
        raise ValueError(f"Unknown schedule scenario label: {schedule_scenario_label}")



    # Create schedule instance
    schedule = MathSchedule(physician_manager, task_manager, calendar)
    schedule.set_scheduling_period(start_date, end_date)
    schedule.set_task_splits(task_splits)
    schedule.set_off_days(off_days)

    # Load initial schedule
    schedule.load_schedule("output/schedule/loaded_schedule.json")

    schedule.generate_schedule(use_initial_schedule=False)
    schedule.print_schedule()

    config_name = config_name.replace(' ', '_')
    schedule.export_model(f"output/models/model_{config_name}.txt")
    schedule.generate_ics_calendar(f"output/schedule/{config_name}_generated_calendar.ics")
    schedule.save_schedule(f"output/schedule/{config_name}_generated_schedule.json")


def generate_all_combinations():
    """Generate all possible combinations of scenarios."""
    return list(itertools.product(
        TASK_SCENARIOS.keys(),
        PHYSICIAN_SCENARIOS.keys(),
        CALENDAR_SCENARIOS.keys(),
        SCHEDULE_SCENARIOS.keys()
    ))

def run_scenario(task_scenario, physician_scenario, calendar_scenario, schedule_scenario):
    """Run a single scenario combination."""
    logger.info(f"\nRunning scenario combination:")
    logger.info(f"Task scenario: {task_scenario} - {TASK_SCENARIOS[task_scenario]}")
    logger.info(f"Physician scenario: {physician_scenario} - {PHYSICIAN_SCENARIOS[physician_scenario]}")
    logger.info(f"Calendar scenario: {calendar_scenario} - {CALENDAR_SCENARIOS[calendar_scenario]}")
    logger.info(f"Schedule scenario: {schedule_scenario} - {SCHEDULE_SCENARIOS[schedule_scenario]}")

    task_manager = initialize_task_manager(scenario_label=task_scenario)
    physician_manager = initialize_physician_manager(task_manager, scenario_label=physician_scenario)
    calendar = initialize_calendar(scenario_label=calendar_scenario)

    generate_schedule(
        physician_manager,
        task_manager,
        calendar,
        task_scenario_label=task_scenario,
        physician_scenario_label=physician_scenario,
        calendar_scenario_label=calendar_scenario,
        schedule_scenario_label=schedule_scenario
    )


def main():
    parser = argparse.ArgumentParser(description="Physician Scheduling Application")
    parser.add_argument('--run_all', action='store_true', help='Run all scenario combinations')
    parser.add_argument('--generate', nargs=4, metavar=('TASK', 'PHYSICIAN', 'CALENDAR', 'SCHEDULE'),
                        help='Generate a specific combination of scenarios')
    parser.add_argument('--task_scenario', type=str, choices=TASK_SCENARIOS.keys(),
                        help='Task initialization scenario label')
    parser.add_argument('--physician_scenario', type=str, choices=PHYSICIAN_SCENARIOS.keys(),
                        help='Physician initialization scenario label')
    parser.add_argument('--calendar_scenario', type=str, choices=CALENDAR_SCENARIOS.keys(),
                        help='Calendar initialization scenario label')
    parser.add_argument('--schedule_scenario', type=str, choices=SCHEDULE_SCENARIOS.keys(),
                        help='Schedule generation scenario label')

    args = parser.parse_args()

    if args.run_all:
        logger.info(f"RUNNING ALL")
        all_combinations = generate_all_combinations()
        total_combinations = len(all_combinations)
        logger.info(f"Running all {total_combinations} scenario combinations")

        for i, (task, physician, calendar, schedule) in enumerate(all_combinations, 1):
            logger.info(f"\nRunning combination {i}/{total_combinations}")
            run_scenario(task, physician, calendar, schedule)
    elif args.generate:
        task, physician, calendar, schedule = args.generate
        if (task in TASK_SCENARIOS and physician in PHYSICIAN_SCENARIOS and
                calendar in CALENDAR_SCENARIOS and schedule in SCHEDULE_SCENARIOS):
            run_scenario(task, physician, calendar, schedule)
        else:
            logger.error("Invalid scenario combination. Please check your input.")
    elif any([args.task_scenario, args.physician_scenario, args.calendar_scenario, args.schedule_scenario]):
        run_scenario(
            args.task_scenario or 'default',
            args.physician_scenario or 'default',
            args.calendar_scenario or 'default',
            args.schedule_scenario or 'default'
        )
    else:
        # Run default scenario if no arguments are provided
        run_scenario('default', 'default', 'default', 'default')


if __name__ == "__main__":
    main()

# python main_test.py --run_all
# python main_test.py --task_scenario restricted_tasks --physician_scenario default --calendar_scenario default --schedule_scenario default