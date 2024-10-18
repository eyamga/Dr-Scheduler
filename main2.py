import logging
from datetime import date
from models.task import TaskCategory, Task, TaskDaysParameter
from models.physician import Physician
from models.calendar import Calendar
from models.math_schedule import MathSchedule
from config.managers import TaskManager, PhysicianManager


def setup_logging():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


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
    task_manager.add_task(Task.create(preop_category, 'Main', 'PREOP_2', heaviness=5, mandatory=True))
    #
    task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_1', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_2', heaviness=5, mandatory=True))

    task_manager.add_task(Task.create(mog_category, 'Main', 'MOG', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(vasc_category, 'Main', 'VASC', heaviness=5, mandatory=False))

    task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_AB_CALL', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_CD_CALL', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(er_category, 'Call', 'ER_CALL', heaviness=5, mandatory=True))
    task_manager.add_task(Task.create(consult_category, 'Call', 'CONSULT_CALL', heaviness=5, mandatory=True))

    task_manager.add_task(Task.create(mog_category, 'Call', 'MOG_CALL', heaviness=5, mandatory=True))
    # task_manager.add_task(Task.create(vasc_category, 'Call', 'VASC_CALL', heaviness=5, mandatory=False))

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
        Physician("Sophie", "Grandmaison", ["MOG", "CTU", "ER", "AMBU"], False, 0.75, ["MOG"], ["VASC"]),
        Physician("Michèle", "Mahone", ["MOG", "CTU", "ER", "AMBU", "PREOP"], False, 0.75, ["MOG"], ["VASC"]),
        Physician("Nazila", "Bettache", ["MOG", "ER", "CTU", "AMBU", "CONSULT", "PREOP"], False, 0.5, ["MOG"], ["VASC"]),
        Physician("Vincent", "Williams", ["MOG", "CTU", "ER", "PREOP", "CONSULT", "AMBU"], False, 0.80, [], ["VASC"]),

        Physician("Gabriel", "Dion", ["CTU", "PREOP", "CONSULT"], False, 0.70, [], ["MOG", "VASC"]),
        Physician("Justine", "Munger", ["CTU"], True, 0.75, [], ["MOG", "VASC"]),
        Physician("Mikhael", "Laskine", ["CTU", "CONSULT", "ER", "PREOP"], False, 0.8, [], ["AMBU", "VASC"]),
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
        Physician("Vasc", "Vasc", [], False, 1.0, [], ["MOG", "CTU", "CONSULT", "ER", "PREOP", "AMBU"]),

        Physician("Benoit", "Deligne", ["CTU", "CONSULT", "ER", "PREOP", "AMBU"], False, 0.5, [], ["MOG", "VASC"]),
        Physician("Martial", "Koenig", ["CTU", "CONSULT", "PREOP", "AMBU", "ER"], False, 0.8, [], ["MOG", "VASC"]),

        #Physician("Christopher Oliver", "Clapperton", ["CTU", "ER", "PREOP", "AMBU", "CONSULT"], False, 0, [], ["MOG", "VASC"]),
        #Physician("Brigitte", "Benard", ["PREOP", "CONSULT", "CTU", "AMBU"], False, 0, [], ["MOG", "VASC"]),
        #Physician("Audrey", "Lacasse", ["CTU", "ER"], False, 0.6, [], ["MOG", "VASC"]),
        ]



    for physician in physicians:
        physician_manager.add_physician(physician)

    # Set unavailability periods
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
                (date(2025, 1, 13), date(2025, 1, 26)),
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

    return physician_manager


def initialize_calendar():
    start_date = date(2024, 1, 6)
    end_date = date(2025, 6, 30)
    region = 'Canada/QC'
    calendar = Calendar.create_calendar(start_date, end_date, region)
    calendar.add_holiday(date(2025, 1, 2))
    calendar.add_holiday(date(2025, 1, 1))
    calendar.add_holiday(date(2024, 12, 25))
    calendar.add_holiday(date(2024, 12, 24))
    return calendar


def generate_schedules(physician_manager, task_manager, calendar):
    start_date = date(2025, 1, 6)
    end_date = date(2025, 6, 30)
    task_splits = {
        "CTU": {"linked": "5:2", "unlinked": "5:2"},
        "ER": {"linked": "5:2", "unlinked": "5:2"},
        "CONSULT": {"linked": "5:2", "unlinked": "5:2"},
        "PREOP": {"linked": "5:2", "unlinked": "5:2"},
        "AMBU": {"linked": "5:2", "unlinked": "5:2"},
        "MOG": {"linked": "5:2", "unlinked": "5:2"},
        "VASC": {"linked": "5:2", "unlinked": "5:2"}

    }

    off_days = {
        "CTU": [date(2023, 1, 3), date(2023, 12, 25)],
        "ER": [date(2023, 7, 4)]
    }

    schedule = MathSchedule(physician_manager, task_manager, calendar)

    schedule.set_scheduling_period(start_date, end_date)
    schedule.set_task_splits(task_splits)
    schedule.set_off_days(off_days)


    # schedule.load_schedule("initial_schedule.json")
    schedule.generate_schedule(use_initial_schedule=False)
    schedule.export_model("model.txt")
    schedule.print_schedule()
    schedule.generate_ics_calendar(f"output/schedule/math_generated_calendar.ics")
    schedule.save_schedule(f"output/schedule/math_generated_schedule.json")



def main():
    setup_logging()

    task_manager = initialize_task_manager()
    task_manager.save_config("output/config/task_config.json")
    #loaded_task_manager = TaskManager.load_config("output/config/task_config.json")

    physician_manager = initialize_physician_manager(task_manager)
    physician_manager.save_config("output/config/physician_config.json")
    #loaded_physician_manager = PhysicianManager.load_config("output/config/physician_config.json", "output/config/task_config.json")

    calendar = initialize_calendar()
    calendar.save_calendar("output/config/calendar.json")
    #loaded_calendar = Calendar.load_calendar("output/config/calendar.json")

    # Generate both schedules (default behavior)
    schedule = generate_schedules(physician_manager, task_manager, calendar)

    schedule

if __name__ == "__main__":
    main()



