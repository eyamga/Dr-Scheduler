import logging
import json
from typing import Dict, List, Any
from datetime import date, timedelta
import requests

class O1Schedule:
    """
    Uses an LLM via OpenRouter API to generate the physician schedule.
    """

    def __init__(self, physician_manager, task_manager, calendar, api_key):
        self.physician_manager = physician_manager
        self.task_manager = task_manager
        self.calendar = calendar
        self.api_key = api_key  # OpenRouter API key
        self.schedule = {}
        self.scheduling_period = None
        self.model = "your_preferred_llm_model"  # Specify the model to use
        logging.debug("O1Schedule initialized")

    def set_scheduling_period(self, start_date: date, end_date: date):
        self.scheduling_period = (start_date, end_date)
        logging.debug(f"Scheduling period set to {self.scheduling_period}")

    def generate_schedule(self):
        """
        Generate a schedule using the LLM via OpenRouter API.
        """
        if not self.scheduling_period:
            raise ValueError("Scheduling period must be set before generating schedule")

        logging.info("Starting LLM-based schedule generation...")

        # Prepare the prompt with all necessary information
        prompt = self._create_prompt()

        # Call the OpenRouter API
        response = self._call_openrouter_api(prompt)

        # Parse the LLM's response
        self.schedule = self._parse_llm_response(response)

        logging.info("Schedule generation completed")

    def _create_prompt(self) -> str:
        """
        Creates a prompt containing all the necessary information for the LLM.
        """
        prompt = f"""
You are tasked with generating a physician schedule based on the following parameters:

**Scheduling Period**: {self.scheduling_period[0]} to {self.scheduling_period[1]}

**Tasks**:
{json.dumps(self._get_tasks_info(), indent=2)}

**Physicians**:
{json.dumps(self._get_physicians_info(), indent=2)}

**Periods**:
{json.dumps(self.calendar.determine_periods(), indent=2, default=str)}

**Constraints and Rules**:
{self._get_constraints()}

Please generate a schedule assigning tasks to physicians for each period, adhering to all constraints and optimizing for fairness, preferences, and workload balance.

Provide the schedule in JSON format, structured as:
{
    "physician_name": [
        {
            "task": "Task Name",
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD"
        },
        ...
    ],
    ...
}
"""
        return prompt

    def _get_tasks_info(self) -> Dict[str, Any]:
        # Collect task information
        tasks_info = {}
        for task in self.task_manager.data['tasks']:
            tasks_info[task.name] = {
                "category": task.category.name,
                "type": task.type.value,
                "heaviness": task.heaviness,
                "mandatory": task.mandatory,
                "linked_task": self.task_manager.data['linkage_manager'].get_linked_call(task)
            }
        return tasks_info

    def _get_physicians_info(self) -> Dict[str, Any]:
        # Collect physician information
        physicians_info = {}
        for physician in self.physician_manager.data['physicians']:
            physicians_info[physician.name] = {
                "preferred_tasks": physician.preferred_tasks,
                "discontinuity_preference": physician.discontinuity_preference,
                "desired_working_percentage": physician.desired_working_weeks,
                "exclusion_tasks": physician.exclusion_tasks,
                "restricted_tasks": physician.restricted_tasks,
                "unavailabilities": [
                    [period[0].isoformat(), period[1].isoformat()] if isinstance(period, tuple) else period.isoformat()
                    for period in self.physician_manager.get_unavailability_periods(physician.name)
                ]
            }
        return physicians_info

    def _get_constraints(self) -> str:
        # Define the constraints and rules as per your specifications
        constraints = """
- All tasks must be assigned to a physician for the entire given period.
- If a call task is linked to a main task, the physician doing the main task must do the linked call task.
- Discontinuity preference: pair physicians who prefer discontinuity to split tasks accordingly.
- Fair distribution of workload, revenue, and calls.
- Respect physicians' availability, preferred tasks, and exclusions.
- Do not assign more than one call per month to a physician.
- Prioritize assigning tasks based on physicians' preferred tasks and desired working percentage.
"""
        return constraints

    def _call_openrouter_api(self, prompt: str) -> str:
        """
        Calls the OpenRouter API with the provided prompt and returns the response.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": 1500,
            "temperature": 0.7,
            "top_p": 1,
        }
        response = requests.post("https://api.openrouter.ai/v1/chat/completions", json=data, headers=headers)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            logging.error(f"OpenRouter API call failed: {response.status_code} {response.text}")
            raise Exception("OpenRouter API call failed")

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parses the LLM's response to extract the schedule.
        """
        try:
            schedule = json.loads(response)
            return schedule
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse LLM response: {e}")
            raise

    def get_schedule(self) -> Dict[str, Any]:
        return self.schedule

    def print_schedule(self):
        for physician, assignments in self.schedule.items():
            print(f"\n{physician}:")
            for assignment in assignments:
                print(f"  {assignment['task']}: {assignment['start_date']} - {assignment['end_date']}")

    def save_schedule(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.schedule, f, indent=2)

    def generate_ics_calendar(self, filename):
        # Implement calendar generation if needed
        pass 