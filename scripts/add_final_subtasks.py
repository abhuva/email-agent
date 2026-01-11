#!/usr/bin/env python3
"""Add mandatory final stage subtask to all tasks in tasks.json"""

import json
from pathlib import Path

def add_final_subtask(task):
    """Add final stage subtask to a task"""
    final_subtask = {
        "id": len(task['subtasks']) + 1,
        "title": "Final stage: Validate tests, update documentation, review rules, mark done, and commit",
        "description": "MANDATORY final stage: Run tests, update documentation, review for rule learnings, mark task done in Task Master, and commit all changes.",
        "status": "pending",
        "dependencies": list(range(1, len(task['subtasks']) + 1)),
        "details": f"""1) Run full test suite: pytest -v and ensure all tests pass (new and existing). Fix any failing tests before proceeding.
2) Update/create module documentation in docs/ directory following documentation.mdc guidelines. Update docs/MAIN_DOCS.md if adding new documentation. Reference relevant PDD sections.
3) Review code for patterns that should be captured in rules (see .cursor/rules/self_improve.mdc). Add new rules if: new technology/pattern used in 3+ files, common bugs could be prevented, or new best practices emerged. Update existing rules if better examples exist.
4) Mark task done in Task Master: task-master set-status --id={task['id']} --status=done
5) Commit tasks.json: git add tasks/tasks.json && git commit -m "chore(tasks): Mark task {task['id']} complete"
6) Commit all changes: git add . && git commit -m "feat(module): Task {task['id']} - {task['title']} [docs]"
This workflow is MANDATORY and must not be skipped. See .cursor/rules/task_completion_workflow.mdc for details."""
    }
    task['subtasks'].append(final_subtask)

def main():
    tasks_file = Path(__file__).parent.parent / 'tasks' / 'tasks.json'
    
    with open(tasks_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for task in data['tasks']:
        add_final_subtask(task)
    
    with open(tasks_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Added final stage subtask to {len(data['tasks'])} tasks")

if __name__ == '__main__':
    main()
