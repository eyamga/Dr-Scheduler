import logging
from datetime import date
from models.task import TaskCategory, Task, TaskDaysParameter
from models.physician import Physician
from models.calendar import Calendar
from models.schedule import Schedule
from models.math_schedule import MathSchedule
from config.managers import TaskManager, PhysicianManager


def setup_logging():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def initialize_task_manager():
    task_manager = TaskManager()

    # Add categories
    ctu_category = TaskCategory(name="CTU", days_parameter=TaskDaysParameter.MULTI_WEEK, number_of_weeks=2,
                                weekday_revenue=2000, call_revenue=4000, restricted=False)
    # er_category = TaskCategory(name="ER", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
    #                            weekday_revenue=2500, call_revenue=5000, restricted=True)
    #
    # consult_category = TaskCategory(name="CONSULT", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
    #                            weekday_revenue=2000, call_revenue=3000, restricted=True)
    #
    # preop_category = TaskCategory(name="PREOP", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
    #                            weekday_revenue=2000, call_revenue=0, restricted=True)
    #
    # ambu_category = TaskCategory(name="AMBU", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
    #                      weekday_revenue=1000, call_revenue=0, restricted=True)
    #
    # mog_category = TaskCategory(name="MOG", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
    #                      weekday_revenue=1500, call_revenue=0, restricted=True)
    #
    # vasc_category = TaskCategory(name="VASC", days_parameter=TaskDaysParameter.CONTINUOUS, number_of_weeks=1,
    #                      weekday_revenue=2000, call_revenue=2500, restricted=True)

    task_manager.add_category(ctu_category)
    # task_manager.add_category(er_category)
    # task_manager.add_category(consult_category)
    #
    # task_manager.add_category(preop_category)
    # task_manager.add_category(ambu_category)
    #
    # task_manager.add_category(mog_category)
    # task_manager.add_category(vasc_category)


    # Add tasks
    task_manager.add_task(Task.create(ctu_category, 'Main', 'CTU_A', heaviness=4, mandatory=True))
    task_manager.add_task(Task.create(ctu_category, 'Main', 'CTU_B', week_offset=1, heaviness=4, mandatory=True))
    # task_manager.add_task(Task.create(ctu_category, 'Main', 'CTU_C', heaviness=4, mandatory=True))
    # task_manager.add_task(Task.create(ctu_category, 'Main', 'CTU_D', week_offset=1, heaviness=4, mandatory=True))
    #
    # task_manager.add_task(Task.create(er_category, 'Main', 'ER_1', heaviness=5, mandatory=True))
    # task_manager.add_task(Task.create(er_category, 'Main', 'ER_2', heaviness=5, mandatory=True))
    #
    # task_manager.add_task(Task.create(consult_category, 'Main', 'CONSULT_1', heaviness=5, mandatory=True))
    # task_manager.add_task(Task.create(consult_category, 'Main', 'CONSULT_2', heaviness=5, mandatory=True))
    #
    # task_manager.add_task(Task.create(preop_category, 'Main', 'PREOP_1', heaviness=5, mandatory=True))
    # task_manager.add_task(Task.create(preop_category, 'Main', 'PREOP_2', heaviness=5, mandatory=True))
    #
    # task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_1', heaviness=5, mandatory=True))
    # task_manager.add_task(Task.create(ambu_category, 'Main', 'AMBU_2', heaviness=5, mandatory=True))
    #
    # task_manager.add_task(Task.create(mog_category, 'Main', 'MOG', heaviness=5, mandatory=False))
    # task_manager.add_task(Task.create(vasc_category, 'Main', 'VASC', heaviness=5, mandatory=False))

    task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_AB_CALL', heaviness=5, mandatory=True))
    # task_manager.add_task(Task.create(ctu_category, 'Call', 'CTU_CD_CALL', heaviness=5, mandatory=True))
    # task_manager.add_task(Task.create(er_category, 'Call', 'ER_CALL', heaviness=5, mandatory=True))
    # task_manager.add_task(Task.create(consult_category, 'Call', 'CONSULT_CALL', heaviness=5, mandatory=True))
    #
    # task_manager.add_task(Task.create(mog_category, 'Call', 'MOG_CALL', heaviness=5, mandatory=False))
    # task_manager.add_task(Task.create(vasc_category, 'Call', 'VASC_CALL', heaviness=5, mandatory=False))

    # Link tasks
    task_manager.link_tasks('CTU_A', 'CTU_AB_CALL')
    task_manager.link_tasks('CTU_B', 'CTU_AB_CALL')
    # task_manager.link_tasks('CTU_C', 'CTU_CD_CALL')
    # task_manager.link_tasks('CTU_D', 'CTU_CD_CALL')
    #
    # task_manager.link_tasks('ER_1', 'ER_CALL')
    # task_manager.link_tasks('ER_2', 'ER_CALL')
    #
    # task_manager.link_tasks('CONSULT_1', 'CONSULT_CALL')
    # task_manager.link_tasks('CONSULT_2', 'CONSULT_CALL')
    #
    # task_manager.link_tasks('VASC', 'VASC_CALL')
    # task_manager.link_tasks('MOG', 'MOG_CALL')
    #

    return task_manager


def initialize_physician_manager(task_manager):
    physician_manager = PhysicianManager(task_manager)

    # Add physicians
    physicians = [
        Physician("Eric", "Yamga", ["CTU"], True, 0.5, [], []),
        Physician("Justine", "Munger", ["CTU"], True, 0.75, [], []),
        # Physician("Audrey", "Lacasse", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
        # Physician("Diem-Quyen", "Nguyen", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
        # Physician("Mikhael", "Laskine", ["ER", "CTU"], False, 1.0, [], ["MOG", "VASC"]),
        # Physician("Benoit", "Deligne", ["ER", "CTU"], False, 0.25, [], ["MOG", "VASC"]),
        # Physician("Michèle", "Mahone", ["ER", "CTU"], False, 0.75, ["MOG"], ["VASC"]),
        # Physician("Robert", "Wistaff", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
        # Physician("Nazila", "Bettache", ["ER", "CTU"], False, 0.5, ["MOG"], ["VASC"]),
        # Physician("Vincent", "Williams", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
        # Physician("Maxime", "Lamarre-Cliche", ["ER", "CTU"], False, 1.0, [], ["MOG", "VASC"]),
        # Physician("Julien", "D'Astous", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
        # Physician("Jean-Pascal", "Costa", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
        # Physician("J.Manuel", "Dominguez", ["ER", "CTU"], False, 1.0, ["VASC"], ["MOG"]),
        # Physician("Camille", "Laflamme", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
        # Physician("Florence", "Weber", ["ER", "CTU"], False, 0.75, ["MOG"], ["VASC"]),
        # Physician("Sophie", "Grandmaison", ["ER", "CTU"], False, 0.75, ["MOG"], ["MOG", "VASC"]),
        # Physician("Marie-Jose", "Miron", ["ER", "CTU"], False, 0.75, ["VASC"], ["MOG", "CTU", "ER", "PREOP", "AMBU"]),
        # Physician("Emmanuelle", "Duceppe", ["PREOP", "CTU"], False, 0.5, [], ["MOG", "VASC"]),
        # Physician("Michel", "Bertrand", ["ER", "CTU"], False, 1.0, [], ["MOG", "VASC"]),
        # Physician("André", "Roussin", ["ER", "CTU"], False, 0.75, ["VASC"], ["CTU", "CONSULT", "ER", "PREOP", "AMBU"]),
        # Physician("Madeleine", "Durand", ["ER", "CTU"], False, 1.0, [], ["MOG", "VASC"]),
        # Physician("Gabriel", "Dion", ["PREOP", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
        # Physician("Brigitte", "Benard", ["ER", "CTU"], False, 0.25, [], ["MOG", "VASC"]),
        # Physician("Christopher Oliver", "Clapperton", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
    ]
    # # Add physicians
    # physicians = [
    #     Physician("Eric", "Yamga", ["ER", "CTU"], True, 0.5, [], ["MOG", "VASC"]),
    #     Physician("Justine", "Munger", ["ER", "CTU"], True, 0.75, [], ["MOG", "VASC"]),
    #     Physician("Audrey", "Lacasse", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
    #     Physician("Diem-Quyen", "Nguyen", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
    #     Physician("Mikhael", "Laskine", ["ER", "CTU"], False, 1.0, [], ["MOG", "VASC"]),
    #     Physician("Benoit", "Deligne", ["ER", "CTU"], False, 0.25, [], ["MOG", "VASC"]),
    #     Physician("Michèle", "Mahone", ["ER", "CTU"], False, 0.75, ["MOG"], ["VASC"]),
    #     Physician("Robert", "Wistaff", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
    #     Physician("Nazila", "Bettache", ["ER", "CTU"], False, 0.5, ["MOG"], ["VASC"]),
    #     Physician("Vincent", "Williams", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
    #     Physician("Maxime", "Lamarre-Cliche", ["ER", "CTU"], False, 1.0, [], ["MOG", "VASC"]),
    #     Physician("Julien", "D'Astous", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
    #     Physician("Jean-Pascal", "Costa", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
    #     Physician("J.Manuel", "Dominguez", ["ER", "CTU"], False, 1.0, ["VASC"], ["MOG"]),
    #     Physician("Camille", "Laflamme", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
    #     Physician("Florence", "Weber", ["ER", "CTU"], False, 0.75, ["MOG"], ["VASC"]),
    #     Physician("Sophie", "Grandmaison", ["ER", "CTU"], False, 0.75, ["MOG"], ["MOG", "VASC"]),
    #     Physician("Marie-Jose", "Miron", ["ER", "CTU"], False, 0.75, ["VASC"], ["MOG", "CTU", "ER", "PREOP", "AMBU"]),
    #     Physician("Emmanuelle", "Duceppe", ["PREOP", "CTU"], False, 0.5, [], ["MOG", "VASC"]),
    #     Physician("Michel", "Bertrand", ["ER", "CTU"], False, 1.0, [], ["MOG", "VASC"]),
    #     Physician("André", "Roussin", ["ER", "CTU"], False, 0.75, ["VASC"], ["CTU", "CONSULT", "ER", "PREOP", "AMBU"]),
    #     Physician("Madeleine", "Durand", ["ER", "CTU"], False, 1.0, [], ["MOG", "VASC"]),
    #     Physician("Gabriel", "Dion", ["PREOP", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
    #     Physician("Brigitte", "Benard", ["ER", "CTU"], False, 0.25, [], ["MOG", "VASC"]),
    #     Physician("Christopher Oliver", "Clapperton", ["ER", "CTU"], False, 0.75, [], ["MOG", "VASC"]),
    # ]
    for physician in physicians:
        physician_manager.add_physician(physician)

    # Set unavailability periods
    unavailability_periods = {
        "Eric Yamga": [
            (date(2024, 1, 1), date(2024, 1, 7)),
            date(2024, 1, 9),
        ],
        "Justine Munger": [
            (date(2024, 2, 1), date(2024, 2, 14)),
            date(2024, 3, 3),
        ]
    }
    physician_manager.set_unavailability_periods(unavailability_periods)

    return physician_manager


def initialize_calendar():
    start_date = date(2024, 12, 1)
    end_date = date(2025, 3, 30)
    region = 'Canada/QC'
    calendar = Calendar.create_calendar(start_date, end_date, region)
    calendar.add_holiday(date(2025, 1, 2))
    calendar.add_holiday(date(2025, 1, 1))
    calendar.add_holiday(date(2024, 12, 25))
    calendar.add_holiday(date(2024, 12, 24))
    return calendar


def generate_schedules(physician_manager, task_manager, calendar, schedule_type='both'):
    start_date = date(2025, 1, 12)
    end_date = date(2025, 2, 6)
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

    schedules = {}

    if schedule_type in ['math', 'both']:
        schedules['math'] = MathSchedule(physician_manager, task_manager, calendar)

    if schedule_type in ['old', 'both']:
        schedules['old'] = Schedule(physician_manager, task_manager, calendar)

    for name, schedule in schedules.items():
        schedule.set_scheduling_period(start_date, end_date)
        schedule.set_task_splits(task_splits)
        #schedule.set_off_days(off_days)


        # schedule.load_schedule("initial_schedule.json")
        schedule.generate_schedule(use_initial_schedule=False)
        schedule.export_model("model.txt")
        schedule.print_schedule()
        schedule.generate_ics_calendar(f"output/schedule/{name}_generated_calendar.ics")
        schedule.save_schedule(f"output/schedule/{name}_generated_schedule.json")

    return schedules


def main():
    setup_logging()

    task_manager = initialize_task_manager()
    task_manager.save_config("output/config/task_config.json")
    loaded_task_manager = TaskManager.load_config("output/config/task_config.json")

    physician_manager = initialize_physician_manager(loaded_task_manager)
    physician_manager.save_config("output/config/physician_config.json")
    loaded_physician_manager = PhysicianManager.load_config("output/config/physician_config.json", "output/config/task_config.json")

    calendar = initialize_calendar()
    calendar.save_calendar("output/config/calendar.json")
    loaded_calendar = Calendar.load_calendar("output/config/calendar.json")

    # Generate both schedules (default behavior)
    all_schedules = generate_schedules(loaded_physician_manager, loaded_task_manager, loaded_calendar, "math")

    # Uncomment the following lines to generate only one type of schedule
    # math_schedules = generate_schedules(loaded_physician_manager, loaded_task_manager, loaded_calendar, schedule_type='both')
    # old_schedules = generate_schedules(loaded_physician_manager, loaded_task_manager, loaded_calendar, schedule_type='old')


if __name__ == "__main__":
    main()
